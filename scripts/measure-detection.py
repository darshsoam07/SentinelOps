"""Measure three independent database-unavailable episodes in a disposable Compose stack."""

import os
import time
from statistics import mean

import httpx


def main():
    with (
        httpx.Client(base_url="http://localhost:8000/api/v1/") as ops,
        httpx.Client(base_url="http://localhost:8001/api/v1/") as pay,
    ):
        login = ops.post(
            "auth/login",
            data={
                "username": "operator",
                "password": os.environ["SNT_BROWSER_PASSWORD"],
            },
        )
        login.raise_for_status()
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        ops.headers.update(headers)
        pay.headers.update(headers)

        def incident_ids():
            response = ops.get("incidents")
            response.raise_for_status()
            return {i["id"] for i in response.json() if i["id"].startswith("ALT-")}

        def toggle(enabled):
            pay.post(
                "simulation/faults",
                json={"fault": "database_unavailable", "enabled": enabled},
            ).raise_for_status()

        samples = []
        for trial in range(3):
            before = incident_ids()
            toggle(True)
            start = time.monotonic()
            try:
                while time.monotonic() - start < 90:
                    response = pay.post(
                        "payments", json={"amount": 1, "currency": "USD"}
                    )
                    assert response.status_code == 503, response.status_code
                    if incident_ids() - before:
                        samples.append(time.monotonic() - start)
                        print(f"Trial {trial + 1}: {samples[-1]:.2f} s", flush=True)
                        break
                    time.sleep(1)
                else:
                    raise RuntimeError("No new incident within 90 s")
            finally:
                toggle(False)
            if trial < 2:
                time.sleep(50)  # Clear the 30-second query window and alert group.
        print(f"MTTD (n=3): {mean(samples):.2f} s")


if __name__ == "__main__":
    main()
