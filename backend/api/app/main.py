import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import router

from contextlib import asynccontextmanager
from . import routes
from .repository import DatabaseIncidents


@asynccontextmanager
async def lifespan(app):
    if isinstance(routes.store, DatabaseIncidents):
        routes.store.seed_once()
    yield


app = FastAPI(lifespan=lifespan, title="SentinelOps")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("DASHBOARD_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
