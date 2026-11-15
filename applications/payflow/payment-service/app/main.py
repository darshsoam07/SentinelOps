from contextlib import asynccontextmanager
from sentinelops_common.observability import instrument
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.dependencies import current_user
from app.api.routers.payments import router
from app.db.database import engine, sessions


@asynccontextmanager
async def lifespan(app):
    yield
    if engine:
        await engine.dispose()


app = FastAPI(title="PayFlow", lifespan=lifespan)
from app.api.routers.recovery import router as recovery_router

app.include_router(recovery_router)
instrument(app, engine)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.dashboard_origins.split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(
    router, prefix="/api/v1", tags=["Payments"], dependencies=[Depends(current_user)]
)
app.include_router(
    router, include_in_schema=False, dependencies=[Depends(current_user)]
)


@app.get("/health")
async def health():
    return {"status": "ok"}
