import time
from itertools import islice
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from app.api.dependencies import current_user
from app.db.database import get_db
from app.db.repository import PaymentRepository
from app.metrics import PaymentMetrics
from app.schemas.payments import FaultChange, Faults, Payment, PaymentInput
from app.services.payments import PaymentStore

router = APIRouter()
metrics = PaymentMetrics()
store = PaymentStore()


@router.post(
    "/payments",
    status_code=201,
    responses={500: {"model": Payment}, 503: {"model": Payment}},
)
async def create_payment(
    request: PaymentInput, response: Response, session=Depends(get_db)
) -> Payment:
    start = time.monotonic()
    payment, response.status_code = await store.create(
        request, PaymentRepository(session) if session else None
    )
    metrics.record(status_code=response.status_code, duration_s=time.monotonic() - start)
    return payment


@router.post(
    "/submit",
    status_code=201,
    responses={500: {"model": Payment}, 503: {"model": Payment}},
)
async def submit_payment(
    request: PaymentInput, response: Response, session=Depends(get_db)
) -> Payment:
    start = time.monotonic()
    payment, response.status_code = await store.create(
        request, PaymentRepository(session) if session else None
    )
    metrics.record(status_code=response.status_code, duration_s=time.monotonic() - start)
    return payment


@router.get("/payments")
async def payments(
    limit: int = Query(50, ge=1, le=100), session=Depends(get_db)
) -> list[Payment]:
    return (
        await PaymentRepository(session).recent(limit)
        if session
        else list(islice(reversed(store.records.values()), limit))
    )


@router.get("/payments/{id}")
async def lookup(id: UUID, session=Depends(get_db)) -> Payment:
    payment = (
        await PaymentRepository(session).get(id) if session else store.records.get(id)
    )
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
