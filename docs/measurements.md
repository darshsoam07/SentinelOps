# Measuring detection and restoration

Use a disposable, otherwise idle Compose stack with both databases and all monitoring services. Set SNT_BROWSER_PASSWORD privately for the configured operator. From the repository root:

```sh
.venv/bin/python scripts/measure_detection.py --output results.json
```

The default is ten independent trials for each of three fault types. The script submits a one-dollar demo payment and checks the incident list each loop, with a one-second sleep. It clears the injection in a finally block, then waits for the incident to resolve and for independent checks to record restoration before the next trial. An unrelated active fault aborts the run. The output is saved after each completed trial. A partial file describes only completed trials.

The load generator records fault_acknowledged_at when the enable call returns and first_signal_at when it first observes a failing or slow payment. incident_created_at is the SentinelOps server timestamp. incident_observed_at is when the client first reads the new incident. Alertmanager supplies resolved_at. SentinelOps supplies verified_restored_at after three successful readiness and fault-state checks over four seconds.

MTTD is client-observed elapsed time from fault acknowledgment to reading the incident. MTTR here is client-observed elapsed time from fault acknowledgment to reading both resolution and verified restoration. Both use the same monotonic clock and include polling delay. UTC timestamps are descriptive and can differ across hosts. Measurement trials use manual cleanup. Use the separate Chromium lifecycle test to assess operator approval and execution.

JSON contains per-trial timestamps, counts, median, minimum and maximum, host platform, UTC date, source revision and monitoring intervals. Results apply to this local workload. [Measurement decision](decisions/measurements.md)

## Observed Compose trials

Measured application revision `be20ba8`. All 30 trials produced distinct incidents with separate resolution and verification timestamps. These trials used manual cleanup.

| Fault | n | Detection seconds, median (min–max) | Restoration seconds, median (min–max) |
|---|---:|---:|---:|
| database_unavailable | 10 | 10.34 (8.31–11.42) | 49.97 (47.95–50.39) |
| high_latency | 10 | 10.07 (9.99–11.90) | 49.74 (48.78–54.83) |
| high_error_rate | 10 | 11.39 (10.35–15.55) | 50.03 (48.99–55.36) |

[Machine-readable samples and run configuration](measurements/compose-trials.json)
