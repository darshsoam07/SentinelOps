# Architecture

The React Router dashboard issues HTTP requests through dashboard/src/services/api.ts. Separate environment variables select the two service origins. The browser loads incidents and summary independently from payment history. Each health indicator queries its own process. The UI fetches resource data when its page opens and refreshes affected records after mutations.

## Incident intelligence

backend/api/app/seed.py supplies a fixed UTC timeline and a qualitative hypothesis with alternative explanations, missing evidence and runbooks. Evidence references identify local demonstration records. The latency trace and percentages describe the seeded deployment window. Availability proxy is the complement of error rate. MTTD spans deployment to detection. MTTR is unavailable until a restoration is observed.

Routes validate bodies with Pydantic and delegate decisions to IncidentStore. It checks incident state, action ownership, allowed operation and prior decision before recording the decision, timeline event and audit entry in a single synchronous transition. A successful request returns the updated incident. Approval leaves execution unexecuted and the incident investigating. New decisions record the username from the validated JWT.

## PayFlow

PaymentStore snapshots fault settings when a payment starts. High latency adds 800 ms without blocking other requests. High error rate fails the first and every other eligible request after activation. Database outage takes precedence over processing errors. All completed attempts receive a UTC timestamp and unique ID and are available for lookup. The chart uses fixed incident evidence while payment activity counts actual calls to the local simulation.

## Boundaries and next phases

Each API uses request-scoped database interactions; Alembic uses a synchronous psycopg connection. Each API has its own SQLAlchemy engine, PostgreSQL login and Alembic history. PayFlow stores receipts in typed columns. SentinelOps stores validated incident aggregates in JSONB and separate audit rows linked to the incident. A row lock serializes decisions, and the transaction commits the timeline, action state and audit together. An idempotent seed initializes the demo. Omitting the database URLs selects the original in-memory mode. Fault switches remain local to one PayFlow process. Deployment phases include Docker Compose, Kubernetes and Helm, Terraform on AWS, GitHub Actions and Argo CD. Prometheus, Grafana, Loki and OpenTelemetry can supply measurements and evidence. Future LLM/RAG investigation can consume read-only evidence. A separate restricted recovery executor would consume explicitly authorized actions and publish execution results. These integrations are future work.

## Live incident lifecycle & monitoring integration

SentinelOps distinguishes two categories of incidents:
1. **Seeded demonstration incident (`SNT-001`)**: A fixed, deterministic scenario used for demonstrating operator investigation, hypothesis evaluation, and approval/rejection workflows with audit trails.
2. **Live PayFlow episodes (`ALT-*`)**: Live incidents generated dynamically by Prometheus and Alertmanager when PayFlow faults are active.

### Alertmanager webhook & episode identity
- Prometheus scrapes PayFlow metrics every 5 seconds and evaluates alert rules (`PayFlowPaymentErrors`, `PayFlowPaymentLatency`) with a 30-second observation window.
- When an alert fires, Alertmanager delivers a webhook payload to SentinelOps at `/internal/alerts` with `ALERT_WEBHOOK_TOKEN` bearer authentication.
- SentinelOps computes a deterministic episode ID: `ALT-` followed by the first 24 characters of `sha256(fingerprint + startsAt)`.
- If an active episode for the fingerprint already exists, repeated firing alerts are handled idempotently, appending updated evidence snapshots without duplicating the episode.

### Episode lifecycle states
```
[Firing alert]       --> Investigating (detected_at set, evidence snapshot captured)
[Resolved alert]     --> Resolving (resolved_at set, recovery unverified pending traffic)
[Verified traffic]   --> Resolved (verified_restored_at set, verification event added)
```

### Verified recovery criteria
A resolved alert does not immediately mark an incident restored. Verified recovery (`POST /api/v1/incidents/{id}/verify`) requires:
- At least 5 successful payment submissions recorded in the observation window.
- Zero server failures (HTTP 5xx).
- p95 latency ≤ 2.0 seconds.
If traffic is absent or criteria are not satisfied, the incident remains unverified in `Resolving` state.

### PostgreSQL episode persistence
Migration `0002_incident_fields.py` extends the `incidents` schema with:
- `fingerprint`: Alertmanager alert fingerprint.
- `starts_at`: ISO 8601 alert start timestamp.
- `resolved_at`: ISO 8601 alert resolved timestamp.
- `verified_restored_at`: ISO 8601 recovery verification timestamp.
- `evidence_source`: Source of the verification metrics (e.g., `prometheus:payflow`).
- `rule_name`: Name of the triggering alert rule.
All state transitions, evidence snapshots, and timeline events are persisted atomically and survive service restarts.

SentinelOps issues 15-minute JWTs after checking the configured Argon2 password hash. Each API checks the signature, issuer, audience, expiry and operator subject before serving business routes. The dashboard attaches the token from localStorage. TanStack Query v5 caches reads within each authenticated session and invalidates payment history when a submission completes, including simulated failed receipts.
