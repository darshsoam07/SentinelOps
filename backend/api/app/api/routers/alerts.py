import hashlib
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.db.database import get_db
from app.schemas.incidents import Event, Incident, Investigation

router = APIRouter()


class Alert(BaseModel):
    fingerprint: str = Field(min_length=1, max_length=128)
    startsAt: datetime
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
    if not path or session is None:
        raise HTTPException(503, "Alert ingestion unavailable")
    expected = Path(path).read_text().strip()
    if not expected or not secrets.compare_digest(
        authorization.encode(), ("Bearer " + expected).encode()
    ):
        raise HTTPException(401, "Invalid webhook credential")
    for alert in payload.alerts:
        if (
            alert.status != "firing"
            or alert.labels.get("alertname") != "PayFlowPaymentErrors"
        ):
            continue
        episode = alert.fingerprint + alert.startsAt.astimezone(UTC).isoformat()
        now = datetime.now(UTC)
        incident = Incident(
            id="ALT-" + hashlib.sha256(episode.encode()).hexdigest()[:24],
            title="PayFlow payment errors",
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
                    title="Alertmanager reported payment errors",
                )
            ],
            investigation=Investigation(
                hypothesis="Payment requests returned server errors.",
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
