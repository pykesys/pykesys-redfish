# pykesys-redfish

Python SDK, CLI, fleet automation framework, and web observability platform for the DMTF Redfish BMC management API.

This project is intended to create an observability and control application to facilitate the management of an Nvidia DGX SuperPod — providing unified BMC access, real-time health monitoring, alerting, and fleet-scale power and boot control across the pod's compute nodes.

## Table of Contents

- [Project Layout](#project-layout)
- [Documentation](#documentation)
- [Scripts](#scripts)
- [Setup](#setup)
- [Docker — Full Stack](#docker--full-stack)
- [Running Tests](#running-tests)
- [SDK Quick Start](#sdk-quick-start)
- [Emulator Sim API](#emulator-sim-api-inject-test-scenarios)
- [Constitutional Governance](#constitutional-governance)
- [Environment Variables](#environment-variables)

---

## Project Layout

```
pykesys-redfish/
├── src/pykesys_redfish/     Python SDK + CLI + fleet library
│   ├── client.py            RedfishClient — core HTTP + session management
│   ├── session.py           Session token lifecycle (supports path-prefix base URLs)
│   ├── exceptions.py        RedfishError hierarchy
│   ├── resources/           Typed resource wrappers (ComputerSystem, Chassis, …)
│   ├── cli/                 `rf` CLI (Typer + Rich)
│   └── fleet/               FleetManager for concurrent multi-BMC operations
├── redfish_web/             Django 4.2 observability web app
│   ├── hosts/               BMC host registry + CRUD
│   ├── inventory/           Snapshot, sensor, and log storage
│   ├── alerts/              Alert rules, events, and Slack notifications
│   └── scheduler/           APScheduler background polling
├── frontend/                React 18 + Vite + Tailwind SPA
├── emulator/                Redfish BMC emulator (FastAPI, 10 virtual nodes)
├── tests/                   SDK unit tests (pytest + respx)
├── tests/integration/       Integration tests against the live emulator
├── docker-compose.yml       Full stack: emulator + Django web app
├── docker-compose.ci.yml    CI: emulator + integration test runner
└── docs/                    All documentation
```

[↑ Back to Top](#table-of-contents)

---

## Documentation

### Project docs

| Document | Description |
|----------|-------------|
| [docs/architecture.md](docs/architecture.md) | Full system architecture — component diagrams, data flow, deployment topologies, security |
| [docs/redfish.md](docs/redfish.md) | Redfish protocol overview — resource model, OData, transport, vendor implementations |
| [docs/sdk.md](docs/sdk.md) | SDK full reference — RedfishClient, all resource classes, FleetManager, exceptions, auth modes, path-prefix URLs, error handling patterns, recipes |
| [docs/cli.md](docs/cli.md) | `rf` CLI command reference — all subcommands with examples |
| [docs/fleet.md](docs/fleet.md) | Fleet automation guide — FleetManager API, bulk ops, CSV/JSON export |
| [docs/emulator.md](docs/emulator.md) | Emulator guide — architecture, node defaults, Redfish coverage, Sim API, scenarios |
| [docs/guide-users.md](docs/guide-users.md) | User guide — web dashboard, REST API, `rf` CLI, Python SDK, curl-based Redfish operations, scripting patterns |
| [docs/guide-admin.md](docs/guide-admin.md) | Admin guide — web app deployment, BMC host management, alert rules, APScheduler, security hardening, firmware lifecycle, LDAP, vendor notes |
| [docs/project-plan-sdk.md](docs/project-plan-sdk.md) | SDK project plan — v0.1 delivered + milestones v0.2–v0.5 |
| [docs/project-plan-web.md](docs/project-plan-web.md) | Web app project plan — v0.1 delivered + milestones v0.2–v0.5 |

### Scripts docs

| Document | Description |
|----------|-------------|
| [docs/scripts.md](docs/scripts.md) | Scripts overview — which script to use and when |
| [docs/run-sh.md](docs/run-sh.md) | `run.sh` — production gunicorn startup |
| [docs/run-dashboard-sh.md](docs/run-dashboard-sh.md) | `run-dashboard.sh` — interactive development launcher |
| [docs/run-tests-local-sh.md](docs/run-tests-local-sh.md) | `run_tests_local.sh` — local test runner |
| [docs/runtests-sh.md](docs/runtests-sh.md) | `runtests.sh` — CI full-suite runner |

[↑ Back to Top](#table-of-contents)

---

## Scripts

Four shell scripts handle everything from day-to-day development to CI:

| Script | Purpose |
|--------|---------|
| `./run.sh` | Start Django via gunicorn (production/staging) |
| `./run-dashboard.sh` | Interactive menu — services, tests, Docker, Django shell |
| `./run_tests_local.sh` | Run SDK / Django / integration tests locally |
| `./runtests.sh` | Run all three suites in sequence (CI / pre-push) |

```bash
# Start all three services in background
./run-dashboard.sh all

# Run SDK unit tests only
./run_tests_local.sh sdk

# Rerun only failed tests
./run_tests_local.sh --failed

# Full CI suite
./runtests.sh
```

See [docs/scripts.md](docs/scripts.md) for the full reference and individual man pages.

[↑ Back to Top](#table-of-contents)

---

## Setup

### SDK + CLI

```bash
uv sync --extra dev
uv run rf --help
```

### Web App

```bash
cd redfish_web
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### Frontend (dev)

```bash
cd frontend
npm install
npm run dev       # http://localhost:5173 (proxies /api → Django :8000)
```

### Emulator (standalone)

```bash
cd emulator
pip install -r requirements.txt
NUM_NODES=10 uvicorn main:app --port 8888 --reload
```

[↑ Back to Top](#table-of-contents)

---

## Docker — Full Stack

```bash
# Start emulator + Django web app
docker compose up

# Django API + SPA:  http://localhost:8000
# Emulator API:      http://localhost:8888
# Emulator Docs:     http://localhost:8888/docs
```

The web app auto-registers 10 emulator nodes as BMCHost records on startup. The fleet dashboard immediately shows all 10 nodes.

[↑ Back to Top](#table-of-contents)

---

## Running Tests

### SDK unit tests

```bash
uv run pytest
```

### Django tests

```bash
cd redfish_web
pytest
```

### Integration tests (requires running emulator)

```bash
# Start emulator
docker compose up emulator

# Run integration tests
EMULATOR_URL=http://localhost:8888 pytest tests/integration/ -v
```

### CI (Docker — emulator + integration tests)

```bash
docker compose -f docker-compose.ci.yml up \
  --abort-on-container-exit \
  --exit-code-from tests
```

[↑ Back to Top](#table-of-contents)

---

## SDK Quick Start

```python
from pykesys_redfish import RedfishClient

# Single BMC
with RedfishClient("https://192.168.1.100", "admin", "password") as rf:
    system = rf.system()
    print(system.power_state, system.health)
    system.graceful_restart()

# Against the emulator
with RedfishClient("http://localhost:8888/bmc/1", "admin", "redfish", verify_ssl=False) as rf:
    print(rf.system().summary())
```

### Fleet

```python
from pykesys_redfish.fleet import FleetManager

fm = FleetManager(
    hosts=[f"http://localhost:8888/bmc/{i}" for i in range(1, 11)],
    username="admin",
    password="redfish",
    verify_ssl=False,
)
inventory = fm.collect_inventory()
fm.export_csv(inventory, "inventory.csv")
print(fm.health_summary())
```

### CLI

```bash
export RF_HOST=http://localhost:8888/bmc/1
export RF_USER=admin
export RF_PASS=redfish

uv run rf info
uv run rf power status
uv run rf power reset --type GracefulRestart
uv run rf boot once Pxe
uv run rf logs list
uv run rf firmware list
```

[↑ Back to Top](#table-of-contents)

---

## Emulator Sim API (inject test scenarios)

```bash
# Apply degraded scenario to nodes 1–3
curl -X POST http://localhost:8888/sim/scenario \
  -H "Content-Type: application/json" \
  -d '{"name": "degraded", "nodes": [1, 2, 3]}'

# Inject a critical SEL event on node 5
curl -X POST http://localhost:8888/sim/nodes/5/sel-event \
  -H "Content-Type: application/json" \
  -d '{"severity": "Critical", "message": "PSU2 failed"}'

# Reset everything
curl -X POST http://localhost:8888/sim/reset
```

See [docs/emulator.md](docs/emulator.md) for the full Sim API reference.

[↑ Back to Top](#table-of-contents)

---

## Constitutional Governance

pykesys-redfish is a **Law Mother** — it carries a full copy of the Constitutional Law Claude
governance framework seeded from
[template-law-claude](../template-law-claude) on 2026-06-11.

The framework provides:

- **30 constitutional laws** (LAW 0-29) governing development practices — session continuity,
  audit trail, documentation, git discipline, testing, sacred proportion, and more.
  See `.claude/PROJECT_LAWS.md`.
- **Enforcement hooks** — a Stop hook (`law-0-enforcer.sh`) that fires when Claude finishes a
  turn and checks that `SESSION_CONTEXT.md` is up to date; a session-loader hook that restores
  context at the start of every session.
- **Constitutional service units** — 41 init-style units in `.claude/.init/` (one per law +
  META-LAWs and Universal Principles), managed by `.claude/bin/law-manage.py`.
- **Slash commands** — `/ladder`, `/cascade`, `/lineage-setup`, `/repatriation`,
  `/daughter-cascade` for session coherence, cascade completion, and lineage management.
- **Project memory** — `MEMORY.md` at repo root (LAW 19); all accumulated knowledge lives here,
  tracked by git, read at every session start.
- **Accretion log** — `docs/accretion.md`; every meaningful session deposits a stratum (LAW 26).

### Key files

| File | Purpose |
|------|---------|
| `MEMORY.md` | Project memory — read first on every session restore |
| `.claude/PROJECT_LAWS.md` | The 30 constitutional laws |
| `.claude/SESSION_CONTEXT.md` | Session state, restoration instructions, ladder run log |
| `.claude/CONSTITUTION-VERSION.md` | Single source of truth for all constitutional counts |
| `.claude/LAW-LINEAGE.md` | Lineage declaration (`role: mother`) |
| `.claude/FOUNDATIONS.md` | 5 Cornerstones + deepenings |
| `.claude/LEXICON.md` | 6 Universal Principles |
| `docs/accretion.md` | Sedimentation record — session strata |

### Validate constitutional database

```bash
python3 .claude/bin/law-manage.py validate
```

### Daughter projects

Projects that inherit constitutional governance from pykesys-redfish place a
`.claude/LAW-LINEAGE.md` in their repo:

```yaml
role: daughter
project: my-project
mother_path: ../pykesys-redfish
mother_name: pykesys-redfish
adoption_model: lightweight   # or full
adopted: YYYY-MM-DD
```

Then run `/lineage-setup daughter` in Claude Code to complete the setup.

[↑ Back to Top](#table-of-contents)

---

## Environment Variables

### SDK / CLI

| Variable | Description |
|----------|-------------|
| `RF_HOST` | Default BMC base URL (e.g. `http://localhost:8888/bmc/1`) |
| `RF_USER` | Default username |
| `RF_PASS` | Default password |
| `RF_VERIFY_SSL` | Set `false` to skip TLS verification |

### Web App

| Variable | Description |
|----------|-------------|
| `DJANGO_SECRET_KEY` | Django secret key (required in production) |
| `DEBUG` | `true` / `false` |
| `EMULATOR_URL` | Base URL of the emulator (e.g. `http://emulator:8888`) |
| `EMULATOR_NUM_NODES` | Number of nodes to register on startup (default: `10`) |
| `EMULATOR_ADMIN_USER` | Emulator admin username (default: `admin`) |
| `EMULATOR_ADMIN_PASS` | Emulator admin password (default: `redfish`) |

### Emulator

| Variable | Description |
|----------|-------------|
| `NUM_NODES` | Number of virtual BMC nodes (default: `10`) |
| `ADMIN_USER` | Admin username for all nodes (default: `admin`) |
| `ADMIN_PASS` | Admin password for all nodes (default: `redfish`) |

[↑ Back to Top](#table-of-contents)
