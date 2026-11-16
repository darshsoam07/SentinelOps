"""Payment submission metrics with bounded cardinality.

An eligible payment submission is a POST to /payments (or /submit).
Success: HTTP 201. Server failure: HTTP 500 or 503.
Reads (GET /payments, GET /payments/{id}) are excluded.
"""

import time
from dataclasses import dataclass, field


@dataclass
class _Histogram:
    """Fixed-bucket histogram for latency observations."""

    count: int = 0
    total: float = 0.0
    buckets: dict[float, int] = field(default_factory=lambda: {
        0.1: 0, 0.25: 0, 0.5: 0, 1.0: 0, 2.5: 0, 5.0: 0, 10.0: 0
    })

    def observe(self, value: float) -> None:
        self.count += 1
        self.total += value
        for bound in self.buckets:
            if value <= bound:
                self.buckets[bound] += 1


@dataclass
class PaymentMetrics:
    """Counters and histogram for payment submission measurement.

    Labels are limited to {status} ∈ {success, error} to keep cardinality
    bounded. The histogram records latency for every submission regardless
    of outcome.
    """

    submissions: int = 0
    failures: int = 0
    latency: _Histogram = field(default_factory=_Histogram)

    def record(self, *, status_code: int, duration_s: float) -> None:
        """Record one payment submission attempt."""
        self.submissions += 1
        if status_code >= 500:
            self.failures += 1
        self.latency.observe(duration_s)

    @property
    def failure_rate(self) -> float:
        """Fraction of submissions that were server failures.

        Returns 0.0 when there are no submissions (zero-traffic).
        """
        if self.submissions == 0:
            return 0.0
        return self.failures / self.submissions

    def snapshot(self) -> dict:
        return {
            "submissions_total": self.submissions,
            "failures_total": self.failures,
            "failure_rate": self.failure_rate,
            "latency_seconds_count": self.latency.count,
            "latency_seconds_sum": round(self.latency.total, 6),
            "latency_seconds_buckets": dict(self.latency.buckets),
        }
