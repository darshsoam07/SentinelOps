from fastapi.testclient import TestClient
from app.main import app


def test_anonymous_routes():
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        for prefix in ["", "/api/v1"]:
            for path in ["/payments", "/simulation/faults"]:
                assert client.get(prefix + path).status_code == 401
                assert client.post(prefix + path, json={}).status_code == 401


def test_public_key_cannot_sign(monkeypatch, tmp_path):
    import jwt
    import pytest
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from app.core.config import settings

    public = Ed25519PrivateKey.generate().public_key()
    path = tmp_path / "public.pem"
    path.write_bytes(
        public.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
    )
    monkeypatch.setattr(settings, "sentinelops_public_key_file", str(path))
    assert "sentinelops_private_key_file" not in type(settings).model_fields
    with pytest.raises((TypeError, AttributeError)):
        jwt.encode({"sub": "operator"}, public, algorithm="EdDSA")
