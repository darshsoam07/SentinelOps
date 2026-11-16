"""Integration test: reads excluded, both POST aliases counted.

Workload over HTTP: 8 successes + 2 server failures via POST /payments
and POST /submit, plus 100 GET reads. Verify the metrics endpoint.
"""

import pytest
from fastapi.testclient import TestClient
from app import routes
from app.main import app
from app.service import PaymentStore
from app.metrics import PaymentMetrics

payload = {"amount": 100, "currency": "USD"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(routes, "store", PaymentStore())
    monkeypatch.setattr(routes, "metrics", PaymentMetrics())
    from app.api.dependencies import current_user
    app.dependency_overrides[current_user] = lambda: "test-operator"
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(current_user, None)


def test_full_workload_with_reads_excluded(client):
    """8 successes + 2 server failures + 100 reads = 10 counted, 20% failure."""
    # Record initial baseline snapshot
    snap0 = client.get("/metrics/payments").json()
    base_submissions = snap0["submissions_total"]
    base_failures = snap0["failures_total"]
    base_latency = snap0["latency_seconds_count"]

    # 4 successes via POST /payments
    ids = []
    for _ in range(4):
        r = client.post("/payments", json=payload)
        assert r.status_code == 201
        ids.append(r.json()["id"])

    # 4 successes via POST /submit (alias) — split evenly across aliases
    for _ in range(4):
        r = client.post("/submit", json=payload)
        assert r.status_code == 201
        ids.append(r.json()["id"])

    # Enable database_unavailable → 1 failure via POST /payments (503)
    client.post("/simulation/faults", json={"fault": "database_unavailable", "enabled": True})
    r = client.post("/payments", json=payload)
    assert r.status_code == 503

    # Switch to high_error_rate → 1 failure via POST /submit (500) — split failures across aliases
    client.post("/simulation/faults", json={"fault": "database_unavailable", "enabled": False})
    client.post("/simulation/faults", json={"fault": "high_error_rate", "enabled": True})
    r = client.post("/submit", json=payload)
    assert r.status_code == 500

    # Clear faults
    client.post("/simulation/faults", json={"fault": "high_error_rate", "enabled": False})

    # 100 reads (50 list + 50 lookup) — none should be counted in payment metrics
    for _ in range(50):
        assert client.get("/payments").status_code == 200
    for pid in ids[:50] if len(ids) >= 50 else ids * 10:
        assert client.get(f"/payments/{pid}").status_code == 200

    # Verify metrics via counter deltas
    snap1 = client.get("/metrics/payments").json()
    delta_submissions = snap1["submissions_total"] - base_submissions
    delta_failures = snap1["failures_total"] - base_failures
    delta_latency = snap1["latency_seconds_count"] - base_latency

    assert delta_submissions == 10, f"Expected 10 submissions, got {delta_submissions}"
    assert delta_failures == 2, f"Expected 2 failures, got {delta_failures}"
    assert delta_latency == 10, f"Expected 10 latency observations, got {delta_latency}"
    assert abs(delta_failures / delta_submissions - 0.20) < 1e-9

    # Idle window: no further submissions during idle period
    # Another 20 reads occur without any submissions
    for _ in range(20):
        assert client.get("/payments").status_code == 200
    snap2 = client.get("/metrics/payments").json()
    assert snap2["submissions_total"] == snap1["submissions_total"]
    assert snap2["failures_total"] == snap1["failures_total"]
