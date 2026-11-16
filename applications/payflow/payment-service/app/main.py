import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sentinelops_common.observability import instrument
from .api.dependencies import current_user
from .routes import router
from .db import engine

app = FastAPI(title="PayFlow")
instrument(app, engine)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("DASHBOARD_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(router, prefix="/api/v1", dependencies=[Depends(current_user)])
app.include_router(router, dependencies=[Depends(current_user)])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
