"""Measure three independent database-unavailable episodes in a disposable Compose stack."""

import argparse
import os
import time
from statistics import median

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fault",
        choices=["database_unavailable", "high_error_rate", "high_latency"],
        default="database_unavailable",
    )
    parser.add_argument("--trials", type=int, default=3)
    args = parser.parse_args()
    if args.trials < 1:
        parser.error("--trials must be positive")
    title = (
        "PayFlow payment latency"
        if args.fault == "high_latency"
        else "PayFlow payment errors"
    )
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
            return {
                i["id"]
                for i in response.json()
                if i["id"].startswith("ALT-") and i["title"] == title
            }

        def toggle(enabled):
            pay.post(
                "simulation/faults",
                json={"fault": args.fault, "enabled": enabled},
            ).raise_for_status()

        samples = []
        for trial in range(args.trials):
            before = incident_ids()
            toggle(True)
            start = time.monotonic()
            try:
                while time.monotonic() - start < 90:
                    response = pay.post(
                        "payments", json={"amount": 1, "currency": "USD"}
                    )
                    allowed = {
                        "database_unavailable": (503,),
                        "high_error_rate": (201, 500),
                        "high_latency": (201,),
                    }
                    assert response.status_code in allowed[args.fault], (
                        response.status_code
                    )
                    if incident_ids() - before:
                        samples.append(time.monotonic() - start)
                        print(f"Trial {trial + 1}: {samples[-1]:.2f} s", flush=True)
                        break
                    time.sleep(1)
                else:
                    raise RuntimeError("No new incident within 90 s")
            finally:
                toggle(False)
            if trial + 1 < args.trials:
                time.sleep(50)  # Clear the 30-second query window and alert group.
        print(f"{args.fault} median detection time (n={args.trials}): {median(samples):.2f} s")


if __name__ == "__main__":
    main()
