from app.schemas.incidents import (
    Action,
    Event,
    Evidence,
    Incident,
    Investigation,
    Metric,
)


def stamp(minute: int) -> str:
    return f"2026-11-14T10:{minute:02}:00Z"


def seed() -> Incident:
    """Fixed teaching scenario, independent of PayFlow traffic."""
    events = [
        (20, "Deployment", "Payment Service v1.8 deployed"),
        (23, "Alert", "Latency increased"),
        (25, "Alert", "CPU crossed 90%"),
        (26, "Alert", "Connection pool approached capacity"),
        (28, "Alert", "HTTP 500 responses increased"),
        (30, "Detection", "Incident detected"),
        (31, "Investigation", "Seeded investigation generated"),
        (32, "Policy", "Recommendations created"),
    ]
    evidence = [
        (
            "Metrics",
            "CPU 95%, error rate 28%, p95 latency 4.2 s, five pod restarts",
            "metrics/payment-window",
        ),
        ("Logs", "Database connection acquisition timed out", "logs/db-timeout"),
        (
            "Traces",
            "Payment spans spent longer waiting for queries",
            "traces/payment-query",
        ),
        ("Deployment", "Version v1.8 preceded the regression", "deployments/v1.8"),
    ]
    actions = [
        (
            "rollback",
            "Roll back to v1.7",
            "Medium",
            "The latency increase followed deployment.",
        ),
        (
            "restart",
            "Restart unhealthy payment pod",
            "Low",
            "Five restarts indicate an unstable replica.",
        ),
        (
            "scale",
            "Scale payment replicas",
            "High",
            "Additional capacity may relieve CPU pressure but increase database load.",
        ),
    ]
    return Incident(
        id="SNT-001",
        title="Payment Service Performance Regression",
        service="Payment Service",
        severity="Critical",
        status="Investigating",
        detected_at=stamp(30),
        timeline=[Event(time=stamp(m), kind=k, title=t) for m, k, t in events],
        investigation=Investigation(
            hypothesis="Inefficient queries introduced in v1.8 increased CPU use and exhausted database connections.",
            confidence="Moderate (qualitative seeded estimate)",
            alternatives=["Traffic burst", "Database connection leak"],
            missing=[
                "Query plans and pre-deployment connection counts are unavailable."
            ],
            evidence=[Evidence(kind=k, detail=d, reference=r) for k, d, r in evidence],
            next_steps=[
                "Compare query plans across versions.",
                "Inspect pool occupancy and acquisition time.",
            ],
            runbooks=["Connection pool saturation", "Deployment rollback review"],
        ),
        actions=[
            Action(
                id=f"ACT-{i:03}",
                operation=o,
                description=d,
                risk=r,
                reason=w,
                requested_at=stamp(32),
            )
            for i, (o, d, r, w) in enumerate(actions, 1)
        ],
    )


METRICS = [
    Metric(name=k, value=v)
    for k, v in [
        ("MTTD", "10 min"),
        ("MTTR", "N/A"),
        ("Error rate", "28%"),
        ("Availability proxy", "72%"),
        ("p50 latency", "680 ms"),
        ("p95 latency", "4.2 s"),
        ("p99 latency", "5.1 s"),
    ]
]

LATENCY_MS = [180, 210, 195, 260, 480, 930, 1470, 2110, 3070, 3850, 4200]
TIMES = [f"10:{i:02}" for i in range(20, 31)]
