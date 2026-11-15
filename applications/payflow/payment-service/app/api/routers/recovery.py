"""Single fixed fault operation, scoped to the exact injection the operator saw."""

import os
import secrets
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException
from app.api.routers import payments
from app.schemas.payments import FaultChange


def authenticate(authorization: str = Header(default="")):
    token = os.getenv("RECOVERY_TOKEN")
    if not token or not secrets.compare_digest(
        authorization.encode(), ("Bearer " + token).encode()
    ):
        raise HTTPException(401, "Invalid recovery credential")


router = APIRouter(prefix="/internal/recovery", dependencies=[Depends(authenticate)])


@router.get("/database-fault")
async def snapshot():
    store = payments.store
    return {
        "generation": store.database_generation,
        "healthy": not any(store.faults.model_dump().values()),
    }


@router.post("/database-fault/{generation}/clear")
async def clear(generation: UUID):
    store = payments.store
    if generation != store.database_generation or not store.faults.database_unavailable:
        raise HTTPException(409, "Fault generation changed")
    store.change(FaultChange(fault="database_unavailable", enabled=False))
    return {"cleared": True}
