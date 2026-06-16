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
- [Appendix — uv](#appendix--uv)

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
├── frontend/                React 18 + Vite SPA
├── emulator/                Redfish BMC emulator (FastAPI, 10 virtual nodes)
├── C++/                     C++ command-deck application (CMake + build scripts)
│   ├── CMakeLists.txt       Build definition (CUDA, SDL2, DDC/CI feature gates)
│   ├── Makefile             Convenience targets: make debug, cuda, full, asan…
│   ├── scripts/             setup-dev.sh, check-deps.sh, build.sh, install-cuda.sh
│   ├── src/                 Source skeleton: input, gesture, display, DDC, CUDA
│   └── .vscode/             VSCode tasks, launch configs, clangd settings
├── tests/                   SDK unit tests (pytest + respx)
├── tests/integration/       Integration tests against the live emulator
├── docker-compose.yml       Full stack: emulator + Django web app
└── docs/                    All documentation
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
| [docs/quickstart.md](docs/quickstart.md) | **Quick start** — Docker Compose walkthrough: build, start, verify, sim scenarios, CLI, add real hosts |
| [docs/architecture.md](docs/architecture.md) | Full system architecture — component diagrams, data flow, deployment topologies, security |
| [docs/touchscreen.md](docs/touchscreen.md) | **C++ touchscreen tutorial** — ViewSonic TD2423D on Linux: evdev MT protocol, libinput, gesture recognition, DRM/KMS, EGL/OpenGL, DDC/CI, CUDA interop, CMake |
| [docs/redfish.md](docs/redfish.md) | Redfish protocol overview — resource model, OData, transport, vendor implementations |
| [docs/sdk.md](docs/sdk.md) | SDK full reference — RedfishClient, all resource classes, FleetManager, exceptions, auth modes, path-prefix URLs, error handling patterns, recipes |
| [docs/cli.md](docs/cli.md) | `rf` CLI command reference — all subcommands with examples |
| [docs/fleet.md](docs/fleet.md) | Fleet automation guide — FleetManager API, bulk ops, CSV/JSON export |
| [docs/emulator.md](docs/emulator.md) | Emulator guide — architecture, node defaults, Redfish coverage, Sim API, scenarios |
| [docs/guide-users.md](docs/guide-users.md) | User guide — web dashboard, REST API, `rf` CLI, Python SDK, curl-based Redfish operations, scripting patterns |
| [docs/guide-admin.md](docs/guide-admin.md) | Admin guide — web app deployment, BMC host management, alert rules, APScheduler, security hardening, firmware lifecycle, LDAP, vendor notes |
| [docs/guide-bmc-images.md](docs/guide-bmc-images.md) | NVIDIA DGX BMC deep-dive — NOR flash layout, filesystem layers, A/B bank updates, ERoT, PLDM, secure boot chain |
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

> **See [docs/quickstart.md](docs/quickstart.md) for the complete walkthrough** — prerequisites, build steps, verifying the stack, injecting scenarios, creating alert rules, and common compose operations.

```bash
# Build the React SPA first (one-time)
cd frontend && npm install && npm run build && cd ..

# Start emulator + Django web app
docker compose up
```

| URL | What's there |
|-----|-------------|
| `http://localhost:8000` | Fleet dashboard (React SPA) |
| `http://localhost:8000/api/fleet/` | Fleet summary JSON |
| `http://localhost:8888` | Redfish emulator (10 nodes) |
| `http://localhost:8888/docs` | Emulator OpenAPI / Swagger UI |
| `http://localhost:8888/sim/nodes/` | Emulator node state |

The web app auto-registers 10 emulator nodes as BMCHost records on startup and begins polling them immediately.

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

---

## Appendix — uv

### What is uv?

`uv` is a Python package and project manager written in Rust, developed by [Astral](https://astral.sh) (the team behind the Ruff linter). It is a single binary that replaces the entire classic Python toolchain:

| Classic tool | uv equivalent |
|-------------|--------------|
| `pip` | `uv pip install` |
| `pip-tools` / `pip-compile` | `uv lock` / `uv sync` |
| `virtualenv` / `venv` | automatic (managed per-project) |
| `pyenv` | `uv python install` |
| `twine` | `uv publish` |

**Why it matters:** uv resolves and installs packages in a fraction of the time pip takes — typically 10–100× faster — because its resolver and downloader are fully parallelized and written in Rust. Cold installs that take 30 seconds with pip often complete in under 2 seconds with uv.

This project uses uv as the primary Python toolchain. The `uv.lock` file at the repo root is the fully-resolved, reproducible lock of all dependencies.

### Installing uv

```bash
# macOS / Linux (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh

# macOS via Homebrew
brew install uv

# pip (if you must bootstrap from pip)
pip install uv

# Verify
uv --version
```

uv installs as a single self-contained binary. No Python required to install uv itself.

### How uv is used in this project

#### pyproject.toml — project definition

```toml
[project]
name = "pykesys-redfish"
requires-python = ">=3.10"
dependencies = [
    "httpx>=0.27",
    "typer>=0.12",
    "rich>=13",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-cov",
    "respx>=0.21",
]

[project.scripts]
rf = "pykesys_redfish.cli.main:app"

[[tool.uv.index]]
url = "https://pypi.apple.com/simple"
default = true
```

uv reads `pyproject.toml` for all project metadata, dependencies, and index configuration.

#### uv.lock — reproducible lock file

`uv.lock` contains the fully-resolved dependency graph with exact versions and hashes for every package. It is committed to the repo and ensures every developer and CI run uses identical package versions.

Unlike `requirements.txt`, `uv.lock` is generated automatically and should never be edited by hand.

#### Key commands

```bash
# Install all dependencies (including dev extras) into a managed virtualenv
uv sync --extra dev

# Install only production dependencies
uv sync

# Run a command inside the project's virtualenv — no activation needed
uv run pytest
uv run rf --help
uv run python -c "import pykesys_redfish; print(pykesys_redfish.__version__)"

# Add a new runtime dependency
uv add httpx

# Add a dev-only dependency
uv add --dev black

# Remove a dependency
uv remove httpx

# Update all packages to latest compatible versions and regenerate lock
uv lock --upgrade

# Update a single package
uv lock --upgrade-package httpx

# Show the current environment
uv pip list
uv pip show httpx
```

#### The managed virtualenv

`uv sync` creates a `.venv/` directory at the project root. `uv run` automatically uses it — you never need to `source .venv/bin/activate`. If you prefer to activate it explicitly:

```bash
source .venv/bin/activate     # macOS / Linux
.venv\Scripts\activate        # Windows
```

#### Common workflows

```bash
# Fresh checkout — get everything ready in one command
git clone <repo>
cd pykesys-redfish
uv sync --extra dev

# Run the test suite
uv run pytest

# Run the CLI
uv run rf --help
export RF_HOST=http://localhost:8888/bmc/1
uv run rf info

# Add a dependency and commit the updated lock
uv add pydantic
git add pyproject.toml uv.lock
git commit -m "add pydantic dependency"

# Check for outdated packages
uv pip list --outdated

# Recreate virtualenv from scratch (if .venv is corrupted)
rm -rf .venv
uv sync --extra dev
```

### uv vs. pip — practical differences

| Task | pip | uv |
|------|-----|----|
| Install from requirements | `pip install -r requirements.txt` | `uv pip install -r requirements.txt` |
| Install project + dev deps | `pip install -e .[dev]` | `uv sync --extra dev` |
| Run a command in venv | `source .venv/bin/activate && pytest` | `uv run pytest` |
| Generate a lock file | `pip-compile` | `uv lock` |
| Install from lock file | `pip-sync` | `uv sync` |
| Add a dependency | Edit `requirements.txt`, `pip install` | `uv add <pkg>` |

`uv run <cmd>` is the idiomatic replacement for activating the venv and running a command. All scripts and CI in this project use `uv run`.

### Further reading

- uv documentation: `https://docs.astral.sh/uv/`
- uv GitHub: `https://github.com/astral-sh/uv`
- pyproject.toml spec: `https://packaging.python.org/en/latest/specifications/pyproject-toml/`

[↑ Back to Top](#table-of-contents)
