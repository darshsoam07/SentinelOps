from contextlib import asynccontextmanager
from sentinelops_common.observability import instrument
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.dependencies import current_user
from app.api.routers.incidents import router
from app.db.database import engine
from app.db.repository import DatabaseIncidents
from app.api.routers.auth import router as auth_router, limiter
from app.api.routers.alerts import router as alerts_router
from app import routes
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded


@asynccontextmanager
async def lifespan(app):
    if isinstance(routes.store, DatabaseIncidents):
        routes.store.seed_once()
    yield
    if engine:
        engine.dispose()


app = FastAPI(title="SentinelOps", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
instrument(app, engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.dashboard_origins.split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(
    router, prefix="/api/v1", tags=["Incidents"], dependencies=[Depends(current_user)]
)
app.include_router(
    router, include_in_schema=False, dependencies=[Depends(current_user)]
)
app.include_router(alerts_router)
app.include_router(auth_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
