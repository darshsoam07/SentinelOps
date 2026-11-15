# Local demo (3–5 minutes)
1. **0:00–0:45.** Sign in at localhost:8080. Show the labelled SNT-001 seed and the live Prometheus source in the overview. In Grafana open SentinelOps service health.
2. **0:45–1:45.** In PayFlow lab enable Database unavailable. Submit several demo payments, roughly once per second across two scrape intervals. Show the failed receipts. Open Incidents and refresh until a new PayFlow payment errors episode appears.
3. **1:45–2:45.** Open Approvals, locate the new alert ID, and review the clear-fault proposal. Approve only that proposal. Watch the execution status change and show the operator's audit records. Submit another payment and retrieve its success receipt.
4. **2:45–4:00.** Refresh after the rule window clears. Show Alertmanager resolution separately from the independent verification timestamp in the incident API response. End with the local trial distribution and its clock definition.
