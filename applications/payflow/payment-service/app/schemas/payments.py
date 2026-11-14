from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class PaymentInput(BaseModel):
    amount: float = Field(gt=0, allow_inf_nan=False)
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class Payment(PaymentInput):
    id: UUID
    created_at: datetime
    status: Literal["SUCCESS", "FAILED"]
    reason: str | None = None


class Faults(BaseModel):
    high_latency: bool = False
    high_error_rate: bool = False
    database_unavailable: bool = False


class FaultChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fault: Literal["high_latency", "high_error_rate", "database_unavailable"]
    enabled: bool
