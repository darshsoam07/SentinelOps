from fastapi import APIRouter
from app.schemas.incidents import Audit, Decision, Incident, Summary
from app.seed import METRICS
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
async def audit(repo=Depends(repository)) -> list[Audit]:
    return await repo.list_audit()


@router.get("/metrics/summary")
async def summary(repo=Depends(repository)) -> Summary:
    records = await repo.list_incidents()
    resolved = sum(i.status == "Resolved" for i in records)
    return Summary(
        source="Seeded scenario",
        active=len(records) - resolved,
        resolved=resolved,
        metrics=METRICS,
        latency_ms=[180, 210, 195, 260, 480, 930, 1470, 2110, 3070, 3850, 4200],
        times=[f"10:{i:02}" for i in range(20, 31)],
    )
