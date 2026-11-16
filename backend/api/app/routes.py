import hashlib
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from .alerts import AlertPayload, EvidenceSnapshot, HealthCriteria, IncidentLifecycle
from .schemas import Action, Audit, Decision, Event, Evidence, Incident, Investigation, Summary
from .seed import METRICS
from .service import IncidentStore

router = APIRouter()
from .db import engine
from .repository import DatabaseIncidents

store = DatabaseIncidents(engine) if engine is not None else IncidentStore()
lifecycle = IncidentLifecycle()


class AlertItem(BaseModel):
    status: Literal["firing", "resolved"]
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    startsAt: datetime | None = None
    endsAt: datetime | None = None
    fingerprint: str = ""


class AlertmanagerNotification(BaseModel):
    version: str = "4"
    status: str = "firing"
    alerts: list[AlertItem] = Field(default_factory=list)


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
async def audit(limit: int = Query(50, ge=1, le=100)) -> list[Audit]:
    return store.audit[:limit]


@router.get("/metrics/summary")
async def summary() -> Summary:
    resolved = sum(i.status == "Resolved" for i in store.incidents.values())
    if url := os.getenv("PROMETHEUS_URL"):
        from .services.telemetry import readings
        return Summary(
            source="Prometheus",
            active=len(store.incidents) - resolved,
            resolved=resolved,
            **await readings(url),
        )
    return Summary(
        source="Seeded scenario",
        active=len(store.incidents) - resolved,
        resolved=resolved,
        metrics=METRICS,
        latency_ms=[180, 210, 195, 260, 480, 930, 1470, 2110, 3070, 3850, 4200],
        times=[f"10:{i:02}" for i in range(20, 31)],
    )


# ── Alert receiver and incident lifecycle ────────────────────────────────

@router.post("/internal/alerts", include_in_schema=False)
async def internal_alerts(
    payload: AlertmanagerNotification,
    authorization: str = Header(default=""),
) -> dict:
    path = os.getenv("ALERT_TOKEN_FILE")
    if path and Path(path).exists():
        expected = Path(path).read_text().strip()
        if expected and not (
            authorization and secrets.compare_digest(
                authorization.encode(), ("Bearer " + expected).encode()
            )
        ):
            raise HTTPException(401, "Invalid webhook credential")

    now = datetime.now(UTC)
    for alert in payload.alerts:
        alertname = alert.labels.get("alertname", "PayFlowPaymentErrors")
        fp = alert.fingerprint or f"{alertname}:PayFlow"
        starts_at = alert.startsAt or now
        episode_key = fp + starts_at.astimezone(UTC).isoformat()
        incident_id = "ALT-" + hashlib.sha256(episode_key.encode()).hexdigest()[:24]

        # Register with lifecycle state machine
        lifecycle.receive_alert(
            AlertPayload(
                status=alert.status,
                alertname=alertname,
                service="PayFlow",
                fingerprint=fp,
                started_at=starts_at,
                ended_at=alert.endsAt,
                evidence=EvidenceSnapshot(source="prometheus"),
            )
        )

        if alert.status == "firing":
            try:
                incident = store.get(incident_id)
            except HTTPException:
                incident = None

            if incident is None:
                incident = Incident(
                    id=incident_id,
                    title="PayFlow payment errors" if alertname == "PayFlowPaymentErrors" else "PayFlow payment latency",
                    service="PayFlow",
                    severity="Critical",
                    status="Investigating",
                    detected_at=now,
                    evidence_source="prometheus",
                    timeline=[
                        Event(time=now, kind="Detection", title=f"Alertmanager fired {alertname}")
                    ],
                    investigation=Investigation(
                        hypothesis="PayFlow payment errors detected by Prometheus alert rule.",
                        confidence="Confirmed via live telemetry",
                        alternatives=[],
                        missing=[],
                        evidence=[
                            Evidence(
                                kind="Alert",
                                detail=f"Prometheus rule {alertname} fired for PayFlow.",
                                reference="prometheus",
                            )
                        ],
                        next_steps=["Inspect PayFlow logs and recent transactions."],
                        runbooks=["Deployment rollback review"],
                    ),
                    actions=[
                        Action(
                            id="ACT-001",
                            operation="rollback",
                            description="Roll back PayFlow deployment",
                            risk="Low",
                            reason="PayFlow payment failure rate exceeded threshold.",
                            requested_at=now,
                        )
                    ],
                )
            incident.status = "Investigating"
            store.save(incident)

        elif alert.status == "resolved":
            try:
                incident = store.get(incident_id)
                incident.resolved_at = alert.endsAt or now
                incident.status = "Resolved"
                incident.timeline.append(
                    Event(time=now, kind="Resolution", title="Alertmanager reported resolution")
                )
                store.save(incident)
            except HTTPException:
                pass

    return {"status": "accepted"}


@router.post("/alerts/receive")
async def receive_alert(payload: AlertPayload) -> dict:
    """Direct alert receiver endpoint."""
    episode = lifecycle.receive_alert(payload)
    return {"episode_id": episode.id, "status": episode.status.value}


@router.get("/episodes")
async def list_episodes() -> list:
    return [ep.model_dump() for ep in lifecycle.list_episodes()]


@router.get("/episodes/{episode_id}")
async def get_episode(episode_id: str) -> dict:
    ep = lifecycle.get_episode(episode_id)
    if ep is None:
        raise HTTPException(404, "Unknown episode")
    return ep.model_dump()


@router.post("/episodes/{episode_id}/verify")
async def verify_episode(episode_id: str, evidence: EvidenceSnapshot) -> dict:
    try:
        ep = lifecycle.verify_recovery(episode_id, evidence)
    except KeyError:
        raise HTTPException(404, "Unknown episode")
    return ep.model_dump()


@router.post("/incidents/{incident_id}/verify")
async def verify_incident(incident_id: str, evidence: EvidenceSnapshot) -> Incident:
    incident = store.get(incident_id)
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
        store.save(incident)
    return incident
