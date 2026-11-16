"""Incident lifecycle tests: replay, concurrency, out-of-order, recovery.

Covers:
  - firing → active
  - repeated firing → still active
  - resolved → resolving
  - repeated resolution → still resolving
  - delayed resolved for unknown fingerprint
  - new episode with same fingerprint after verified
  - recovery without traffic → unverified
  - verified recovery with healthy traffic
  - re-firing during resolving → back to active
  - loading old records (list/get)
  - seeded demo still works
"""

import pytest
from datetime import UTC, datetime
from app.alerts import (
    AlertPayload, EvidenceSnapshot, EpisodeStatus, HealthCriteria,
    IncidentLifecycle,
)


@pytest.fixture
def lc():
    return IncidentLifecycle()


def firing(alertname="PaymentFailureRateHigh", service="PayFlow",
           fp=None, evidence=None):
    return AlertPayload(
        status="firing", alertname=alertname, service=service,
        fingerprint=fp, evidence=evidence,
    )


def resolved(alertname="PaymentFailureRateHigh", service="PayFlow",
             fp=None, evidence=None):
    return AlertPayload(
        status="resolved", alertname=alertname, service=service,
        fingerprint=fp, evidence=evidence,
    )


# ── Firing ──────────────────────────────────────────────────────────────

def test_firing_creates_episode(lc):
    ep = lc.receive_alert(firing())
    assert ep.status == EpisodeStatus.ACTIVE
    assert ep.rule == "PaymentFailureRateHigh"
    assert ep.service == "PayFlow"
    assert len(ep.transitions) == 1
    assert ep.transitions[0]["to"] == "active"


def test_repeated_firing_is_idempotent(lc):
    ep1 = lc.receive_alert(firing(fp="test:fp"))
    ep2 = lc.receive_alert(firing(fp="test:fp"))
    assert ep1.id == ep2.id
    assert ep2.status == EpisodeStatus.ACTIVE
    assert len(ep2.transitions) == 2  # initial + repeated


def test_firing_with_evidence(lc):
    ev = EvidenceSnapshot(
        source="prometheus",
        submissions_total=100, failures_total=30, failure_rate=0.3,
    )
    ep = lc.receive_alert(firing(evidence=ev))
    assert ep.evidence.source == "prometheus"
    assert ep.evidence.failure_rate == 0.3


# ── Resolved ────────────────────────────────────────────────────────────

def test_resolved_transitions_to_resolving(lc):
    ep = lc.receive_alert(firing(fp="fp1"))
    ep = lc.receive_alert(resolved(fp="fp1"))
    assert ep.status == EpisodeStatus.RESOLVING
    assert ep.resolved_at is not None


def test_repeated_resolution_is_idempotent(lc):
    lc.receive_alert(firing(fp="fp1"))
    ep1 = lc.receive_alert(resolved(fp="fp1"))
    ep2 = lc.receive_alert(resolved(fp="fp1"))
    assert ep1.id == ep2.id
    assert ep2.status == EpisodeStatus.RESOLVING


def test_delayed_resolved_without_firing(lc):
    ep = lc.receive_alert(resolved(fp="unknown:fp"))
    assert ep.status == EpisodeStatus.UNVERIFIED
    assert "without prior firing" in ep.transitions[0]["reason"]


# ── Re-firing during resolving ──────────────────────────────────────────

def test_refire_during_resolving(lc):
    lc.receive_alert(firing(fp="fp1"))
    lc.receive_alert(resolved(fp="fp1"))
    ep = lc.receive_alert(firing(fp="fp1"))
    assert ep.status == EpisodeStatus.ACTIVE
    assert any(t["reason"] == "re-fired during resolving" for t in ep.transitions)


# ── New episode same fingerprint after resolution ───────────────────────

def test_new_episode_after_verified(lc):
    ep1 = lc.receive_alert(firing(fp="fp1"))
    lc.receive_alert(resolved(fp="fp1"))
    healthy = EvidenceSnapshot(
        source="prometheus",
        submissions_total=10, failures_total=0, failure_rate=0.0,
        latency_p95_s=0.5,
    )
    lc.verify_recovery(ep1.id, healthy)
    assert ep1.status == EpisodeStatus.VERIFIED

    # Same fingerprint → new episode
    ep2 = lc.receive_alert(firing(fp="fp1"))
    assert ep2.id != ep1.id
    assert ep2.status == EpisodeStatus.ACTIVE


# ── Recovery verification ───────────────────────────────────────────────

def test_recovery_without_traffic_is_unverified(lc):
    ep = lc.receive_alert(firing(fp="fp1"))
    lc.receive_alert(resolved(fp="fp1"))
    empty = EvidenceSnapshot(source="prometheus", submissions_total=0)
    lc.verify_recovery(ep.id, empty)
    assert ep.status == EpisodeStatus.UNVERIFIED
    assert "insufficient traffic" in ep.transitions[-1]["reason"]


def test_verified_recovery_with_healthy_traffic(lc):
    ep = lc.receive_alert(firing(fp="fp1"))
    lc.receive_alert(resolved(fp="fp1"))
    healthy = EvidenceSnapshot(
        source="prometheus",
        submissions_total=10, failures_total=0, failure_rate=0.0,
        latency_p95_s=0.5,
    )
    lc.verify_recovery(ep.id, healthy)
    assert ep.status == EpisodeStatus.VERIFIED
    assert ep.verified_at is not None


def test_unverified_when_failure_rate_high(lc):
    ep = lc.receive_alert(firing(fp="fp1"))
    lc.receive_alert(resolved(fp="fp1"))
    bad = EvidenceSnapshot(
        source="prometheus",
        submissions_total=10, failures_total=3, failure_rate=0.3,
        latency_p95_s=0.5,
    )
    lc.verify_recovery(ep.id, bad)
    assert ep.status == EpisodeStatus.UNVERIFIED
    assert "failure rate" in ep.transitions[-1]["reason"]


def test_unverified_when_latency_high(lc):
    ep = lc.receive_alert(firing(fp="fp1"))
    lc.receive_alert(resolved(fp="fp1"))
    slow = EvidenceSnapshot(
        source="prometheus",
        submissions_total=10, failures_total=0, failure_rate=0.0,
        latency_p95_s=5.0,
    )
    lc.verify_recovery(ep.id, slow)
    assert ep.status == EpisodeStatus.UNVERIFIED
    assert "latency" in ep.transitions[-1]["reason"]


# ── Loading old records ─────────────────────────────────────────────────

def test_list_and_get_episodes(lc):
    ep1 = lc.receive_alert(firing(fp="fp1", alertname="A"))
    ep2 = lc.receive_alert(firing(fp="fp2", alertname="B"))
    episodes = lc.list_episodes()
    assert len(episodes) == 2
    assert lc.get_episode(ep1.id) is not None
    assert lc.get_episode(ep2.id) is not None
    assert lc.get_episode("nonexistent") is None


# ── Concurrency: two simultaneous firings for different fingerprints ────

def test_concurrent_firings_create_separate_episodes(lc):
    ep1 = lc.receive_alert(firing(fp="fp-a"))
    ep2 = lc.receive_alert(firing(fp="fp-b"))
    assert ep1.id != ep2.id
    assert len(lc.episodes) == 2


# ── Out-of-order: resolved arrives before firing ────────────────────────

def test_out_of_order_resolved_before_firing(lc):
    # Resolved arrives first (delayed event)
    ep1 = lc.receive_alert(resolved(fp="fp-oo"))
    assert ep1.status == EpisodeStatus.UNVERIFIED
    # Then firing arrives — creates a new episode
    ep2 = lc.receive_alert(firing(fp="fp-oo"))
    assert ep2.id != ep1.id
    assert ep2.status == EpisodeStatus.ACTIVE


# ── Seeded demo compatibility ───────────────────────────────────────────

def test_seeded_demo_still_works():
    """The existing seeded incident store must still function."""
    from app.service import IncidentStore
    store = IncidentStore()
    incident = store.get("SNT-001")
    assert incident.severity == "Critical"
    assert incident.status == "Investigating"
    assert len(incident.actions) == 3
