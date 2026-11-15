import asyncio
import math
from datetime import UTC, datetime
import httpx
from fastapi import HTTPException

RATE = 'sum(rate(http_requests_total{job="payflow",route="/api/v1/payments"}[1m]))'
ERRORS = 'sum(rate(http_requests_total{job="payflow",route="/api/v1/payments",status=~"5.."}[1m]))'
P95 = 'histogram_quantile(0.95,sum by(le)(rate(http_request_duration_seconds_bucket{job="payflow",route="/api/v1/payments"}[1m])))'


async def readings(url):
    now = int(datetime.now(UTC).timestamp())
    async with httpx.AsyncClient(base_url=url, timeout=3) as client:

        async def query(path, **params):
            response = await client.get("/api/v1/" + path, params=params)
            response.raise_for_status()
            return response.json()["data"]["result"]

        try:
            rate, errors, series = await asyncio.gather(
                query("query", query=RATE),
                query("query", query=ERRORS),
                query("query_range", query=P95, start=now - 300, end=now, step=5),
            )
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise HTTPException(503, "Prometheus readings unavailable") from exc
    points = [
        (t, round(float(v) * 1000))
        for t, v in (series[0]["values"] if series else [])
        if math.isfinite(float(v))
    ]
    metrics = [
        {
            "name": name,
            "value": format(float(result[0]["value"][1]), ".2f") + " /s"
            if result
            else "—",
        }
        for name, result in [("Request rate", rate), ("Server error rate", errors)]
    ]
    metrics.append(
        {"name": "p95 latency", "value": f"{points[-1][1]} ms" if points else "—"}
    )
    return dict(
        metrics=metrics,
        latency_ms=[v for _, v in points],
        times=[datetime.fromtimestamp(t, UTC).strftime("%H:%M:%S") for t, _ in points],
    )
