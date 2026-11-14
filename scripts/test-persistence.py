"""Exercise real HTTP processes twice in disposable PostgreSQL schemas."""

import os
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
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=directory,
            env=env,
            check=True,
        )
        yield env
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        engine.dispose()


@contextmanager
def server(directory, env):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=directory,
        env=env,
    )
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}") as client:
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
        with server(pay, pay_env) as client:
            response = client.post("/payments", json={"amount": 501, "currency": "INR"})
            assert response.status_code == 201
            receipt = response.json()
        with server(pay, pay_env) as client:
            assert client.get("/payments/" + receipt["id"]).json() == receipt
        with server(ops, ops_env) as client:

            def approve(_):
                return client.post(
                    "/incidents/SNT-001/approve", json={"action_id": "ACT-001"}
                ).status_code

            with ThreadPoolExecutor(2) as pool:
                assert sorted(pool.map(approve, range(2))) == [200, 409]
        with server(ops, ops_env) as client:
            incident = client.get("/incidents/SNT-001").json()
            assert incident["actions"][0]["status"] == "Approved"
            assert incident["timeline"][-1]["kind"] == "Approval"
            assert len(client.get("/audit-logs").json()) == 2
    print(
        "PASS: migrations, payment restart, concurrent decision, audit and timeline restart"
    )


if __name__ == "__main__":
    main()
