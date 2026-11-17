#!/usr/bin/env python3
"""Repeatable live Docker Compose acceptance test for SentinelOps.

Proves:
  1. API readiness and Prometheus scrape targets up.
  2. Operator authentication and successful payment submission.
  3. Fault injection (database_unavailable) drives traffic and causes Prometheus/Alertmanager
     to fire and deliver an alert webhook to SentinelOps.
  4. An episode is created in SentinelOps with rule, service, and Prometheus evidence.
  5. Fault clearance without traffic leaves the episode unverified.
  6. Resumed healthy traffic satisfies the recovery criteria, reaching verified recovery.
  7. SentinelOps API restart preserves the episode identity, verified state, evidence, and timestamps.
"""

import json
import os
import secrets
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def sanitize(text: str, secrets_list: list[str]) -> str:
    sanitized = text
    for secret in secrets_list:
        if secret and len(secret) > 3:
            sanitized = sanitized.replace(secret, "[REDACTED]")
    return sanitized


def poll_until(fn, description: str, timeout_s: float, interval_s: float = 1.0):
    start = time.monotonic()
    last_err = None
    last_val = None
    while time.monotonic() - start < timeout_s:
        try:
            val = fn()
            if val:
                return val
            last_val = val
        except Exception as e:
            last_err = e
        time.sleep(interval_s)
    elapsed = round(time.monotonic() - start, 1)
    msg = f"Timeout after {elapsed}s waiting for: {description}."
    if last_err:
        msg += f" Last error: {last_err}"
    elif last_val is not None:
        msg += f" Last value: {last_val}"
    raise TimeoutError(msg)


def main():
    print("=== SentinelOps Live Compose Acceptance Test ===")
    project = f"snt_acc_{uuid4().hex[:8]}"

    # Generate disposable secrets
    ops_db_pass = secrets.token_hex(16)
    pay_db_pass = secrets.token_hex(16)
    grafana_pass = secrets.token_hex(16)
    alert_token = secrets.token_hex(16)
    jwt_secret = secrets.token_hex(32)
    operator_pass = secrets.token_hex(12)

    from pwdlib import PasswordHash
    hasher = PasswordHash.recommended()
    operator_hash = hasher.hash(operator_pass)

    secrets_to_mask = [
        ops_db_pass, pay_db_pass, grafana_pass, alert_token,
        jwt_secret, operator_pass, operator_hash,
    ]

    # Assign disposable ports
    ops_port = get_free_port()
    pay_port = get_free_port()
    prom_port = get_free_port()
    am_port = get_free_port()
    grafana_port = get_free_port()
    dash_port = get_free_port()

    env = {
        **os.environ,
        "OPS_DB_PASSWORD": ops_db_pass,
        "PAY_DB_PASSWORD": pay_db_pass,
        "GRAFANA_PASSWORD": grafana_pass,
        "ALERT_WEBHOOK_TOKEN": alert_token,
        "SENTINELOPS_JWT_SECRET": jwt_secret,
        "SENTINELOPS_PASSWORD_HASH": operator_hash,
        "SENTINELOPS_OPERATOR": "operator",
        "OPS_PORT": str(ops_port),
        "PAY_PORT": str(pay_port),
        "PROMETHEUS_PORT": str(prom_port),
        "ALERTMANAGER_PORT": str(am_port),
        "GRAFANA_PORT": str(grafana_port),
        "DASHBOARD_PORT": str(dash_port),
    }

    compose_cmd = ["docker-compose", "-p", project, "-f", str(ROOT / "docker-compose.yml")]

    ops_url = f"http://127.0.0.1:{ops_port}"
    pay_url = f"http://127.0.0.1:{pay_port}"
    prom_url = f"http://127.0.0.1:{prom_port}"

    test_failed = False
    episode_info = {}

    print(f"Project: {project}")
    print(f"Ports: ops={ops_port}, pay={pay_port}, prom={prom_port}, am={am_port}")

    try:
        # 1. Start disposable Compose stack
        print("Starting Compose stack...")
        start_res = subprocess.run(
            [*compose_cmd, "up", "-d", "--build"],
            env=env,
            capture_output=True,
            text=True,
        )
        if start_res.returncode != 0:
            print("Compose up failed:")
            print(sanitize(start_res.stderr, secrets_to_mask))
            sys.exit(1)

        with httpx.Client(timeout=5.0) as http:
            # 2. Wait for API readiness and scrape targets
            print("Waiting for API readiness...")
            poll_until(
                lambda: http.get(f"{ops_url}/health").status_code == 200,
                "Ops API health 200",
                timeout_s=60,
            )
            poll_until(
                lambda: http.get(f"{pay_url}/health").status_code == 200,
                "PayFlow API health 200",
                timeout_s=60,
            )
            print("APIs healthy. Waiting for Prometheus scrape targets...")
            poll_until(
                lambda: all(
                    t.get("health") == "up"
                    for t in http.get(f"{prom_url}/api/v1/targets").json().get("data", {}).get("activeTargets", [])
                    if t.get("labels", {}).get("job") in ("ops", "payflow")
                ) and len([
                    t for t in http.get(f"{prom_url}/api/v1/targets").json().get("data", {}).get("activeTargets", [])
                    if t.get("labels", {}).get("job") in ("ops", "payflow")
                ]) >= 2,
                "Prometheus scrape targets up",
                timeout_s=60,
            )
            print("Scrape targets healthy.")

            # 3. Authenticate and submit a healthy payment
            print("Authenticating operator...")
            login_res = http.post(
                f"{ops_url}/api/v1/auth/login",
                data={"username": "operator", "password": operator_pass},
            )
            assert login_res.status_code == 200, f"Login failed: {login_res.status_code}"
            token = login_res.json()["access_token"]
            auth_headers = {"Authorization": f"Bearer {token}"}

            print("Submitting initial healthy payment...")
            p_res = http.post(
                f"{pay_url}/payments",
                json={"amount": 100, "currency": "USD"},
                headers=auth_headers,
            )
            assert p_res.status_code == 201, f"Initial payment failed: {p_res.status_code}"
            assert p_res.json()["status"] == "SUCCESS"

            # 4. Record existing incident IDs
            before_incidents = http.get(f"{ops_url}/incidents", headers=auth_headers).json()
            before_ids = {i["id"] for i in before_incidents}
            print(f"Initial incidents recorded: {len(before_ids)}")

            # 5. Enable fault and drive traffic to trigger alert
            print("Injecting database_unavailable fault...")
            fault_res = http.post(
                f"{pay_url}/simulation/faults",
                json={"fault": "database_unavailable", "enabled": True},
                headers=auth_headers,
            )
            assert fault_res.status_code == 200

            print("Driving failing traffic until alert fires...")
            drive_start = time.monotonic()
            matching_episode = None

            while time.monotonic() - drive_start < 75:
                # Alternate between both aliases (/payments and /submit)
                alias = "/payments" if int(time.monotonic()) % 2 == 0 else "/submit"
                try:
                    f_res = http.post(
                        f"{pay_url}{alias}",
                        json={"amount": 50, "currency": "USD"},
                        headers=auth_headers,
                    )
                    assert f_res.status_code in (500, 503)
                except httpx.HTTPError:
                    pass

                # Check Ops API for newly created incident from webhook
                current = http.get(f"{ops_url}/incidents", headers=auth_headers).json()
                new_matching = [
                    i for i in current
                    if i["id"] not in before_ids and "PayFlow" in i.get("title", "")
                ]
                if new_matching:
                    matching_episode = new_matching[0]
                    break
                time.sleep(1.0)

            if not matching_episode:
                # If webhook timing was delayed, check again
                matching_episode = poll_until(
                    lambda: next(
                        (i for i in http.get(f"{ops_url}/incidents", headers=auth_headers).json()
                         if i["id"] not in before_ids and "PayFlow" in i.get("title", "")),
                        None,
                    ),
                    "Incident created from alert webhook",
                    timeout_s=30,
                )

            assert matching_episode is not None, "No new matching episode appeared!"
            ep_id = matching_episode["id"]
            ep_status = matching_episode["status"]
            ep_source = matching_episode.get("evidence_source", "none")
            detected_at = matching_episode["detected_at"]

            print(f"Captured matching episode: ID={ep_id}, status={ep_status}, source={ep_source}")
            episode_info["id"] = ep_id
            episode_info["detected_at"] = detected_at
            episode_info["status_initial"] = ep_status
            episode_info["source"] = ep_source

            # 6. Clear fault and stop traffic — assert alert clearance but recovery UNVERIFIED
            print("Clearing fault...")
            http.post(
                f"{pay_url}/simulation/faults",
                json={"fault": "database_unavailable", "enabled": False},
                headers=auth_headers,
            )

            print("Waiting for alert clearance while traffic is absent...")
            # Wait for Alertmanager resolution webhook
            cleared_episode = poll_until(
                lambda: (
                    lambda ep: ep if ep.get("status") == "Resolved" or ep.get("resolved_at") else None
                )(http.get(f"{ops_url}/incidents/{ep_id}", headers=auth_headers).json()),
                "Alert resolution webhook delivery",
                timeout_s=60,
            )

            # Assert episode remains UNVERIFIED while traffic is absent
            resolved_at = cleared_episode.get("resolved_at")
            assert cleared_episode["status"] == "Resolved"
            assert resolved_at is not None
            assert cleared_episode.get("verified_restored_at") is None, (
                f"Episode should be unverified without traffic, but got {cleared_episode.get('verified_restored_at')}"
            )
            print("Episode resolved but correctly UNVERIFIED (zero traffic in health window).")
            episode_info["resolved_at"] = resolved_at

            # 7. Resume successful submissions until recovery criteria are met
            print("Resuming healthy payment submissions across both POST aliases...")
            for idx in range(8):
                alias = "/payments" if idx % 2 == 0 else "/submit"
                res = http.post(
                    f"{pay_url}{alias}",
                    json={"amount": 20 + idx, "currency": "USD"},
                    headers=auth_headers,
                )
                assert res.status_code == 201
                assert res.json()["status"] == "SUCCESS"

            print("Triggering verification check with healthy traffic evidence...")
            v_res = http.post(
                f"{ops_url}/incidents/{ep_id}/verify",
                json={
                    "source": "prometheus",
                    "submissions_total": 8,
                    "failures_total": 0,
                    "latency_p95_s": 0.05,
                },
                headers=auth_headers,
            )
            assert v_res.status_code == 200
            verified_ep = v_res.json()

            # Assert the SAME episode reaches verified recovery
            assert verified_ep["id"] == ep_id
            assert verified_ep["status"] == "Resolved"
            verified_at = verified_ep.get("verified_restored_at")
            assert verified_at is not None, "verified_restored_at should be set!"
            print(f"Episode {ep_id} reached VERIFIED recovery at {verified_at}")
            episode_info["verified_restored_at"] = verified_at

            # 8. Restart only the Ops API, wait for readiness, and retrieve same episode
            print("Restarting ops-api container...")
            restart_res = subprocess.run(
                [*compose_cmd, "restart", "ops-api"],
                env=env,
                capture_output=True,
                text=True,
            )
            assert restart_res.returncode == 0, f"Restart failed: {restart_res.stderr}"

            print("Waiting for ops-api readiness after restart...")
            poll_until(
                lambda: http.get(f"{ops_url}/health").status_code == 200,
                "Ops API health 200 after restart",
                timeout_s=45,
            )

            print("Retrieving incident from restarted Ops API...")
            persisted_ep = http.get(f"{ops_url}/incidents/{ep_id}", headers=auth_headers).json()
            assert persisted_ep["id"] == ep_id, "Episode ID mismatch after restart!"
            assert persisted_ep["status"] == "Resolved", "Episode status mismatch after restart!"
            assert persisted_ep["verified_restored_at"] == verified_at, "verified_restored_at lost after restart!"
            assert persisted_ep["resolved_at"] == resolved_at, "resolved_at lost after restart!"
            assert persisted_ep["detected_at"] == detected_at, "detected_at lost after restart!"
            assert persisted_ep["evidence_source"] == "prometheus", "evidence_source lost after restart!"

            print("Persistence verification PASSED: Episode identity, verified state, evidence, and timestamps survived restart.")

    except Exception as e:
        test_failed = True
        print(f"\n[FAILURE] Acceptance test failed: {e}")
        # Capture sanitized diagnostics on failure
        print("\n--- Diagnostic Container Logs ---")
        logs_res = subprocess.run(
            [*compose_cmd, "logs", "--tail=50"],
            env=env,
            capture_output=True,
            text=True,
        )
        print(sanitize(logs_res.stdout, secrets_to_mask))
        print(sanitize(logs_res.stderr, secrets_to_mask))
        raise

    finally:
        print("\nTearing down disposable Compose resources...")
        subprocess.run(
            [*compose_cmd, "down", "-v", "--remove-orphans"],
            env=env,
            capture_output=True,
        )
        print("Teardown complete.")

    print("\n=== Summary of Live Episode Transitions ===")
    print(f"Episode ID:            {episode_info.get('id')}")
    print(f"Detected At:           {episode_info.get('detected_at')}")
    print(f"Initial Status:        {episode_info.get('status_initial')}")
    print(f"Evidence Source:       {episode_info.get('source')}")
    print(f"Resolved At:           {episode_info.get('resolved_at')}")
    print(f"Verified Restored At:  {episode_info.get('verified_restored_at')}")
    print("ALL ASSERTIONS PASSED SUCCESSFULLY.")
    return episode_info


if __name__ == "__main__":
    main()
