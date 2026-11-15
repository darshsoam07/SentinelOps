import asyncio
import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx

from app.db.database import sessions
from app.db.repository import DatabaseIncidents
from app.schemas.incidents import Action, Audit


def client():
    return httpx.AsyncClient(
        base_url=os.environ["PAYFLOW_INTERNAL_URL"],
        timeout=3,
        headers={"Authorization": "Bearer " + os.environ["RECOVERY_TOKEN"]},
    )


async def proposal(now):
    if not os.getenv("PAYFLOW_INTERNAL_URL"):
        return []
    try:
        async with client() as pay:
            response = await pay.get("/internal/recovery/database-fault")
            response.raise_for_status()
            generation = response.json()["generation"]
    except (httpx.HTTPError, ValueError, KeyError):
        # Ingestion must still record the alert if PayFlow cannot describe the fault.
        return []
    if generation is None:
        return []
    return [
        Action(
            id="CLEAR-" + str(UUID(generation)),
            operation="clear_database_fault",
            generation=generation,
            description="Clear this injected PayFlow database fault",
            risk="Low",
            reason="PayFlow reports this simulation fault is active.",
            requested_at=now,
        )
    ]


async def verify(pay):
    for attempt in range(3):
        if attempt:
            await asyncio.sleep(2)
        ready = await pay.get("/ready")
        ready.raise_for_status()
        state = await pay.get("/internal/recovery/database-fault")
        state.raise_for_status()
        if (
            ready.json().get("status") != "ready"
            or state.json().get("healthy") is not True
        ):
            return False
    return True


async def update(id, action_id, actor, outcome=None):
    async with sessions.begin() as session:
        repo = DatabaseIncidents(session)
        incident = await repo.lock(id)
        action = next(a for a in incident.actions if a.id == action_id)
        if (
            action.operation != "clear_database_fault"
            or action.status != "Approved"
            or action.outcome
        ):
            return None
        now = datetime.now(UTC)
        if outcome is None:
            if action.action_started_at or incident.status != "Investigating":
                return None
            action.action_started_at = now
        else:
            action.outcome = outcome
            if outcome == "recovered":
                incident.verified_restored_at = now
        await repo.save(incident)
        await repo.append(
            Audit(
                id=str(uuid4()),
                incident_id=id,
                action=action.id,
                actor=actor,
                time=now,
                decision="Approved",
                execution=outcome or "Executing",
            )
        )
        return action.generation


async def execute(id, action_id, actor):
    generation = await update(id, action_id, actor)
    if not generation:
        return
    outcome = "failed"
    try:
        async with client() as pay:
            result = await pay.post(
                f"/internal/recovery/database-fault/{UUID(generation)}/clear"
            )
            result.raise_for_status()
            outcome = "recovered" if await verify(pay) else "persisted"
    except (httpx.HTTPError, ValueError, KeyError):
        pass
    await update(id, action_id, actor, outcome)
