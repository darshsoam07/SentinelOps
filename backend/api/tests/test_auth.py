from datetime import UTC, datetime, timedelta
import secrets
import jwt
from fastapi.testclient import TestClient
from pydantic import SecretStr
from app.api.routers.auth import hasher
from app.core.config import settings
from app.main import app


def test_authentication(monkeypatch, tmp_path):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PrivateFormat,
        PublicFormat,
        NoEncryption,
    )

    key = Ed25519PrivateKey.generate()
    private = tmp_path / "private.pem"
    public = tmp_path / "public.pem"
    private.write_bytes(
        key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    )
    public.write_bytes(
        key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
    )
    password = secrets.token_hex(16)
    monkeypatch.setattr(settings, "sentinelops_private_key_file", str(private))
    monkeypatch.setattr(settings, "sentinelops_public_key_file", str(public))
    monkeypatch.setattr(
        settings, "sentinelops_password_hash", SecretStr(hasher.hash(password))
    )
    with TestClient(app) as client:
        for path in ("/incidents", "/api/v1/incidents"):
            assert client.get(path).status_code == 401
        path = "/api/v1/auth/login"
        assert (
            client.post(
                path, data={"username": "operator", "password": "wrong"}
            ).status_code
            == 401
        )
        token = client.post(
            path, data={"username": "operator", "password": password}
        ).json()["access_token"]
        assert client.get(
            "/api/v1/users/me", headers={"Authorization": "Bearer " + token}
        ).json() == {"username": "operator"}
        claims = jwt.decode(
            token,
            key.public_key(),
            algorithms=["EdDSA"],
            audience="sentinelops-workspace",
        )
        for invalid in (
            jwt.encode(
                {**claims, "exp": datetime.now(UTC) - timedelta(seconds=1)},
                key,
                algorithm="EdDSA",
            ),
            jwt.encode(claims, Ed25519PrivateKey.generate(), algorithm="EdDSA"),
            jwt.encode(claims, secrets.token_hex(32), algorithm="HS256"),
        ):
            assert (
                client.get(
                    "/api/v1/users/me", headers={"Authorization": "Bearer " + invalid}
                ).status_code
                == 401
            )


def test_login_rate_limit(monkeypatch):
    from app.api.routers.auth import limiter

    limiter.reset()
    monkeypatch.setattr(
        settings, "sentinelops_password_hash", SecretStr(hasher.hash("test-password"))
    )
    try:
        with TestClient(app) as client:
            for _ in range(10):
                assert (
                    client.post(
                        "/api/v1/auth/login",
                        data={"username": "operator", "password": "wrong"},
                    ).status_code
                    == 401
                )
            assert (
                client.post(
                    "/api/v1/auth/login",
                    data={"username": "operator", "password": "wrong"},
                ).status_code
                == 429
            )
    finally:
        limiter.reset()
