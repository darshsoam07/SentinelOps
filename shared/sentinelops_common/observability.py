from time import perf_counter
from fastapi import HTTPException, Response
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


def instrument(app, engine):
    registry = CollectorRegistry()
    requests = Counter(
        "http_requests",
        "Completed HTTP requests",
        ["route", "status"],
        registry=registry,
    )

    duration = Histogram(
        "http_request_duration_seconds",
        "Time to response headers",
        ["route"],
        registry=registry,
    )

    @app.middleware("http")
    async def measure(request, call_next):
        start = perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route = getattr(request.scope.get("route"), "path", "unmatched")
            requests.labels(route, str(status)).inc()
            duration.labels(route).observe(perf_counter() - start)

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
