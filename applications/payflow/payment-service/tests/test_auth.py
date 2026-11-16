from fastapi.testclient import TestClient
from app.main import app


def test_anonymous_routes():
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        for prefix in ["", "/api/v1"]:
            for path in ["/payments", "/simulation/faults"]:
                assert client.get(prefix + path).status_code == 401
                assert client.post(prefix + path, json={}).status_code == 401
