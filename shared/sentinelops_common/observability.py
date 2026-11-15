from fastapi import HTTPException, Response
from prometheus_client import (
    CollectorRegistry,
    Counter,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


def instrument(app, engine):
    registry = CollectorRegistry()
    requests = Counter(
        "http_requests", "Completed HTTP requests", ["status"], registry=registry
    )

    @app.middleware("http")
    async def measure(request, call_next):
        try:
            response = await call_next(request)
        except Exception:
            requests.labels("500").inc()
            raise
        requests.labels(str(response.status_code)).inc()
        return response

    @app.get("/ready")
    async def ready():
        if engine is not None:
            try:
                async with engine.connect() as connection:
                    await connection.execute(text("SELECT 1"))
            except (SQLAlchemyError, OSError, TimeoutError):
                raise HTTPException(503, "Database unavailable")
        return {
            "status": "ready",
            "storage": "postgresql" if engine is not None else "memory",
        }

    @app.get("/metrics")
    async def metrics():
        return Response(
            generate_latest(registry), headers={"Content-Type": CONTENT_TYPE_LATEST}
        )
