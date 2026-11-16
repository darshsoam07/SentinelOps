import pytest
from app import routes

path = "/incidents/SNT-001"


def test_reads(client):
    assert client.get("/health").status_code == 200
    incident = client.get(path).json()
    assert incident == client.get("/incidents").json()[0]
    assert incident["severity"] == "Critical"
    assert client.get("/incidents/unknown").status_code == 404
    summary = client.get("/metrics/summary").json()
    assert summary["active"] == 1 and len(summary["metrics"]) == 7


@pytest.mark.parametrize(
    "decision,status", [("approve", "Approved"), ("reject", "Rejected")]
)
def test_decision(client, decision, status):
    request = {"action_id": "ACT-001", "note": "Reviewed evidence"}
    response = client.post(path + "/" + decision, json=request)
    assert response.status_code == 200
    assert response.json()["actions"][0]["status"] == status
    assert response.json()["timeline"][-1]["kind"] == "Approval"
    audit = client.get("/audit-logs").json()
    assert audit[0]["decision"] == status and audit[0]["note"] == request["note"]
    assert audit[0]["execution"] == "Unexecuted"
    assert client.post(path + "/approve", json=request).status_code == 409
    assert client.get("/audit-logs").json() == audit


def test_policy(client):
    assert (
        client.post(path + "/approve", json={"action_id": "wrong"}).status_code == 404
    )
    incident = routes.store.get("SNT-001")
    incident.actions[0].operation = "unknown"
    assert (
        client.post(path + "/approve", json={"action_id": "ACT-001"}).status_code == 403
    )
    incident.status = "Resolved"
    assert (
        client.post(path + "/reject", json={"action_id": "ACT-002"}).status_code == 409
    )


def test_audit_limit_and_note(client):
    result = client.post(
        "/incidents/SNT-001/approve", json={"action_id": "ACT-001", "note": "Reviewed"}
    )
    assert result.status_code == 200
    audit = client.get("/audit-logs?limit=1").json()
    assert len(audit) == 1
    assert audit[0]["note"] == "Reviewed"
    assert client.get("/audit-logs?limit=0").status_code == 422
