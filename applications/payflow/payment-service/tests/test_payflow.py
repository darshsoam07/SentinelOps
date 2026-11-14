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
