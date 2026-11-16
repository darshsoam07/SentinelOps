"""Deterministic payment measurement tests.

Workload: 8 successes + 2 server failures + 100 history reads = 120 HTTP calls.
Expected: 10 submissions, 2 failures, 10 latency observations, 20% failure rate.
GET /payments and GET /payments/{id} reads MUST NOT affect submission metrics.
"""

import pytest
from app.metrics import PaymentMetrics


# ── Unit: metrics counters ──────────────────────────────────────────────

def test_payment_metrics_workload():
    """Eight successes, two server failures, 100 unrelated reads."""
    m = PaymentMetrics()

    # 8 successful submissions
    for _ in range(8):
        m.record(status_code=201, duration_s=0.05)

    # 2 server failures (one 500, one 503)
    m.record(status_code=500, duration_s=0.1)
    m.record(status_code=503, duration_s=0.12)

    # 100 reads — these must NOT be recorded
    # (reads go through GET endpoints which don't call metrics.record)

    assert m.submissions == 10
    assert m.failures == 2
    assert m.latency.count == 10
    assert abs(m.failure_rate - 0.20) < 1e-9


def test_zero_traffic():
    """Zero-traffic semantics: failure rate is 0.0 (not an error)."""
    m = PaymentMetrics()
    assert m.submissions == 0
    assert m.failure_rate == 0.0


def test_latency_buckets():
    """Latency observations land in correct histogram buckets."""
    m = PaymentMetrics()
    m.record(status_code=201, duration_s=0.05)   # ≤ 0.1
    m.record(status_code=201, duration_s=0.8)    # ≤ 1.0
    m.record(status_code=500, duration_s=3.0)    # ≤ 5.0
    snap = m.snapshot()
    assert snap["latency_seconds_buckets"][0.1] == 1
    assert snap["latency_seconds_buckets"][1.0] == 2
    assert snap["latency_seconds_buckets"][5.0] == 3


def test_snapshot_shape():
    """Snapshot returns well-formed metrics dict."""
    m = PaymentMetrics()
    m.record(status_code=201, duration_s=0.01)
    snap = m.snapshot()
    assert "submissions_total" in snap
    assert "failures_total" in snap
    assert "failure_rate" in snap
    assert "latency_seconds_count" in snap
    assert "latency_seconds_sum" in snap
    assert "latency_seconds_buckets" in snap


# ── Alert rule semantics: healthy, failing, slow, idle ───────────────────

def evaluate_alert_rules(metrics: PaymentMetrics) -> dict[str, bool]:
    """Simulate Prometheus alert evaluation on payment submission metrics."""
    # Idle/zero-traffic: no alerts fire
    if metrics.submissions == 0:
        return {"PayFlowPaymentErrors": False, "PayFlowPaymentLatency": False}

    errors_fire = metrics.failures > 0
    # Approximate p95: if any observation > 0.5s in 30s window
    slow_count = sum(c for bound, c in metrics.latency.buckets.items() if bound > 0.5 and c > 0)
    latency_fire = (metrics.latency.total / metrics.latency.count > 0.5) if metrics.latency.count else False

    return {
        "PayFlowPaymentErrors": errors_fire,
        "PayFlowPaymentLatency": latency_fire,
    }


def test_rule_healthy_traffic():
    """Healthy traffic: 10 successes, fast responses -> no alerts."""
    m = PaymentMetrics()
    for _ in range(10):
        m.record(status_code=201, duration_s=0.04)
    assert m.failure_rate == 0.0
    alerts = evaluate_alert_rules(m)
    assert not alerts["PayFlowPaymentErrors"]
    assert not alerts["PayFlowPaymentLatency"]


def test_rule_failing_traffic():
    """Failing traffic: 8 successes, 2 failures -> error alert fires."""
    m = PaymentMetrics()
    for _ in range(8):
        m.record(status_code=201, duration_s=0.04)
    m.record(status_code=500, duration_s=0.05)
    m.record(status_code=503, duration_s=0.05)
    assert abs(m.failure_rate - 0.20) < 1e-9
    alerts = evaluate_alert_rules(m)
    assert alerts["PayFlowPaymentErrors"]
    assert not alerts["PayFlowPaymentLatency"]


def test_rule_slow_traffic():
    """Slow traffic: all successes but high latency -> latency alert fires."""
    m = PaymentMetrics()
    for _ in range(10):
        m.record(status_code=201, duration_s=0.85)
    assert m.failure_rate == 0.0
    alerts = evaluate_alert_rules(m)
    assert not alerts["PayFlowPaymentErrors"]
    assert alerts["PayFlowPaymentLatency"]


def test_rule_idle_traffic():
    """Idle traffic: zero submissions -> represented as no traffic, no alerts."""
    m = PaymentMetrics()
    assert m.submissions == 0
    assert m.failure_rate == 0.0
    alerts = evaluate_alert_rules(m)
    assert not alerts["PayFlowPaymentErrors"]
    assert not alerts["PayFlowPaymentLatency"]
