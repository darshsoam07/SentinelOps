import time
from uuid import uuid4
import pytest

payload = {"amount": 500, "currency": "INR"}


def test_round_trip(client):
    assert client.get("/health").json()["status"] == "ok"
    response = client.post("/payments", json=payload)
    assert response.status_code == 201
    payment = response.json()
    assert payment["status"] == "SUCCESS"
    assert client.get("/payments/" + payment["id"]).json() == payment
    assert client.get("/payments").json() == [payment]
    assert client.get("/payments/" + str(uuid4())).status_code == 404


@pytest.mark.parametrize(
    "field,value",
    [("amount", 0), ("amount", -1), ("currency", "IN"), ("currency", "usd")],
)
def test_invalid(client, field, value):
    assert client.post("/payments", json={**payload, field: value}).status_code == 422


@pytest.mark.parametrize(
    "fault,expected",
    [("high_latency", 201), ("high_error_rate", 500), ("database_unavailable", 503)],
)
def test_fault(client, fault, expected):
    for enabled in [True, False]:
        assert (
            client.post(
                "/simulation/faults", json={"fault": fault, "enabled": enabled}
            ).json()[fault]
            == enabled
        )
        assert client.get("/simulation/faults").json()[fault] == enabled
        start = time.monotonic()
        response = client.post("/payments", json=payload)
        assert response.status_code == (expected if enabled else 201)
        if fault == "high_latency" and enabled:
            assert time.monotonic() - start >= 0.8
        if fault == "high_error_rate" and enabled:
            assert client.post("/payments", json=payload).status_code == 201


def test_bounded_recent_payments(client):
    for amount in range(1, 5):
        assert (
            client.post(
                "/payments", json={"amount": amount, "currency": "USD"}
            ).status_code
            == 201
        )
    assert [p["amount"] for p in client.get("/payments?limit=2").json()] == [4, 3]
    assert client.get("/payments?limit=101").status_code == 422
    assert client.get("/ready").json()["storage"] == "memory"
    assert "http_requests_total" in client.get("/metrics").text


def test_receipt_metrics_use_route_template(client):
    from uuid import uuid4

    unknown = str(uuid4())
    assert client.get("/api/v1/payments/" + unknown).status_code == 404
    metrics = client.get("/metrics").text
    assert 'route="/payments/{id}"' in metrics
    assert unknown not in metrics
    assert "http_request_duration_seconds_bucket" in metrics


def test_recovery_rejects_old_generation(client, monkeypatch):
    monkeypatch.setenv("RECOVERY_TOKEN", "test-scope")
    headers = {"Authorization": "Bearer test-scope"}
    path = "/internal/recovery/database-fault"
    assert client.get(path).status_code == 401
    for enabled in [True, False, True]:
        client.post(
            "/simulation/faults",
            json={"fault": "database_unavailable", "enabled": enabled},
        ).raise_for_status()
        if enabled:
            current = client.get(path, headers=headers).json()["generation"]
            if "first" not in locals():
                first = current
    assert client.post(f"{path}/{first}/clear", headers=headers).status_code == 409
    assert client.post(f"{path}/{current}/clear", headers=headers).status_code == 200
    assert client.post(f"{path}/{current}/clear", headers=headers).status_code == 409
