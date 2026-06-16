# Quick Start — Docker Compose

This guide gets the full pykesys-redfish stack running in under 5 minutes using Docker Compose. You will have a live fleet dashboard, 10 emulated BMC nodes, background polling, and alert evaluation — no physical hardware required.

For non-Docker setup see [guide-admin.md — Local development](guide-admin.md#local-development).

---

## Prerequisites

| Requirement | Minimum version | Check |
|-------------|----------------|-------|
| Docker Desktop or Docker Engine | 24+ | `docker --version` |
| Docker Compose (plugin) | v2.20+ | `docker compose version` |
| Free ports | 8000 (web), 8888 (emulator) | `lsof -i :8000 -i :8888` |

---

## 1 — Clone and enter the repo

```bash
git clone <repo-url> pykesys-redfish
cd pykesys-redfish
```

---

## 2 — Build the React SPA (one-time)

The Vite build runs **outside** Docker so the compiled assets are available for Django to serve.

```bash
cd frontend
npm install
npm run build          # outputs to redfish_web/staticfiles/spa/
cd ..
```

> Skip this if you only want the API and don't need the web UI. Django still works without it.

---

## 3 — Start the stack

```bash
docker compose up
```

Docker Compose builds two images (first run takes 1–3 minutes) and starts:

| Service | What it does | Default URL |
|---------|-------------|-------------|
| `emulator` | FastAPI Redfish emulator — 10 virtual BMC nodes | `http://localhost:8888` |
| `web` | Django REST API + APScheduler + static SPA | `http://localhost:8000` |

On startup the web container automatically:
1. Runs `python manage.py migrate`
2. Runs `python manage.py init_emulator_hosts` — registers all 10 emulator nodes as `BMCHost` records
3. Starts the Django dev server
4. APScheduler begins polling the emulator nodes every 60 seconds

To run in the background:

```bash
docker compose up -d
docker compose logs -f          # follow all logs
docker compose logs -f web      # follow only web logs
```

---

## 4 — Verify everything is up

```bash
# Emulator health
curl http://localhost:8888/healthz
# → {"status":"ok","nodes":[1,2,3,4,5,6,7,8,9,10]}

# Fleet API — all 10 hosts with latest snapshot
curl http://localhost:8000/api/fleet/
# → [{host: "http://emulator:8888/bmc/1", latest_snapshot: {...}}, ...]
```

Open the dashboard: **http://localhost:8000**

You should see a 10-node grid, all green (health OK, power On).

---

## 5 — Try the Sim control API

Inject a failure scenario to see how the dashboard and alerts respond.

```bash
# Put nodes 2 and 3 into a degraded state
curl -X POST http://localhost:8888/sim/scenario \
  -H "Content-Type: application/json" \
  -d '{"name": "degraded", "nodes": [2, 3]}'

# Put node 5 into a critical state
curl -X POST http://localhost:8888/sim/scenario \
  -H "Content-Type: application/json" \
  -d '{"name": "critical", "nodes": [5]}'
```

Trigger an immediate poll to see the changes without waiting for the scheduler:

```bash
curl -X POST http://localhost:8000/api/hosts/2/poll/
curl -X POST http://localhost:8000/api/hosts/3/poll/
curl -X POST http://localhost:8000/api/hosts/5/poll/
```

Refresh the dashboard — nodes 2, 3, and 5 should now show Warning or Critical.

Reset everything:

```bash
curl -X POST http://localhost:8888/sim/reset
```

---

## 6 — Create an alert rule

Alert rules evaluate automatically after every poll. Create one that fires when a node's health becomes Critical:

```bash
curl -X POST http://localhost:8000/api/alerts/rules/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Node health critical",
    "field": "health",
    "operator": "eq",
    "value": "Critical",
    "severity": "critical",
    "enabled": true
  }'
```

Now apply the critical scenario to node 1 and trigger a poll:

```bash
curl -X POST http://localhost:8888/sim/scenario \
  -H "Content-Type: application/json" \
  -d '{"name": "critical", "nodes": [1]}'

curl -X POST http://localhost:8000/api/hosts/1/poll/
```

Check for open alert events:

```bash
curl "http://localhost:8000/api/alerts/events/?open=true"
```

The Alerts page at **http://localhost:8000/alerts** should show the open event.

---

## 7 — Try the CLI against the emulator

```bash
# Set credentials
export RF_HOST=http://localhost:8888/bmc/1
export RF_USER=admin
export RF_PASS=redfish

# System summary
uv run rf info

# Power status
uv run rf power status

# Set one-time PXE boot
uv run rf boot once Pxe

# View SEL logs (empty until you inject events)
uv run rf logs list
```

---

## 8 — Add a real BMC host (optional)

If you have a real BMC on your network, register it alongside the emulator nodes:

```bash
curl -X POST http://localhost:8000/api/hosts/ \
  -H "Content-Type: application/json" \
  -d '{
    "host": "https://192.168.1.100",
    "display_name": "My Server",
    "username": "admin",
    "password": "bmc-password",
    "verify_ssl": false,
    "poll_interval": 300,
    "enabled": true
  }'
```

The web app will start polling it on the next scheduler cycle (within 60 seconds).

---

## Common Docker Compose Operations

```bash
# View running services
docker compose ps

# Restart a single service
docker compose restart web
docker compose restart emulator

# Rebuild after code changes
docker compose up --build

# Stop and remove containers (keeps the DB volume)
docker compose down

# Stop and remove everything including the database
docker compose down -v

# Open a Django shell
docker compose exec web python manage.py shell

# Run Django management commands
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py migrate

# Run the integration test suite against the running emulator
docker compose up emulator -d
EMULATOR_URL=http://localhost:8888 pytest tests/integration/ -v

# CI pipeline (emulator + tests in Docker, no host dependencies)
docker compose -f docker-compose.ci.yml up \
  --abort-on-container-exit \
  --exit-code-from tests
```

---

## Services at a Glance

| URL | What you'll find |
|-----|-----------------|
| `http://localhost:8000` | Fleet dashboard SPA |
| `http://localhost:8000/api/fleet/` | Fleet summary JSON |
| `http://localhost:8000/api/hosts/` | Host CRUD API |
| `http://localhost:8000/api/alerts/rules/` | Alert rules API |
| `http://localhost:8000/admin/` | Django admin (requires superuser) |
| `http://localhost:8888/healthz` | Emulator health |
| `http://localhost:8888/docs` | Emulator OpenAPI / Swagger UI |
| `http://localhost:8888/sim/nodes/` | All emulator node states |
| `http://localhost:8888/sim/scenarios/` | Available scenarios |

---

## Next Steps

| I want to… | Where to look |
|------------|--------------|
| Understand the Redfish protocol | [docs/redfish.md](redfish.md) |
| Use the Python SDK in a script | [docs/sdk.md](sdk.md) |
| Run fleet-wide operations | [docs/fleet.md](fleet.md) |
| Use the `rf` CLI in depth | [docs/cli.md](cli.md) |
| Configure production deployment | [docs/guide-admin.md](guide-admin.md) |
| Use the Sim API to inject scenarios | [docs/emulator.md](emulator.md) |
| Understand the system architecture | [docs/architecture.md](architecture.md) |
