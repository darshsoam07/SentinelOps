# SentinelOps

SentinelOps is a local reliability engineering workspace for investigating a payment-service regression. Operators can follow evidence from deployment to detection, evaluate recovery recommendations, and exercise a separate payment API under controlled faults.

## WSL2 Ubuntu setup

Use Python 3.11+ and Node 22.12+ with npm. This checkout was built in Ubuntu with Python 3.14 and Node 22. Run these commands in Ubuntu.

```bash
cd ~/sentinelops
pwd
git status --short --branch
find applications backend dashboard/src docs -type f | sort
python3 --version
node --version
npm --version
# On a fresh Ubuntu installation with missing prerequisites:
# sudo apt update && sudo apt install python3-venv nodejs npm
test -x .venv/bin/python || python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/api/requirements-dev.txt -r applications/payflow/payment-service/requirements-dev.txt
cd dashboard
npm ci
test -f .env || cp .env.example .env
npx playwright install --with-deps chromium
```

The dashboard source and Vite configuration are included. The environment file selects the SentinelOps and PayFlow base URLs. Both APIs allow the dashboard origin through CORS. Override DASHBOARD_ORIGINS with a comma-separated list when changing the frontend port.

## PostgreSQL persistence (M1)

Install PostgreSQL in Ubuntu and run the setup script from the repository root. It creates one login and database per service and applies both Alembic migrations. Local credentials live in the Git-ignored .env.postgres file.

```bash
sudo apt install postgresql openssl
sudo service postgresql start
cd ~/sentinelops
bash scripts/setup-postgres.sh
source .env.postgres
.venv/bin/python scripts/test-persistence.py
```

Source the connection settings in each API terminal as shown below. With the settings omitted, the APIs use the in-memory demo. Fault switches and their counters are process-local in both modes. The persistence test uses isolated schemas and removes its own fixtures.

## Start the workspace

Open three Ubuntu terminals. Use Ctrl+C in each to stop its process.

**Terminal 1 / PayFlow**

```bash
cd ~/sentinelops/applications/payflow/payment-service
source ~/sentinelops/.venv/bin/activate
source ~/sentinelops/.env.postgres
uvicorn app.main:app --reload --port 8001
```

**Terminal 2 / SentinelOps API**

```bash
cd ~/sentinelops/backend/api
source ~/sentinelops/.venv/bin/activate
source ~/sentinelops/.env.postgres
uvicorn app.main:app --reload --port 8000
```

**Terminal 3 / dashboard**

```bash
cd ~/sentinelops/dashboard
npm run dev
```

## Verify in a browser

Open http://localhost:5173 in Windows. Check that both services show Online. Open SNT-001, inspect its timeline and evidence, then follow Review recommended actions. Approve one action and reject another. Reload and inspect both audit entries. In PayFlow lab, submit a payment, retrieve its ID, enable Database unavailable and submit again. The failed receipt remains available. Disable the switch and submit another payment to confirm recovery.

```bash
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8001/health
curl -fsS http://localhost:5173/ >/dev/null
```

## API contracts

Interactive schemas and example bodies are available at http://localhost:8000/docs and http://localhost:8001/docs.

| Service | Method and path | Result |
|---|---|---|
| Both | GET /health | Process health |
| SentinelOps | GET /incidents | Incident list with nested actions and investigation |
| SentinelOps | GET /incidents/{id} | Detail including UTC timeline and simulated evidence |
| SentinelOps | POST /incidents/{id}/approve or /reject | Updated incident. Body contains action_id and optional note |
| SentinelOps | GET /audit-logs | Most recent events first |
| SentinelOps | GET /metrics/summary | Seeded metrics, latency series and incident counts |
| PayFlow | POST /payments | Submit positive amount and uppercase three-letter currency. Returns a UUID receipt |
| PayFlow | GET /payments or /payments/{id} | Recent transactions or a single receipt |
| PayFlow | GET /simulation/faults | Three boolean flags |
| PayFlow | POST /simulation/faults | Set one flag with fault and enabled. Returns all flags |

Missing records return 404. Invalid inputs return 422. Policy violations return 403 and incompatible or repeated decisions return 409. Successful payments return 201. Injected processing failures return 500 and simulated database outages return 503, both with a stored failed receipt.

## Tests

```bash
cd ~/sentinelops
source .venv/bin/activate
(cd backend/api && python -m pytest -q)
(cd applications/payflow/payment-service && python -m pytest -q)
cd dashboard
npm test
npm run build
npm run test:e2e
```

Browser tests launch their own Vite and API processes on ports 5174, 8100 and 8101. Test mutations stay in those processes.

## Repository and roadmap

- **dashboard/** contains the React, TypeScript, Vite and Tailwind workspace, HTTP client, pages and browser tests.
- **backend/api/** owns incident records, evidence, decision policy and audit history.
- **applications/payflow/payment-service/** owns payments and the fault simulator.
- **docs/architecture.md** describes data flow, metric provenance and future integrations.

In PostgreSQL mode, receipts, incidents, decisions, timelines and audits survive restarts. Operator identity is a demo label. Future phases cover PostgreSQL, cloud delivery, observability, model-backed investigation and restricted recovery execution. See [architecture](docs/architecture.md).
