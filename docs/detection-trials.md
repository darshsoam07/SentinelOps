# PayFlow fault detection trials

On 15 November 2026 the local Docker Desktop stack ran both FastAPI services, separate PostgreSQL 16 databases, Prometheus and Alertmanager. The load generator ran in WSL and used the authenticated PayFlow API. Each trial enabled one simulation switch. The database-unavailable switch returns HTTP 503 while the database itself continues running.

| Fault | Trials | Time to incident (seconds) | Mean (seconds) |
| --- | ---: | --- | ---: |
| Database unavailable | 3 | 17.41, 10.21, 10.22 | 12.62 |
| High latency (800 ms injected) | 1 | 8.11 | — |
| High error rate (alternating HTTP 500 and 201) | 1 | 13.28 | — |

The clock starts on the load generator when the enable request returns successfully. It stops when the same process first reads a new incident for the expected alert through the SentinelOps API. It uses Python's monotonic clock. Each loop submits a one-dollar demo payment, checks for the incident, then waits one second. Detection time includes request handling, scrape and evaluation timing, webhook delivery, database commit and polling delay.

Prometheus scraped and evaluated every five seconds. Both rules used 30-second windows. Alertmanager grouped by alert name with a one-second initial wait. The error rule detected an increase in 5xx responses, and the latency rule detected p95 above 500 ms. The harness disabled each fault in a finally block and allowed 50 seconds between repeated trials. The measurements describe this local workload. The single trials establish that those paths work and do not estimate their typical latency.

To repeat in a disposable Compose stack, set SNT_BROWSER_PASSWORD to the test operator password in the shell and run:

```sh
.venv/bin/python scripts/measure-detection.py --fault database_unavailable --trials 3
.venv/bin/python scripts/measure-detection.py --fault high_latency --trials 1
.venv/bin/python scripts/measure-detection.py --fault high_error_rate --trials 1
```
