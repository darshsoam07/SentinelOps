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


class Incident(BaseModel):
    id: str
    title: str
    severity: str
    service: str
    status: str
    detected_at: datetime
    resolved_at: datetime | None = None
    verified_restored_at: datetime | None = None
    evidence_source: str = "none"
    investigation: Investigation
    timeline: list[Event]
    actions: list[Action]


class EvidenceSnapshot(BaseModel):
    source: str = "prometheus"
    submissions_total: int = 0
    failures_total: int = 0
    latency_p95_s: float | None = None


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


class User(BaseModel):
    username: str


class AccessToken(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
