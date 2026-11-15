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


def test_repeat_delivery_and_independent_restoration(tmp_path, monkeypatch):
    import json
    from unittest.mock import AsyncMock
    from app.db.database import get_db
    from app.api.routers import alerts

    secret = tmp_path / "token"
    secret.write_text("test-webhook")
    monkeypatch.setenv("ALERT_TOKEN_FILE", str(secret))
    monkeypatch.setenv("PAYFLOW_INTERNAL_URL", "http://pay")
    monkeypatch.setattr(alerts.recovery, "proposal", AsyncMock(return_value=[]))
    monkeypatch.setattr(alerts.recovery, "client", AsyncMock)
    monkeypatch.setattr(alerts.recovery, "verify", AsyncMock(return_value=True))
    session = AsyncMock()

    async def db():
        yield session

    app.dependency_overrides[get_db] = db
    alert = {
        "fingerprint": "trial",
        "startsAt": "2026-01-01T00:00:00Z",
        "status": "firing",
        "labels": {"alertname": "PayFlowPaymentErrors"},
    }

    def send(client):
        return client.post(
            "/internal/alerts",
            headers={"Authorization": "Bearer test-webhook"},
            json={"alerts": [alert]},
        )

    try:
        with TestClient(app) as client:
            assert send(client).status_code == 200
            row = json.loads(session.execute.await_args.args[1]["record"])
            assert send(client).status_code == 200
            assert (
                json.loads(session.execute.await_args.args[1]["record"])["id"]
                == row["id"]
            )
            alert.update(status="resolved")
            assert send(client).status_code == 422
            alert["endsAt"] = "2026-01-01T02:00:00Z"
            session.scalar.return_value = None
            assert send(client).status_code == 503
            session.scalar.return_value = row
            session.execute.reset_mock()
            assert send(client).status_code == 200
            updated = json.loads(session.execute.await_args_list[0].args[1]["record"])
            assert updated["resolved_at"] != updated["verified_restored_at"]
            assert updated["verified_restored_at"] and updated["status"] == "Resolved"
            session.scalar.return_value = updated
            assert send(client).status_code == 200
            assert session.execute.await_count == 2
    finally:
        app.dependency_overrides.pop(get_db)
