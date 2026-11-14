from datetime import UTC, datetime, timedelta
import secrets
import jwt
from fastapi.testclient import TestClient
from pydantic import SecretStr
from app.api.routers.auth import hasher
from app.core.config import settings
from app.main import app


def test_authentication(monkeypatch):
    key = secrets.token_hex(32)
    password = secrets.token_hex(16)
    monkeypatch.setattr(settings, "sentinelops_jwt_secret", SecretStr(key))
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
            token, key, algorithms=["HS256"], audience="sentinelops-workspace"
        )
        for invalid in (
            jwt.encode(
                {**claims, "exp": datetime.now(UTC) - timedelta(seconds=1)},
                key,
                algorithm="HS256",
            ),
            jwt.encode(claims, secrets.token_hex(32), algorithm="HS256"),
        ):
            assert (
                client.get(
                    "/api/v1/users/me", headers={"Authorization": "Bearer " + invalid}
                ).status_code
                == 401
            )
