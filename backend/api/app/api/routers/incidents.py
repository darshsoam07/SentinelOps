import os
from app.services.telemetry import readings
from fastapi import APIRouter, Depends, Query
from app.api.dependencies import current_user
from datetime import UTC, datetime
from app.schemas.incidents import Audit, Decision, Event, EvidenceSnapshot, Incident, Summary
from app.seed import METRICS, LATENCY_MS, TIMES
from app.services.incidents import IncidentStore

router = APIRouter()
from app.db.database import engine
from app.db.repository import DatabaseIncidents
from app.services.incidents import IncidentStore

store = DatabaseIncidents(engine) if engine is not None else IncidentStore()


def repository():
    return store


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


@router.post("/incidents/{id}/verify")
async def verify_incident(
    id: str,
    evidence: EvidenceSnapshot,
    repo=Depends(repository),
) -> Incident:
    if hasattr(repo, "detail"):
        incident = await repo.detail(id)
    else:
        incident = repo.get(id)
    now = datetime.now(UTC)

    # Verification criteria: at least 5 submissions, 0 server errors, p95 <= 2.0s
    if (
        evidence.submissions_total >= 5
        and evidence.failures_total == 0
        and (evidence.latency_p95_s is None or evidence.latency_p95_s <= 2.0)
    ):
        incident.verified_restored_at = now
        incident.status = "Resolved"
        incident.evidence_source = evidence.source
        incident.timeline.append(
            Event(time=now, kind="Verification", title="Recovery verified with healthy traffic")
        )
        if hasattr(repo, "save"):
            res = repo.save(incident)
            if hasattr(res, "__await__"):
                await res
    return incident
