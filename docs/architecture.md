# Architecture

The React Router dashboard issues HTTP requests through dashboard/src/services/api.ts. Separate environment variables select the two service origins. The browser loads incidents and summary independently from payment history. Each health indicator queries its own process. The UI fetches resource data when its page opens and refreshes affected records after mutations.

## Incident intelligence

backend/api/app/seed.py supplies a fixed UTC timeline and a qualitative hypothesis with alternative explanations, missing evidence and runbooks. Evidence references identify local demonstration records. The latency trace and percentages describe the seeded deployment window. Availability proxy is the complement of error rate. MTTD spans deployment to detection. MTTR is unavailable until a restoration is observed.

Routes validate bodies with Pydantic and delegate decisions to IncidentStore. It checks incident state, action ownership, allowed operation and prior decision before recording the decision, timeline event and audit entry in a single synchronous transition. A successful request returns the updated incident. Approval leaves execution unexecuted and the incident investigating. New decisions record the username from the validated JWT.

## PayFlow

PaymentStore snapshots fault settings when a payment starts. High latency adds 800 ms without blocking other requests. High error rate fails the first and every other eligible request after activation. Database outage takes precedence over processing errors. All completed attempts receive a UTC timestamp and unique ID and are available for lookup. The chart uses fixed incident evidence while payment activity counts actual calls to the local simulation.

## Boundaries and next phases

Each API uses request-scoped async SQLAlchemy sessions with asyncpg; Alembic uses a synchronous psycopg connection. Each API has its own SQLAlchemy engine, PostgreSQL login and Alembic history. PayFlow stores receipts in typed columns. SentinelOps stores validated incident aggregates in JSONB and separate audit rows linked to the incident. A row lock serializes decisions, and the transaction commits the timeline, action state and audit together. An idempotent seed initializes the demo. Omitting the database URLs selects the original in-memory mode. Fault switches remain local to one PayFlow process. Deployment phases include Docker Compose, Kubernetes and Helm, Terraform on AWS, GitHub Actions and Argo CD. Prometheus, Grafana, Loki and OpenTelemetry can supply measurements and evidence. Future LLM/RAG investigation can consume read-only evidence. A separate restricted recovery executor would consume explicitly authorized actions and publish execution results. These integrations are future work.

SentinelOps issues 15-minute JWTs after checking the configured Argon2 password hash. Each API checks the signature, issuer, audience, expiry and operator subject before serving business routes. The dashboard attaches the token from memory. TanStack Query v5 caches reads within each authenticated session and invalidates payment history when a submission completes, including simulated failed receipts.
