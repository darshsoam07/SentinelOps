"""Integration tests for alert receiver and episodes via HTTP."""

import pytest
from fastapi.testclient import TestClient
from app import routes
from app.main import app
from app.service import IncidentStore
from app.alerts import IncidentLifecycle


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(routes, "store", IncidentStore())
    monkeypatch.setattr(routes, "lifecycle", IncidentLifecycle())
    from app.api.dependencies import current_user
    app.dependency_overrides[current_user] = lambda: "test-operator"
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(current_user, None)


def test_firing_and_resolved_lifecycle(client):
    """Fire → resolve → verify full lifecycle via HTTP."""
    # Fire an alert
    r = client.post("/alerts/receive", json={
        "status": "firing",
        "alertname": "PaymentFailureRateHigh",
        "service": "PayFlow",
        "fingerprint": "test:http",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "active"
    ep_id = data["episode_id"]

    # List episodes
    r = client.get("/episodes")
    assert r.status_code == 200
    assert len(r.json()) == 1

    # Get episode
    r = client.get(f"/episodes/{ep_id}")
    assert r.status_code == 200
    assert r.json()["status"] == "active"

    # Resolve
    r = client.post("/alerts/receive", json={
        "status": "resolved",
        "alertname": "PaymentFailureRateHigh",
        "service": "PayFlow",
        "fingerprint": "test:http",
    })
    assert r.json()["status"] == "resolving"

    # Verify with healthy evidence
    r = client.post(f"/episodes/{ep_id}/verify", json={
        "source": "prometheus",
        "submissions_total": 10,
        "failures_total": 0,
        "failure_rate": 0.0,
        "latency_p95_s": 0.5,
    })
    assert r.json()["status"] == "verified"


def test_episode_not_found(client):
    assert client.get("/episodes/nonexistent").status_code == 404


def test_seeded_incidents_still_accessible(client):
    """Existing seeded incidents remain accessible alongside episodes."""
    r = client.get("/incidents/SNT-001")
    assert r.status_code == 200
    assert r.json()["severity"] == "Critical"


def test_internal_alerts_webhook(client):
    """Alertmanager webhook delivery: firing -> unverified resolution -> verified."""
    firing_payload = {
        "version": "4",
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {"alertname": "PayFlowPaymentErrors", "job": "payflow", "severity": "high"},
                "fingerprint": "alertmanager-fp-1",
                "startsAt": "2026-11-16T12:00:00Z",
            }
        ],
    }
    r = client.post("/internal/alerts", json=firing_payload)
    assert r.status_code == 200

    # Incident created
    incidents = client.get("/incidents").json()
    new_inc = next((i for i in incidents if i["id"].startswith("ALT-")), None)
    assert new_inc is not None
    assert new_inc["status"] == "Investigating"
    assert new_inc["evidence_source"] == "prometheus"
    inc_id = new_inc["id"]

    # Resolution notification without traffic -> resolved but unverified
    resolved_payload = {
        "version": "4",
        "status": "resolved",
        "alerts": [
            {
                "status": "resolved",
                "labels": {"alertname": "PayFlowPaymentErrors", "job": "payflow"},
                "fingerprint": "alertmanager-fp-1",
                "startsAt": "2026-11-16T12:00:00Z",
                "endsAt": "2026-11-16T12:05:00Z",
            }
        ],
    }
    r = client.post("/internal/alerts", json=resolved_payload)
    assert r.status_code == 200

    inc = client.get(f"/incidents/{inc_id}").json()
    assert inc["status"] == "Resolved"
    assert inc["resolved_at"] is not None
    assert inc["verified_restored_at"] is None  # Unverified while traffic absent!

    # Verify with insufficient traffic (< 5) -> remains unverified
    r = client.post(f"/incidents/{inc_id}/verify", json={
        "source": "prometheus",
        "submissions_total": 2,
        "failures_total": 0,
    })
    assert r.json()["verified_restored_at"] is None

    # Verify with healthy traffic (>= 5 submissions, 0 errors, low latency) -> verified!
    r = client.post(f"/incidents/{inc_id}/verify", json={
        "source": "prometheus",
        "submissions_total": 8,
        "failures_total": 0,
        "latency_p95_s": 0.05,
    })
    verified_inc = r.json()
    assert verified_inc["verified_restored_at"] is not None
    assert verified_inc["evidence_source"] == "prometheus"
    assert any(e["kind"] == "Verification" for e in verified_inc["timeline"])
