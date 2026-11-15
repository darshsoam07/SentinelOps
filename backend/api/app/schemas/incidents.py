from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class Event(BaseModel):
    time: datetime
    kind: str
    title: str


class Evidence(BaseModel):
    kind: str
    detail: str
    reference: str


class Investigation(BaseModel):
    hypothesis: str
    confidence: str
    alternatives: list[str]
    missing: list[str]
    evidence: list[Evidence]
    next_steps: list[str]
    runbooks: list[str]


class Action(BaseModel):
    id: str
    operation: str
    description: str
    risk: str
    reason: str
    requested_at: datetime
    status: Literal["Pending", "Approved", "Rejected"] = "Pending"

    generation: str | None = None
    action_started_at: datetime | None = None
    outcome: Literal["recovered", "persisted", "failed"] | None = None


class Incident(BaseModel):
    id: str
    title: str
    severity: str
    service: str
    status: str
    detected_at: datetime
    resolved_at: datetime | None = None
    verified_restored_at: datetime | None = None
    investigation: Investigation
    timeline: list[Event]
    actions: list[Action]


class Decision(BaseModel):
    action_id: str
    note: str = Field(default="", max_length=500)


class Audit(BaseModel):
    id: str
    incident_id: str
    action: str
    actor: str
    time: datetime
    decision: str
    execution: str
    note: str = ""


class Metric(BaseModel):
    name: str
    value: str


class Summary(BaseModel):
    source: str
    active: int
    resolved: int
    metrics: list[Metric]
    latency_ms: list[int]
    times: list[str]
