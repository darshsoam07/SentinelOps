# SentinelOps — Cloud Incident Intelligence and Reliability Engineering Workspace

**Observe. Investigate. Decide. Recover.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Optional%20Persistence-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

SentinelOps gives an operator one place to investigate a PayFlow payment regression, review a proposed recovery action and see who decided it. The same workspace lets a reviewer send payments to a running API and observe how it responds to controlled faults.

> **Current status · Runnable local MVP.** Incident SNT-001 uses seeded evidence. Payment receipts, API health checks, approval decisions and audit entries come from actual HTTP requests. Both services support in-memory operation and optional PostgreSQL persistence.

| Feature | Status | Evidence |
|---|---|---|
| Operator login with Ed25519 tokens | Implemented | [Signing ADR](docs/decisions/ed25519.md), [auth tests](backend/api/tests/test_auth.py) |
| Live alerts, episode deduplication and resolution audit | Implemented | [PostgreSQL restart and redelivery test](scripts/test-persistence.py) |
| Approved clearance of one injected PayFlow database fault | Implemented | [Chromium Compose test](dashboard/compose-tests/recovery.spec.ts), [executor ADR](docs/decisions/recovery.md) |
| SNT-001 deployment investigation and remediation recommendations | Seeded | [Scenario source](backend/api/app/seed.py) |
| Detection and restoration trial collection | Implemented | [Measurement method](docs/measurements.md) |
| Signing-key rotation and token revocation | Planned | [Signing limits](docs/decisions/ed25519.md) |

## Problem statement

After a payment deployment, slow requests and database timeouts may appear together. An operator needs to establish which observations support a rollback, what evidence is missing and whether anyone has already approved the action.

## Solution and reliability workflow

The full workflow runs from observing a failure through detecting and correlating signals, investigating a cause, reviewing a recommendation, executing recovery and verifying restoration. Today's entry point is a prepared incident. The operator inspects its evidence, approves or rejects a recommendation, and checks the resulting timeline and audit history.

## Implemented features

| Capability | What a reviewer can verify today |
|---|---|
| Operations overview | Check both API processes and inspect the seeded latency window alongside counts of actual test payments. |
| Investigation | Filter incidents and open the UTC timeline, hypothesis, evidence references, alternatives, missing evidence and suggested runbooks. |
| Decision and audit | Approve or reject an allowlisted action. A second decision returns HTTP 409. The first decision appears in both the timeline and audit trail. |
| Payment traffic | Submit a positive amount and three-letter uppercase currency. Retrieve the resulting UUID receipt, including failed attempts. |
| Controlled faults | Add 800 ms of latency, fail the first and every other eligible payment with HTTP 500, or simulate a database outage with HTTP 503. |
| Persistence | Restart the APIs with PostgreSQL configured and retrieve the original receipt and decision. Each service owns its database and migrations. |

## Main demonstration · Payment Service Performance Regression (SNT-001)

1. Open **SNT-001** from Overview. Its seeded deployment timeline begins at 10:20 UTC on 14 November 2026. Detection follows at 10:30 UTC.
2. Inspect the evidence: 95% CPU, a 28% HTTP error rate, 4.2 seconds p95 latency and five pod restarts. The metrics, logs, trace references and deployment record are seeded. The deterministic investigation links the regression to possible database connection exhaustion and identifies missing query plans.
3. Open **Approvals**. Review the rollback, restart and scaling recommendations, then decide one action. Refresh the page and find its action ID in the audit trail. Execution stays unexecuted and the incident remains investigating.
4. Open **PayFlow lab**. Submit a payment, enable **Database unavailable**, and submit again. Retrieve the failed receipt by ID. Disable the fault and submit once more to observe a successful payment. These requests exercise PayFlow independently of the seeded incident.

[Incident fixture](backend/api/app/seed.py) · [Decision policy](backend/api/app/services/incidents.py) · [Payment fault behavior](applications/payflow/payment-service/app/services/payments.py)

## Architecture

```mermaid
flowchart TB
    U[Operator] --> D[React + TypeScript Dashboard]

    D --> O[SentinelOps FastAPI :8000]
    D --> P[PayFlow FastAPI :8001]

    O --> IS[Incident Store]
    O --> AU[Audit Store]
    O --> SE[Seeded Incident Scenario]

    P --> PS[Payment Store]
    P --> FS[Fault Simulator]

    IS -. optional persistence .-> DB1[(SentinelOps PostgreSQL)]
    AU -. optional persistence .-> DB1
    PS -. optional persistence .-> DB2[(PayFlow PostgreSQL)]
```

The browser calls each API independently. PostgreSQL mode commits the decision, timeline change and audit entry in one transaction under a row lock. PayFlow stores each completed payment attempt separately. [Architecture notes](docs/architecture.md) · [Dashboard HTTP client](dashboard/src/services/api.ts)

## Technology stack and responsibility

| Technology | Responsibility |
|---|---|
| React 19 | Dashboard interface |
| TypeScript | Frontend type safety |
| Vite | Frontend development and build |
| Tailwind CSS | UI styling |
| Python | Backend development |
| FastAPI | REST APIs |
| Pydantic | Request and response validation |
| SQLAlchemy | Database access |
| Alembic | Database migrations |
| PostgreSQL | Optional persistent storage |
| Pytest | Backend testing |
| Vitest | Frontend unit testing |
| Playwright | Browser-based end-to-end testing |

## Screenshots

### Operations overview

![Operations overview with the critical incident, latency chart, service health and payment activity](docs/assets/overview.png)

Both local APIs are online and PayFlow has recorded one test request. The reliability indicators describe the seeded incident window.

### Incident investigation

![SNT-001 timeline, probable cause, alternative hypotheses, runbooks and supporting evidence](docs/assets/incident-investigation.png)

The SNT-001 timeline places the deployment before the latency increase. The seeded investigation identifies missing query plans and suggests checks for connection pool exhaustion.

### Approvals and audit

![Recovery requests with approve and reject controls above the recorded decision in the audit trail](docs/assets/approvals-audit.png)

The operator approved the rollback recommendation. The audit row records the decision and shows execution as unexecuted. Two other requests await review.

### PayFlow lab

![Test payment form, fault switches, transaction lookup and a successful payment receipt](docs/assets/payflow-lab.png)

A test payment was submitted and retrieved by ID with all three simulated faults switched off.

## Local setup prerequisites

- Windows 11 with WSL2 Ubuntu, or a compatible Linux environment.
- Python 3.11 or newer.
- Node.js 22.12 or newer.
- npm.
- Git.

PostgreSQL is optional for the in-memory demonstration.

## Installation

### Clone the repository

The current Playwright configuration expects the repository at `~/sentinelops`.

```bash
git clone https://github.com/darshsoam07/SentinelOps.git ~/sentinelops
cd ~/sentinelops
```

### Step 2 — Create the Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip

python -m pip install \
  -e ./shared -r backend/api/requirements-dev.txt \
  -r applications/payflow/payment-service/requirements-dev.txt
```

### Step 3 — Install frontend dependencies

```bash
cd ~/sentinelops/dashboard

npm ci

test -f .env || cp .env.example .env
```

### Configure operator sign-in

From the repository root, run the setup once and choose your operator password.

```bash
cd ~/sentinelops
.venv/bin/python scripts/setup-auth.py
```

The script creates an Ed25519 pair in the ignored .keys directory and writes operator settings to .env.auth. Only SentinelOps needs the signing key. For an existing installation, generate the pair once with `.venv/bin/python scripts/generate-keys.py` and replace the old JWT secret setting with the public and private key file paths. Sign in at the dashboard as `operator`. Each login lasts 15 minutes. The dashboard keeps the token in localStorage across reloads. Signing out or receiving HTTP 401 clears it and returns the operator to /login.

## Starting all three applications

Open three Ubuntu terminals.

**Terminal 1 — PayFlow API**

```bash
cd ~/sentinelops/applications/payflow/payment-service

source ~/sentinelops/.venv/bin/activate
export SENTINELOPS_PUBLIC_KEY_FILE=~/sentinelops/.keys/public.pem

uvicorn app.main:app --reload --port 8001
```

**Terminal 2 — SentinelOps API**

```bash
cd ~/sentinelops/backend/api

source ~/sentinelops/.venv/bin/activate
source ~/sentinelops/.env.auth

uvicorn app.main:app --reload --port 8000
```

**Terminal 3 — React dashboard**

```bash
cd ~/sentinelops/dashboard

npm run dev
```

## Application URLs

| Component | URL |
|---|---|
| React dashboard | http://localhost:5173 |
| SentinelOps API | http://localhost:8000 |
| SentinelOps Swagger docs | http://localhost:8000/docs |
| PayFlow API | http://localhost:8001 |
| PayFlow Swagger docs | http://localhost:8001/docs |

## Optional PostgreSQL persistence

By default, the applications use their in-memory stores.

To enable PostgreSQL persistence in WSL2 Ubuntu:

```bash
sudo apt update
sudo apt install -y postgresql openssl

sudo service postgresql start

cd ~/sentinelops

bash scripts/setup-postgres.sh
```

The script creates separate database users and databases for SentinelOps and PayFlow, generates local connection settings in `.env.postgres`, and applies the Alembic migrations.

Before starting each API, source the connection settings:

```bash
source ~/sentinelops/.env.postgres
```

With PostgreSQL enabled, payment receipts, incident decisions, timelines and audit records survive application restarts.

To verify persistence:

```bash
cd ~/sentinelops

source .venv/bin/activate
source .env.postgres

python scripts/test-persistence.py
```

The persistence test uses isolated PostgreSQL schemas and removes its test data afterward.

The setup script runs `alembic upgrade head` from each API directory using the root virtual environment. Keep the generated connection settings outside Git. [Database setup](scripts/setup-postgres.sh)

## API reference

Business routes in the tables below are available under `/api/v1` and at their original paths. Both require the same bearer token. Health checks are public. Use the SentinelOps Swagger **Authorize** control or POST form fields `username` and `password` to `/api/v1/auth/login` on port 8000. Send the returned token in `Authorization: Bearer <token>` to either API. `GET /api/v1/users/me` returns the signed-in operator.

### SentinelOps API — Port 8000

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/incidents` | List incidents |
| GET | `/incidents/{id}` | Retrieve incident details |
| POST | `/incidents/{id}/approve` | Approve a proposed action |
| POST | `/incidents/{id}/reject` | Reject a proposed action |
| GET | `/audit-logs` | Retrieve audit events |
| GET | `/metrics/summary` | Retrieve seeded reliability summary |

Approval and rejection request example:

```json
{
  "action_id": "ACT-001",
  "note": "Reviewed the recommendation"
}
```

### PayFlow API — Port 8001

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/payments` | Create payment |
| GET | `/payments` | List payment transactions |
| GET | `/payments/{id}` | Retrieve a payment |
| GET | `/simulation/faults` | Retrieve fault configuration |
| POST | `/simulation/faults` | Enable or disable a fault |

## Running tests

### Backend tests

```bash
cd ~/sentinelops

source .venv/bin/activate

(cd backend/api && python -m pytest -q)

(cd applications/payflow/payment-service && python -m pytest -q)
```

### Frontend tests and build

```bash
cd ~/sentinelops/dashboard

npm test

npm run build
```

### End-to-end browser tests

From the dashboard directory, install Chromium:

```bash
cd ~/sentinelops/dashboard
npx playwright install --with-deps chromium
```

Run the browser tests:

```bash
cd ~/sentinelops/dashboard
env -u SENTINELOPS_DATABASE_URL -u PAYFLOW_DATABASE_URL npm run test:e2e
```

Playwright starts isolated test services on ports 8100, 8101 and 5174 so that browser tests do not mutate the normal development workspace.

## Repository structure

```text
SentinelOps/
│
├── applications/
│   └── payflow/
│       └── payment-service/
│           ├── app/
│           ├── alembic/
│           └── tests/
│
├── backend/
│   └── api/
│       ├── app/
│       ├── alembic/
│       └── tests/
│
├── dashboard/
│   ├── src/
│   │   ├── pages/
│   │   └── services/
│   └── tests/
│
├── docs/
│   └── architecture.md
│
├── scripts/
│   ├── setup-postgres.sh
│   └── test-persistence.py
│
├── .gitignore
├── LICENSE
└── README.md
```

## Current limitations and security boundaries

The current application is a local development and demonstration project.

- Do not expose the APIs directly to the public internet.
- Authentication supports one configured operator.
- New decisions record the authenticated username. Existing audit records retain their original actor label.
- Fault switches are process-local.
- The incident and reliability scenario is seeded.
- Approved actions are not executed against Kubernetes.
- Do not use production payment or infrastructure data.

Only the database-fault clearance operation executes. Seeded restart, rollback and scale decisions remain audit-only. Operator lab controls still allow manual fault injection and cleanup.

SNT-001 uses deterministic evidence. Compose uses Prometheus for runtime metrics, Grafana for visualization and Alertmanager for incident creation and resolution. See the [three-to-five-minute demo](docs/demo-script.md).

## SentinelOps 2.0 roadmap

| Planned milestone | Engineering outcome |
|---|---|
| Container packaging | Run the two APIs, dashboard and databases with Docker Compose. |
| Observability and SLOs | Instrument PayFlow with OpenTelemetry, collect metrics in Prometheus, logs in Loki and traces in Tempo, and display measured reliability and error budgets in Grafana. |
| Incident correlation | Detect threshold breaches, group related events and calculate the affected services from a dependency map. |
| Evidence-based RCA | Collect incident-window evidence, retrieve runbooks and optionally use an LLM to synthesize hypotheses. |
| Kubernetes recovery | Deploy locally with Helm, execute an approved operation through restricted RBAC and verify recovery before resolving an incident. |
| Chaos engineering and replay | Run bounded experiments, clean up faults and replay the recorded incident timeline. |
| Delivery and cloud | Validate changes in GitHub Actions, reconcile deployments with Argo CD and provision an AWS environment with Terraform. |

## Contributing

Contributions and engineering suggestions are welcome.

Before proposing a change:

1. Understand the existing service boundaries.
2. Keep the SentinelOps API and PayFlow responsibilities separate.
3. Add tests for changed behavior.
4. Update documentation when API contracts or setup instructions change.

## License

Licensed under the [MIT License](LICENSE).

## Docker Compose

Generate the signing pair once with `.venv/bin/python scripts/generate-keys.py` if setup-auth has not already created it. Copy `.env.example` to `.env`. Supply independent random values for the database, Grafana, webhook and executor credentials. Copy the operator name and Argon2 password hash from .env.auth and single-quote the hash in .env to preserve its dollar signs. Both APIs run as non-root and Compose mounts only the public verification key into PayFlow.

```sh
docker compose up --build -d
```

Open http://localhost:8080. Each API migrates its own database before serving requests. Both APIs expose `/health`, `/ready` and Prometheus counters at `/metrics`. Payments and audit lists return the latest 50 records by default (`?limit=1` through `100`). Login allows ten attempts per minute per client address per API process. Only SentinelOps signs operator tokens.

Grafana at http://localhost:3000 provisions the SentinelOps service health dashboard. Prometheus scrapes both APIs every five seconds. The overview reads PayFlow request rate, server error rate and p95 latency from Prometheus. A firing payment-error or high-latency alert creates one incident per fingerprint and firing episode. Local launches without Prometheus use labelled seed data.

The login limiter uses the ASGI client address, per process, per client address. Multiple workers have independent quotas. Configure Uvicorn's forwarded-header trust only for known reverse proxy addresses. The metrics endpoints are unauthenticated. Keep the API listeners on loopback or a private network and exclude /metrics from public reverse-proxy routes.

[Local fault detection trials, clock definition and reproduction commands](docs/detection-trials.md)
