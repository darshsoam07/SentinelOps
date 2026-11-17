from datetime import UTC, datetime
from uuid import uuid4
from fastapi import HTTPException
from app.schemas.incidents import Audit, Decision, Event, Incident
from app.seed import seed, stamp

ALLOWLIST = {"restart", "rollback", "scale"}


class IncidentStore:
    """Decision transitions are synchronous within the single API event loop."""

    def __init__(self):
        incident = seed()
        self.incidents = {incident.id: incident}
        self.audit = [
            Audit(
                id="EVT-001",
                incident_id=incident.id,
                action="Recommendations requested",
                actor="Demo policy",
                time=stamp(32),
                decision="Pending",
                execution="Unexecuted",
            )
        ]

    def get(self, id: str) -> Incident:
        if id not in self.incidents:
            raise HTTPException(404, "Unknown incident")
        return self.incidents[id]

    async def list_incidents(self):
        return list(self.incidents.values())

    async def status_counts(self):
        from collections import Counter

        return Counter(i.status for i in self.incidents.values())

    async def list_audit(self, limit=50):
        return self.audit[:limit]

    async def detail(self, id):
        return self.get(id)

    async def decide(
        self, id: str, request: Decision, approved: bool, actor: str
    ) -> Incident:
        incident = self.get(id)
        self.audit.insert(0, incident_decision(incident, request, approved, actor))
        return incident

    def save(self, incident: Incident):
        self.incidents[incident.id] = incident


def incident_decision(
    incident: Incident, request: Decision, approved: bool, actor: str
) -> Audit:
    action = next((a for a in incident.actions if a.id == request.action_id), None)
    if action is None:
        raise HTTPException(404, "Unknown action for incident")
    if action.operation not in ALLOWLIST:
        raise HTTPException(403, "Operation outside policy")
    if incident.status != "Investigating" or action.status != "Pending":
        raise HTTPException(409, "Incident or action no longer permits a decision")
    action.status = "Approved" if approved else "Rejected"
    # Preserve event order even on machines whose clock predates the scenario.
    time = max(datetime.now(UTC), incident.timeline[-1].time)
    incident.timeline.append(
        Event(time=time, kind="Approval", title=f"{action.id} {action.status.lower()}")
    )
    return Audit(
        id=str(uuid4()),
        incident_id=incident.id,
        action=action.id,
        actor=actor,
        time=time,
        decision=action.status,
        execution="Unexecuted",
        note=request.note,
    )
