from fastapi import HTTPException
from sqlalchemy import text
from app.schemas.incidents import Audit, Incident
from app.services.incidents import IncidentStore, incident_decision


class DatabaseIncidents:
    """Lock the incident through validation, state transition and audit insertion."""

    def __init__(self, engine):
        self.engine = engine

    def seed_once(self):
        initial = IncidentStore()
        incident = next(iter(initial.incidents.values()))
        with self.engine.begin() as conn:
            inserted = conn.execute(
                text(
                    "INSERT INTO incidents VALUES (:id, CAST(:record AS jsonb)) ON CONFLICT DO NOTHING RETURNING id"
                ),
                dict(id=incident.id, record=incident.model_dump_json()),
            ).scalar()
            if inserted:
                self.append(conn, initial.audit[0])

    def append(self, conn, event):
        conn.execute(
            text(
                "INSERT INTO audit_events(id,incident_id,record) VALUES (:id,:incident,CAST(:record AS jsonb))"
            ),
            dict(
                id=event.id, incident=event.incident_id, record=event.model_dump_json()
            ),
        )

    @property
    def incidents(self):
        with self.engine.connect() as conn:
            return {
                r.id: Incident.model_validate(r.record)
                for r in conn.execute(text("SELECT * FROM incidents ORDER BY id"))
            }

    @property
    def audit(self):
        with self.engine.connect() as conn:
            return [
                Audit.model_validate(r)
                for r in conn.execute(
                    text("SELECT record FROM audit_events ORDER BY sequence DESC")
                ).scalars()
            ]

    async def list_audit(self, limit=50):
        with self.engine.connect() as conn:
            return [
                Audit.model_validate(r)
                for r in conn.execute(
                    text("SELECT record FROM audit_events ORDER BY sequence DESC LIMIT :limit"),
                    {"limit": limit},
                ).scalars()
            ]

    async def list_incidents(self):
        return list(self.incidents.values())

    async def detail(self, id):
        return self.get(id)

    async def status_counts(self):
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT status, count(*) FROM incidents GROUP BY status")
            )
            return dict(rows.all())

    def get(self, id):
        with self.engine.connect() as conn:
            record = conn.execute(
                text("SELECT record FROM incidents WHERE id=:id"), dict(id=id)
            ).scalar()
            if record is None:
                raise HTTPException(404, "Unknown incident")
            return Incident.model_validate(record)

    def save(self, incident: Incident):
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO incidents VALUES (:id, CAST(:record AS jsonb)) ON CONFLICT (id) DO UPDATE SET record=CAST(:record AS jsonb)"
                ),
                dict(id=incident.id, record=incident.model_dump_json()),
            )

    async def decide(self, id, request, approved, actor="operator"):
        return self.decide_sync(id, request, approved, actor)

    def decide_sync(self, id, request, approved, actor="operator"):
        with self.engine.begin() as conn:
            record = conn.execute(
                text("SELECT record FROM incidents WHERE id=:id FOR UPDATE"),
                dict(id=id),
            ).scalar()
            if record is None:
                raise HTTPException(404, "Unknown incident")
            incident = Incident.model_validate(record)
            event = incident_decision(incident, request, approved, actor)
            conn.execute(
                text("UPDATE incidents SET record=CAST(:record AS jsonb) WHERE id=:id"),
                dict(id=id, record=incident.model_dump_json()),
            )
            self.append(conn, event)
            return incident
