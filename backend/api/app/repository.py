from fastapi import HTTPException
from sqlalchemy import text
from .schemas import Audit, Incident
from .service import IncidentStore, incident_decision


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

    def get(self, id):
        with self.engine.connect() as conn:
            record = conn.execute(
                text("SELECT record FROM incidents WHERE id=:id"), dict(id=id)
            ).scalar()
            if record is None:
                raise HTTPException(404, "Unknown incident")
            return Incident.model_validate(record)

    def decide(self, id, request, approved):
        with self.engine.begin() as conn:
            record = conn.execute(
                text("SELECT record FROM incidents WHERE id=:id FOR UPDATE"),
                dict(id=id),
            ).scalar()
            if record is None:
                raise HTTPException(404, "Unknown incident")
            incident = Incident.model_validate(record)
            event = incident_decision(incident, request, approved)
            conn.execute(
                text("UPDATE incidents SET record=CAST(:record AS jsonb) WHERE id=:id"),
                dict(id=id, record=incident.model_dump_json()),
            )
            self.append(conn, event)
            return incident
