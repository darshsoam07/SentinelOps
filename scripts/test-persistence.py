"""Exercise real HTTP processes twice in disposable PostgreSQL schemas."""

import os
import tempfile
import secrets
import jwt
from datetime import UTC, datetime, timedelta
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, ExitStack
from pathlib import Path
from uuid import uuid4

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


def verify_incident_migration(directory, env, url):
    def migrate(command, revision):
        subprocess.run(
            [sys.executable, "-m", "alembic", command, revision],
            cwd=directory,
            env=env,
            check=True,
        )

    migrate("upgrade", "0001")
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text("""INSERT INTO incidents(id, record) VALUES
                ('upgrade-fixture', '{"status":"Open","severity":"Low"}')""")
            )
        migrate("upgrade", "0002")
        with engine.begin() as connection:
            query = text(
                "SELECT status, severity FROM incidents WHERE id='upgrade-fixture'"
            )
            assert tuple(connection.execute(query).one()) == ("Open", "Low")
            connection.execute(
                text("""UPDATE incidents SET record='{"status":"Resolved","severity":"High"}'
                WHERE id='upgrade-fixture'""")
            )
            assert tuple(connection.execute(query).one()) == ("Resolved", "High")
        migrate("downgrade", "0001")
        with engine.begin() as connection:
            assert set(
                connection.execute(text("SELECT * FROM incidents LIMIT 0")).keys()
            ) == {"id", "record"}
            assert (
                connection.execute(
                    text(
                        "DELETE FROM incidents WHERE id='upgrade-fixture' RETURNING record"
                    )
                ).scalar()["status"]
                == "Resolved"
            )
    finally:
        engine.dispose()


@contextmanager
def database(name, directory):
    variable = name + "_DATABASE_URL"
    url = make_url(os.environ[variable])
    schema = "test_" + uuid4().hex
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    try:
        test_url = url.update_query_dict({"options": "-csearch_path=" + schema})
        env = dict(
            os.environ, **{variable: test_url.render_as_string(hide_password=False)}
        )
        if name == "SENTINELOPS":
            verify_incident_migration(directory, env, test_url)
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=directory,
            env=env,
            check=True,
        )
        env[variable] = url.render_as_string(hide_password=False)
        env["PG_TEST_SCHEMA"] = schema
        env["PYTHONPATH"] = (
            str(ROOT / "scripts") + os.pathsep + env.get("PYTHONPATH", "")
        )
        yield env
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        engine.dispose()


@contextmanager
def server(directory, env, signing_file):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "persistence_app:build",
            "--factory",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=directory,
        env=env,
    )
    try:
        now = datetime.now(UTC)
        token = jwt.encode(
            dict(
                sub="operator",
                iss="sentinelops",
                aud="sentinelops-workspace",
                iat=now,
                exp=now + timedelta(minutes=5),
            ),
            Path(signing_file).read_bytes(),
            algorithm="EdDSA",
        )
        with httpx.Client(
            headers={"Authorization": "Bearer " + token},
            base_url=f"http://127.0.0.1:{port}",
        ) as client:
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError("API exited during startup")
                try:
                    if client.get("/health").is_success:
                        break
                except httpx.ConnectError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError("API startup timed out")
            assert client.get("/ready").json() == {
                "status": "ready",
                "storage": "postgresql",
            }
            assert "http_requests_total" in client.get("/metrics").text
            yield client
    finally:
        process.terminate()
        process.wait(timeout=10)


def main():
    ops = ROOT / "backend/api"
    pay = ROOT / "applications/payflow/payment-service"
    with ExitStack() as stack:
        ops_env = stack.enter_context(database("SENTINELOPS", ops))
        pay_env = stack.enter_context(database("PAYFLOW", pay))
        keys = Path(stack.enter_context(tempfile.TemporaryDirectory())) / "keys"
        subprocess.run([sys.executable, ROOT / "scripts/generate-keys.py", keys], check=True)
        ops_env["SENTINELOPS_PUBLIC_KEY_FILE"] = pay_env["SENTINELOPS_PUBLIC_KEY_FILE"] = str(keys / "public.pem")
        signing_file = keys / "private.pem"
        with server(pay, pay_env, signing_file) as client:
            response = client.post("/payments", json={"amount": 501, "currency": "INR"})
            assert response.status_code == 201
            receipt = response.json()
        with server(pay, pay_env, signing_file) as client:
            assert client.get("/payments/" + receipt["id"]).json() == receipt
            assert client.get("/payments?limit=1").json() == [receipt]
        with server(ops, ops_env, signing_file) as client:

            def approve(_):
                return client.post(
                    "/incidents/SNT-001/approve", json={"action_id": "ACT-001"}
                ).status_code

            with ThreadPoolExecutor(2) as pool:
                assert sorted(pool.map(approve, range(2))) == [200, 409]
        with server(ops, ops_env, signing_file) as client:
            incident = client.get("/incidents/SNT-001").json()
            assert incident["actions"][0]["status"] == "Approved"
            assert incident["timeline"][-1]["kind"] == "Approval"
            assert len(client.get("/audit-logs").json()) == 2
            assert len(client.get("/audit-logs?limit=1").json()) == 1
            assert client.get("/metrics/summary").json()["active"] == 1
        with tempfile.NamedTemporaryFile(mode="w") as credential:
            credential.write(secrets.token_hex(32))
            credential.flush()
            ops_env["ALERT_TOKEN_FILE"] = credential.name
            headers = {"Authorization": "Bearer " + Path(credential.name).read_text()}
            with server(ops, ops_env, signing_file) as client:
                alert = dict(
                    fingerprint="integration",
                    startsAt="2026-01-01T00:00:00Z",
                    status="firing",
                    labels={"alertname": "PayFlowPaymentErrors"},
                )
                for status in ("firing", "firing", "resolved", "resolved", "firing"):
                    alert.update(status=status, endsAt="2026-01-01T01:00:00Z")
                    assert (
                        client.post(
                            "/internal/alerts",
                            headers=headers,
                            json={"alerts": [alert]},
                        ).status_code
                        == 200
                    )
                episodes = [
                    i
                    for i in client.get("/incidents").json()
                    if i["id"].startswith("ALT-")
                ]
                assert len(episodes) == 1 and episodes[0]["status"] == "Resolved"
                assert (
                    episodes[0]["resolved_at"]
                    and episodes[0]["verified_restored_at"] is None
                )
                assert (
                    len(
                        [
                            e
                            for e in client.get("/audit-logs").json()
                            if e["actor"] == "Alertmanager"
                        ]
                    )
                    == 1
                )
    print(
        "PASS: migrations, payment restart, concurrent decision, audit and timeline restart"
    )


if __name__ == "__main__":
    main()
