import os
from app.services.telemetry import readings
from fastapi import APIRouter, Query, BackgroundTasks
from app.services.recovery import execute
from app.schemas.incidents import Audit, Decision, Incident, Summary
from app.seed import METRICS, LATENCY_MS, TIMES
from app.services.incidents import IncidentStore

router = APIRouter()
from app.db.database import get_db
from fastapi import Depends
from app.api.dependencies import current_user
from app.db.repository import DatabaseIncidents

store = IncidentStore()


async def repository(session=Depends(get_db)):
    return DatabaseIncidents(session) if session is not None else store


@router.get("/incidents")
async def incidents(repo=Depends(repository)) -> list[Incident]:
    return await repo.list_incidents()


@router.get("/incidents/{id}")
async def detail(id: str, repo=Depends(repository)) -> Incident:
    return await repo.detail(id)


@router.post("/incidents/{id}/approve")
async def approve(
    id: str,
    request: Decision,
    background: BackgroundTasks,
    actor: str = Depends(current_user),
    repo=Depends(repository),
) -> Incident:
    incident = await repo.decide(id, request, True, actor)
    if any(
        a.id == request.action_id and a.operation == "clear_database_fault"
        for a in incident.actions
    ):
        await repo.session.commit()
        background.add_task(execute, id, request.action_id, actor)
    return incident


@router.post("/incidents/{id}/reject")
async def reject(
    id: str,
    request: Decision,
    actor: str = Depends(current_user),
    repo=Depends(repository),
) -> Incident:
    return await repo.decide(id, request, False, actor)


@router.get("/audit-logs")
async def audit(
    limit: int = Query(50, ge=1, le=100), repo=Depends(repository)
) -> list[Audit]:
    return await repo.list_audit(limit)


@router.get("/metrics/summary")
async def summary(repo=Depends(repository)) -> Summary:
    counts = await repo.status_counts()
    resolved = counts.get("Resolved", 0)
    if url := os.getenv("PROMETHEUS_URL"):
        return Summary(
            source="Prometheus",
            active=sum(counts.values()) - resolved,
            resolved=resolved,
            **await readings(url),
        )
    return Summary(
        source="Seeded scenario",
        active=sum(counts.values()) - resolved,
        resolved=resolved,
        metrics=METRICS,
        latency_ms=LATENCY_MS,
        times=TIMES,
    )
