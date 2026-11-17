import hashlib
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app import routes
from app.alerts import AlertPayload, EvidenceSnapshot
from app.schemas.incidents import Action, Event, Evidence, Incident, Investigation

router = APIRouter()


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
        routes.lifecycle.receive_alert(
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
                incident = routes.store.get(incident_id)
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
            routes.store.save(incident)
            from app.api.routers import incidents
            incidents.store.save(incident)

        elif alert.status == "resolved":
            try:
                incident = routes.store.get(incident_id)
                incident.resolved_at = alert.endsAt or now
                incident.status = "Resolved"
                incident.timeline.append(
                    Event(time=now, kind="Resolution", title="Alertmanager reported resolution")
                )
                routes.store.save(incident)
                from app.api.routers import incidents
                incidents.store.save(incident)
            except HTTPException:
                pass

    return {"status": "accepted"}


@router.post("/alerts/receive")
async def receive_alert(payload: AlertPayload) -> dict:
    episode = routes.lifecycle.receive_alert(payload)
    return {"episode_id": episode.id, "status": episode.status.value}


@router.get("/episodes")
async def list_episodes() -> list:
    return [ep.model_dump() for ep in routes.lifecycle.list_episodes()]


@router.get("/episodes/{episode_id}")
async def get_episode(episode_id: str) -> dict:
    ep = routes.lifecycle.get_episode(episode_id)
    if ep is None:
        raise HTTPException(404, "Unknown episode")
    return ep.model_dump()


@router.post("/episodes/{episode_id}/verify")
async def verify_episode(episode_id: str, evidence: EvidenceSnapshot) -> dict:
    try:
        ep = routes.lifecycle.verify_recovery(episode_id, evidence)
    except KeyError:
        raise HTTPException(404, "Unknown episode")
    return ep.model_dump()
