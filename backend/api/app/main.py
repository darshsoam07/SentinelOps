import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .api.dependencies import current_user
from .api.routers.auth import router as auth_router, limiter
from .routes import router
from . import routes
from .repository import DatabaseIncidents
from .db import engine
from sentinelops_common.observability import instrument


@asynccontextmanager
async def lifespan(app):
    if isinstance(routes.store, DatabaseIncidents):
        routes.store.seed_once()
    yield


app = FastAPI(lifespan=lifespan, title="SentinelOps")
instrument(app, engine)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("DASHBOARD_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(
    router, prefix="/api/v1", tags=["Incidents"], dependencies=[Depends(current_user)]
)
app.include_router(
    router, include_in_schema=False, dependencies=[Depends(current_user)]
)
app.include_router(auth_router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
