"""Run serial trials against the local disposable Compose stack."""

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import platform
import re
from statistics import median
import subprocess
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
FAULTS = {
    "database_unavailable": "PayFlow payment errors",
    "high_latency": "PayFlow payment latency",
    "high_error_rate": "PayFlow payment errors",
}


def utc():
    return datetime.now(UTC).isoformat()


def run_trial(ops, pay, fault):
    def incidents():
        result = ops.get("incidents")
        result.raise_for_status()
        return result.json()

    def toggle(enabled):
        pay.post(
            "simulation/faults", json={"fault": fault, "enabled": enabled}
        ).raise_for_status()

    states = pay.get("simulation/faults")
    states.raise_for_status()
    if any(states.json().values()):
        raise RuntimeError("A fault is already active")
    before = {i["id"] for i in incidents()}
    toggle(True)
    start = time.monotonic()
    sample = {"fault": fault, "fault_acknowledged_at": utc()}
    try:
        while time.monotonic() - start < 120:
            result = pay.post("payments", json={"amount": 1, "currency": "USD"})
            if result.status_code not in (201, 500, 503):
                result.raise_for_status()
            # First observed application symptom, distinct from Prometheus firing time.
            if result.status_code >= 500 or result.elapsed.total_seconds() >= 0.5:
                sample.setdefault("first_signal_at", utc())
            episode = next(
                (
                    i
                    for i in incidents()
                    if i["title"] == FAULTS[fault] and i["id"] not in before
                ),
                None,
            )
            if episode:
                sample.update(
                    incident_id=episode["id"],
                    incident_created_at=episode["detected_at"],
                    incident_observed_at=utc(),
                    mttd_seconds=round(time.monotonic() - start, 3),
                )
                break
            time.sleep(1)
        else:
            raise TimeoutError("No new incident")
    finally:
        toggle(False)
    sample["fault_cleared_at"] = utc()
    while time.monotonic() - start < 240:
        result = ops.get("incidents/" + sample["incident_id"])
        result.raise_for_status()
        episode = result.json()
        if episode["resolved_at"] and episode["verified_restored_at"]:
            sample.update(
                resolved_at=episode["resolved_at"],
                verified_restored_at=episode["verified_restored_at"],
                mttr_seconds=round(time.monotonic() - start, 3),
            )
            return sample
        time.sleep(1)
    raise TimeoutError("No confirmed resolution")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.trials < 1 or args.output.exists():
        parser.error("Use positive trials and a new output filename")
    configs = ROOT / "infrastructure/monitoring"
    raw = (configs / "prometheus.yml").read_text() + (
        configs / "alertmanager.yml"
    ).read_text()
    timing = {
        k: re.search(r"^\s*" + k + r": (\S+)", raw, re.M)[1]
        for k in (
            "scrape_interval",
            "evaluation_interval",
            "group_wait",
            "group_interval",
            "repeat_interval",
        )
    }
    timing["rule_for"] = (
        re.findall(r"^\s*for: (\S+)", (configs / "payflow.yml").read_text(), re.M)
        or "none"
    )
    samples = []
    report = {
        "date": utc(),
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "machine": platform.platform(),
        "monitoring": timing,
        "samples": samples,
        "summary": {},
    }
    with (
        httpx.Client(base_url="http://localhost:8000/api/v1/") as ops,
        httpx.Client(base_url="http://localhost:8001/api/v1/") as pay,
    ):
        for fault in FAULTS:
            for _ in range(args.trials):
                login = ops.post(
                    "auth/login",
                    data={
                        "username": "operator",
                        "password": os.environ["SNT_BROWSER_PASSWORD"],
                    },
                )
                login.raise_for_status()
                ops.headers["Authorization"] = pay.headers["Authorization"] = (
                    "Bearer " + login.json()["access_token"]
                )
                sample = run_trial(ops, pay, fault)
                samples.append(sample)
                data = [s for s in samples if s["fault"] == fault]
                summary = {"n": len(data)}
                for metric in ("mttd_seconds", "mttr_seconds"):
                    values = [s[metric] for s in data]
                    summary[metric] = {
                        "min": min(values),
                        "median": median(values),
                        "max": max(values),
                    }
                report["summary"][fault] = summary
                args.output.write_text(json.dumps(report, indent=2) + "\n")
                print(fault, sample["mttd_seconds"], sample["mttr_seconds"], flush=True)


if __name__ == "__main__":
    main()
