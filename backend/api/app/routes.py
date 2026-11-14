from fastapi import APIRouter
from .schemas import Audit, Decision, Incident, Summary
from .seed import METRICS
from .service import IncidentStore

router = APIRouter()
from .db import engine
from .repository import DatabaseIncidents

store = DatabaseIncidents(engine) if engine is not None else IncidentStore()


@router.get("/incidents")
async def incidents() -> list[Incident]:
    return list(store.incidents.values())


@router.get("/incidents/{id}")
async def detail(id: str) -> Incident:
    return store.get(id)


@router.post("/incidents/{id}/approve")
async def approve(id: str, request: Decision) -> Incident:
    return store.decide(id, request, True)


@router.post("/incidents/{id}/reject")
async def reject(id: str, request: Decision) -> Incident:
    return store.decide(id, request, False)


@router.get("/audit-logs")
async def audit() -> list[Audit]:
    return store.audit


@router.get("/metrics/summary")
async def summary() -> Summary:
    resolved = sum(i.status == "Resolved" for i in store.incidents.values())
    return Summary(
        source="Seeded scenario",
        active=len(store.incidents) - resolved,
        resolved=resolved,
        metrics=METRICS,
        latency_ms=[180, 210, 195, 260, 480, 930, 1470, 2110, 3070, 3850, 4200],
        times=[f"10:{i:02}" for i in range(20, 31)],
    )
