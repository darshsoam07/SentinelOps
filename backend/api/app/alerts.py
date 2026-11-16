"""Alert receiver and incident lifecycle management.

Episode identity: fingerprint = f"{alertname}:{service}"
State transitions: firing → active, resolved → resolving → verified | unverified

An incident episode tracks:
  - rule: the alert rule name (e.g. "PaymentFailureRateHigh")
  - service: the affected service
  - timestamps: started_at, resolved_at, verified_at
  - observation_window: (start, end) of the measurement period
  - evidence_source: where the measurement comes from

A missing measurement is explicit: evidence_source="none" when no metrics exist.

State machine:
  - firing delivery → create new episode (or re-fire existing active episode)
  - resolved delivery → mark resolving (alert cleared, not yet verified)
  - verified → enough healthy traffic observed in the health window
  - unverified → resolved without sufficient traffic evidence

Health window criteria:
  - minimum_count: at least N successful submissions
  - latency_p95_threshold_s: p95 latency below threshold
  - Insufficient traffic → unverified
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class EpisodeStatus(str, Enum):
    ACTIVE = "active"
    RESOLVING = "resolving"
    VERIFIED = "verified"
    UNVERIFIED = "unverified"


class EvidenceSnapshot(BaseModel):
    source: str = "none"
    submissions_total: int = 0
    failures_total: int = 0
    failure_rate: float = 0.0
    latency_p95_s: float | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None


class HealthCriteria(BaseModel):
    minimum_count: int = 5
    max_failure_rate: float = 0.05
    latency_p95_threshold_s: float = 2.0


class IncidentEpisode(BaseModel):
    id: str = Field(default_factory=lambda: f"EP-{uuid4().hex[:8]}")
    fingerprint: str
    rule: str
    service: str
    status: EpisodeStatus = EpisodeStatus.ACTIVE
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None
    verified_at: datetime | None = None
    evidence: EvidenceSnapshot = Field(default_factory=EvidenceSnapshot)
    transitions: list[dict] = Field(default_factory=list)


class AlertPayload(BaseModel):
    """Webhook payload from alert delivery."""
    status: str  # "firing" or "resolved"
    alertname: str
    service: str
    fingerprint: str | None = None  # auto-generated if missing
    started_at: datetime | None = None
    ended_at: datetime | None = None
    evidence: EvidenceSnapshot | None = None


class IncidentLifecycle:
    """Manages the incident episode state machine.

    Thread-safe for single event loop (async). For database persistence,
    wrap transitions in a transaction.
    """

    def __init__(self):
        self.episodes: dict[str, IncidentEpisode] = {}
        self._by_fingerprint: dict[str, str] = {}  # fingerprint → episode_id

    def _fingerprint(self, alertname: str, service: str) -> str:
        return f"{alertname}:{service}"

    def _transition(self, episode: IncidentEpisode, new_status: EpisodeStatus,
                    reason: str, timestamp: datetime | None = None) -> None:
        ts = timestamp or datetime.now(UTC)
        episode.transitions.append({
            "from": episode.status.value,
            "to": new_status.value,
            "reason": reason,
            "timestamp": ts.isoformat(),
        })
        episode.status = new_status

    def receive_alert(self, payload: AlertPayload) -> IncidentEpisode:
        """Process an alert delivery (firing or resolved).

        Handles: firing, repeated firing, resolved, repeated resolved,
        delayed events, and new episode with same fingerprint after resolution.
        """
        fp = payload.fingerprint or self._fingerprint(payload.alertname, payload.service)
        ts = payload.started_at or datetime.now(UTC)

        if payload.status == "firing":
            return self._handle_firing(fp, payload, ts)
        elif payload.status == "resolved":
            return self._handle_resolved(fp, payload)
        else:
            raise ValueError(f"Unknown alert status: {payload.status}")

    def _handle_firing(self, fp: str, payload: AlertPayload,
                       ts: datetime) -> IncidentEpisode:
        existing_id = self._by_fingerprint.get(fp)
        if existing_id and existing_id in self.episodes:
            existing = self.episodes[existing_id]
            if existing.status == EpisodeStatus.ACTIVE:
                # Repeated firing — update evidence, no state change
                if payload.evidence:
                    existing.evidence = payload.evidence
                existing.transitions.append({
                    "from": "active", "to": "active",
                    "reason": "repeated firing",
                    "timestamp": ts.isoformat(),
                })
                return existing
            elif existing.status == EpisodeStatus.RESOLVING:
                # Re-fire during resolving — back to active
                self._transition(existing, EpisodeStatus.ACTIVE,
                                "re-fired during resolving", ts)
                if payload.evidence:
                    existing.evidence = payload.evidence
                return existing
            # verified/unverified → new episode

        # New episode
        episode = IncidentEpisode(
            fingerprint=fp,
            rule=payload.alertname,
            service=payload.service,
            started_at=ts,
            evidence=payload.evidence or EvidenceSnapshot(),
        )
        episode.transitions.append({
            "from": "none", "to": "active",
            "reason": "firing",
            "timestamp": ts.isoformat(),
        })
        self.episodes[episode.id] = episode
        self._by_fingerprint[fp] = episode.id
        return episode

    def _handle_resolved(self, fp: str, payload: AlertPayload) -> IncidentEpisode:
        existing_id = self._by_fingerprint.get(fp)
        ts = payload.ended_at or datetime.now(UTC)

        if not existing_id or existing_id not in self.episodes:
            # Delayed resolved for unknown episode — create resolved episode
            episode = IncidentEpisode(
                fingerprint=fp,
                rule=payload.alertname,
                service=payload.service,
                started_at=ts,
                resolved_at=ts,
                status=EpisodeStatus.UNVERIFIED,
                evidence=payload.evidence or EvidenceSnapshot(),
            )
            episode.transitions.append({
                "from": "none", "to": "unverified",
                "reason": "resolved without prior firing record",
                "timestamp": ts.isoformat(),
            })
            self.episodes[episode.id] = episode
            self._by_fingerprint[fp] = episode.id
            return episode

        existing = self.episodes[existing_id]

        if existing.status == EpisodeStatus.ACTIVE:
            existing.resolved_at = ts
            self._transition(existing, EpisodeStatus.RESOLVING,
                            "alert cleared", ts)
            if payload.evidence:
                existing.evidence = payload.evidence
            return existing

        if existing.status == EpisodeStatus.RESOLVING:
            # Repeated resolved — idempotent
            existing.transitions.append({
                "from": "resolving", "to": "resolving",
                "reason": "repeated resolution",
                "timestamp": ts.isoformat(),
            })
            return existing

        # Already verified/unverified — ignore
        return existing

    def verify_recovery(self, episode_id: str,
                        evidence: EvidenceSnapshot,
                        criteria: HealthCriteria | None = None) -> IncidentEpisode:
        """Attempt to verify recovery with health evidence.

        Only transitions from resolving → verified or unverified.
        """
        if episode_id not in self.episodes:
            raise KeyError(f"Unknown episode: {episode_id}")

        episode = self.episodes[episode_id]
        criteria = criteria or HealthCriteria()
        ts = datetime.now(UTC)
        episode.evidence = evidence

        if episode.status != EpisodeStatus.RESOLVING:
            return episode  # no-op for non-resolving episodes

        if evidence.submissions_total < criteria.minimum_count:
            self._transition(episode, EpisodeStatus.UNVERIFIED,
                            f"insufficient traffic ({evidence.submissions_total} < {criteria.minimum_count})",
                            ts)
            return episode

        if evidence.failure_rate > criteria.max_failure_rate:
            self._transition(episode, EpisodeStatus.UNVERIFIED,
                            f"failure rate too high ({evidence.failure_rate:.1%} > {criteria.max_failure_rate:.1%})",
                            ts)
            return episode

        if (evidence.latency_p95_s is not None and
                evidence.latency_p95_s > criteria.latency_p95_threshold_s):
            self._transition(episode, EpisodeStatus.UNVERIFIED,
                            f"latency too high ({evidence.latency_p95_s:.2f}s > {criteria.latency_p95_threshold_s:.2f}s)",
                            ts)
            return episode

        episode.verified_at = ts
        self._transition(episode, EpisodeStatus.VERIFIED,
                        "healthy traffic observed", ts)
        return episode

    def list_episodes(self) -> list[IncidentEpisode]:
        return list(reversed(list(self.episodes.values())))

    def get_episode(self, episode_id: str) -> IncidentEpisode | None:
        return self.episodes.get(episode_id)
