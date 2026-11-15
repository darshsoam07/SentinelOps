import hashlib
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from app.db.repository import DatabaseIncidents
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy import text

from app.db.database import get_db
from app.schemas.incidents import Event, Incident, Investigation, Audit

router = APIRouter()


class Alert(BaseModel):
    fingerprint: str = Field(min_length=1, max_length=128)
    startsAt: AwareDatetime
    endsAt: AwareDatetime | None = None
    status: Literal["firing", "resolved"]
    labels: dict[str, str]


class Notification(BaseModel):
    alerts: list[Alert] = Field(max_length=100)


@router.post("/internal/alerts", include_in_schema=False)
async def receive(
    payload: Notification,
    authorization: str = Header(default=""),
    session=Depends(get_db),
):
    path = os.getenv("ALERT_TOKEN_FILE")
    if not authorization:
        raise HTTPException(401, "Invalid webhook credential")
    if not path:
        raise HTTPException(503, "Alert ingestion unavailable")
    expected = Path(path).read_text().strip()
    if not expected or not secrets.compare_digest(
        authorization.encode(), ("Bearer " + expected).encode()
    ):
        raise HTTPException(401, "Invalid webhook credential")
    if session is None:
        raise HTTPException(503, "Alert storage unavailable")
    for alert in payload.alerts:
        details = {
            "PayFlowPaymentErrors": (
                "PayFlow payment errors",
                "Payment requests returned server errors.",
            ),
            "PayFlowPaymentLatency": (
                "PayFlow payment latency",
                "Payment p95 exceeded 500 ms.",
            ),
        }.get(alert.labels.get("alertname"))
        if details is None:
            continue
        title, observation = details
        episode = alert.fingerprint + alert.startsAt.astimezone(UTC).isoformat()
        now = datetime.now(UTC)
        incident_id = "ALT-" + hashlib.sha256(episode.encode()).hexdigest()[:24]
        if alert.status == "resolved":
            if alert.endsAt is None or alert.endsAt < alert.startsAt:
                raise HTTPException(422, "Invalid alert resolution time")
            row = await session.scalar(
                text("SELECT record FROM incidents WHERE id=:id FOR UPDATE"),
                {"id": incident_id},
            )
            if row is None:
                # Ask Alertmanager to retry if resolution raced the firing transaction.
                raise HTTPException(503, "Firing episode has not been recorded")
            existing = Incident.model_validate(row)
            if existing.resolved_at is None:
                existing.resolved_at = alert.endsAt.astimezone(UTC)
                existing.status = "Resolved"
                existing.timeline.append(
                    Event(
                        time=now,
                        kind="Resolution",
                        title="Alertmanager reported resolution",
                    )
                )
                await session.execute(
                    text(
                        "UPDATE incidents SET record=CAST(:record AS jsonb) WHERE id=:id"
                    ),
                    {"record": existing.model_dump_json(), "id": incident_id},
                )
                await DatabaseIncidents(session).append(
                    Audit(
                        id=str(uuid4()),
                        incident_id=incident_id,
                        action="Alert resolution",
                        actor="Alertmanager",
                        time=now,
                        decision="Resolved",
                        execution="Unverified",
                    )
                )
            continue
        incident = Incident(
            id=incident_id,
            title=title,
            service="PayFlow",
            severity="High",
            status="Investigating",
            detected_at=now,
            resolved_at=None,
            actions=[],
            timeline=[
                Event(
                    time=now,
                    kind="Detection",
                    title=observation,
                )
            ],
            investigation=Investigation(
                hypothesis=observation,
                confidence="Unconfirmed",
                alternatives=[],
                missing=[],
                evidence=[],
                next_steps=["Inspect PayFlow receipts and service metrics."],
                runbooks=[],
            ),
        )
        await session.execute(
            text(
                "INSERT INTO incidents(id,record) VALUES (:id,CAST(:record AS jsonb)) ON CONFLICT(id) DO NOTHING"
            ),
            {"id": incident.id, "record": incident.model_dump_json()},
        )
    return {"status": "accepted"}
