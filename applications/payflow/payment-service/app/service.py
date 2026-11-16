import asyncio
from datetime import UTC, datetime
from uuid import uuid4
from .schemas import FaultChange, Faults, Payment, PaymentInput


class PaymentStore:
    """Single-event-loop repository. Each request uses the fault snapshot at arrival."""

    def __init__(self, repository=None):
        self.repository = repository
        self.records = {}
        self.faults = Faults()
        self.error_attempts = 0

    def change(self, change: FaultChange) -> Faults:
        if (
            change.fault == "high_error_rate"
            and change.enabled != self.faults.high_error_rate
        ):
            self.error_attempts = 0
        setattr(self.faults, change.fault, change.enabled)
        return self.faults

    async def create(self, request: PaymentInput) -> tuple[Payment, int]:
        faults = self.faults.model_copy()
        reason, code = None, 201
        if faults.database_unavailable:
            reason, code = "Simulated database outage", 503
        elif faults.high_error_rate:
            self.error_attempts += 1
            if self.error_attempts % 2:
                reason, code = "Simulated processing error", 500
        if faults.high_latency:
            await asyncio.sleep(0.82)
        payment = Payment(
            **request.model_dump(),
            id=uuid4(),
            created_at=datetime.now(UTC),
            status="FAILED" if reason else "SUCCESS",
            reason=reason,
        )
        if self.repository is not None:
            self.repository.insert(payment)
        else:
            self.records[payment.id] = payment
        return payment, code
