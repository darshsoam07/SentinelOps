import time
from uuid import UUID
from fastapi import APIRouter, HTTPException, Response
from .schemas import FaultChange, Faults, Payment, PaymentInput
from .service import PaymentStore
from .metrics import PaymentMetrics

router = APIRouter()
from .db import engine
from .repository import PaymentRepository

metrics = PaymentMetrics()
store = PaymentStore(PaymentRepository(engine) if engine is not None else None)


@router.post(
    "/payments",
    status_code=201,
    responses={500: {"model": Payment}, 503: {"model": Payment}},
)
async def create_payment(request: PaymentInput, response: Response) -> Payment:
    start = time.monotonic()
    payment, response.status_code = await store.create(request)
    metrics.record(status_code=response.status_code, duration_s=time.monotonic() - start)
    return payment


# POST /submit is an alias for POST /payments — both count as submissions.
@router.post(
    "/submit",
    status_code=201,
    responses={500: {"model": Payment}, 503: {"model": Payment}},
)
async def submit_payment(request: PaymentInput, response: Response) -> Payment:
    start = time.monotonic()
    payment, response.status_code = await store.create(request)
    metrics.record(status_code=response.status_code, duration_s=time.monotonic() - start)
    return payment


@router.get("/payments")
async def payments() -> list[Payment]:
    return (
        store.repository.recent()
        if store.repository
        else list(reversed(store.records.values()))
    )


@router.get("/payments/{id}")
async def lookup(id: UUID) -> Payment:
    payment = store.repository.get(id) if store.repository else store.records.get(id)
    if payment is None:
        raise HTTPException(404, "Unknown payment")
    return payment


@router.get("/simulation/faults")
async def faults() -> Faults:
    return store.faults


@router.post("/simulation/faults")
async def change_fault(change: FaultChange) -> Faults:
    return store.change(change)


@router.get("/metrics/payments")
async def payment_metrics() -> dict:
    """Submission metrics snapshot. Reads are excluded."""
    return metrics.snapshot()
