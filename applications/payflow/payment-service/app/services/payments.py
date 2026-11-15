import asyncio
from datetime import UTC, datetime
from uuid import uuid4
from app.schemas.payments import FaultChange, Faults, Payment, PaymentInput


class PaymentStore:
    """Single-event-loop repository. Each request uses the fault snapshot at arrival."""

    def __init__(self):
        self.database_generation = None
        self.records = {}
        self.faults = Faults()
        self.error_attempts = 0

    def change(self, change: FaultChange) -> Faults:
        if (
            change.fault == "high_error_rate"
            and change.enabled != self.faults.high_error_rate
        ):
            self.error_attempts = 0
        if (
            change.fault == "database_unavailable"
            and self.faults.database_unavailable != change.enabled
        ):
            self.database_generation = uuid4() if change.enabled else None
        setattr(self.faults, change.fault, change.enabled)
        return self.faults

    async def create(
        self, request: PaymentInput, repository=None
    ) -> tuple[Payment, int]:
        faults = self.faults.model_copy()
        reason, code = None, 201
        if faults.database_unavailable:
            reason, code = "Simulated database outage", 503
        elif faults.high_error_rate:
            self.error_attempts += 1
            if self.error_attempts % 2:
                reason, code = "Simulated processing error", 500
        if faults.high_latency:
            await asyncio.sleep(0.8)
        payment = Payment(
            **request.model_dump(),
            id=uuid4(),
            created_at=datetime.now(UTC),
            status="FAILED" if reason else "SUCCESS",
            reason=reason,
        )
        if repository is not None:
            await repository.insert(payment)
        else:
            self.records[payment.id] = payment
        return payment, code
