from fastapi.testclient import TestClient
from app.main import app


def test_webhook_requires_its_own_secret(tmp_path, monkeypatch):
    secret = tmp_path / "webhook"
    secret.write_text("alertmanager-test-token")
    monkeypatch.setenv("ALERT_TOKEN_FILE", str(secret))
    with TestClient(app) as client:
        for headers in ({}, {"Authorization": "Bearer wrong"}):
            assert (
                client.post(
                    "/internal/alerts", json={"alerts": []}, headers=headers
                ).status_code
                == 401
            )
