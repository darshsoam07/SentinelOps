from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.dependencies import current_user
from app.api.routers.incidents import router
from app.db.database import engine, sessions
from app.db.repository import DatabaseIncidents
from app.api.routers.auth import router as auth_router


@asynccontextmanager
async def lifespan(app):
    if sessions:
        async with sessions.begin() as session:
            await DatabaseIncidents(session).seed_once()
    yield
    if engine:
        await engine.dispose()


app = FastAPI(title="SentinelOps", lifespan=lifespan)
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
app.include_router(auth_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
