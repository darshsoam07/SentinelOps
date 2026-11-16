import os
from app.services.telemetry import readings
from fastapi import APIRouter, Query
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
    actor: str = Depends(current_user),
    repo=Depends(repository),
) -> Incident:
    return await repo.decide(id, request, True, actor)


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
        return Summary(source="Prometheus", active=sum(counts.values()) - resolved, resolved=resolved, **await readings(url))
    return Summary(
        source="Seeded scenario",
        active=sum(counts.values()) - resolved,
        resolved=resolved,
        metrics=METRICS,
        latency_ms=LATENCY_MS,
        times=TIMES,
    )
