from fastapi import HTTPException
from sqlalchemy import text
from app.schemas.incidents import Audit, Incident
from app.services.incidents import IncidentStore, incident_decision


class DatabaseIncidents:
    """Lock the incident through validation, state transition and audit insertion."""

    def __init__(self, session):
        self.session = session

    async def seed_once(self):
        initial = IncidentStore()
        incident = next(iter(initial.incidents.values()))
        inserted = (
            await self.session.execute(
                text(
                    "INSERT INTO incidents(id,record) VALUES (:id, CAST(:record AS jsonb)) ON CONFLICT DO NOTHING RETURNING id"
                ),
                dict(id=incident.id, record=incident.model_dump_json()),
            )
        ).scalar()
        if inserted:
            await self.append(initial.audit[0])

    async def append(self, event):
        (
            await self.session.execute(
                text(
                    "INSERT INTO audit_events(id,incident_id,record) VALUES (:id,:incident,CAST(:record AS jsonb))"
                ),
                dict(
                    id=event.id,
                    incident=event.incident_id,
                    record=event.model_dump_json(),
                ),
            )
        )

    async def list_incidents(self):
        return [
            Incident.model_validate(r.record)
            for r in (
                await self.session.execute(text("SELECT * FROM incidents ORDER BY id"))
            )
        ]

    async def status_counts(self):
        rows = await self.session.execute(
            text("SELECT status, count(*) FROM incidents GROUP BY status")
        )
        return dict(rows.all())

    async def list_audit(self, limit=50):
        return [
            Audit.model_validate(r)
            for r in (
                await self.session.execute(
                    text(
                        "SELECT record FROM audit_events ORDER BY sequence DESC LIMIT :limit"
                    ),
                    {"limit": limit},
                )
            ).scalars()
        ]

    async def detail(self, id):
        record = (
            await self.session.execute(
                text("SELECT record FROM incidents WHERE id=:id"), dict(id=id)
            )
        ).scalar()
        if record is None:
            raise HTTPException(404, "Unknown incident")
        return Incident.model_validate(record)

    async def save(self, incident):
        await self.session.execute(
            text("UPDATE incidents SET record=CAST(:record AS jsonb) WHERE id=:id"),
            {"id": incident.id, "record": incident.model_dump_json()},
        )

    async def lock(self, id):
        record = await self.session.scalar(
            text("SELECT record FROM incidents WHERE id=:id FOR UPDATE"), {"id": id}
        )
        if record is None:
            raise HTTPException(404, "Unknown incident")
        return Incident.model_validate(record)

    async def decide(self, id, request, approved, actor):
        record = (
            await self.session.execute(
                text("SELECT record FROM incidents WHERE id=:id FOR UPDATE"),
                dict(id=id),
            )
        ).scalar()
        if record is None:
            raise HTTPException(404, "Unknown incident")
        incident = Incident.model_validate(record)
        event = incident_decision(incident, request, approved, actor)
        (
            await self.session.execute(
                text("UPDATE incidents SET record=CAST(:record AS jsonb) WHERE id=:id"),
                dict(id=id, record=incident.model_dump_json()),
            )
        )
        await self.append(event)
        return incident
