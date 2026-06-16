# pykesys-redfish Memory

## Project Identity

- **Repo**: pykesys-redfish — Python SDK, CLI, and fleet automation for the Redfish BMC management API
- **Branch**: main
- **Role**: Law-mother (constitutional source, full adoption 2026-06-11)
- **Seeded from**: ../template-law-claude

## Constitutional State

- **30 laws active** (LAW 0-29)
- 6 Universal Principles
- 5 Cornerstones + deepenings
- Four Books: LAW / ACTION / RE-ACTION / EPIPHANIES
- 41 constitutional service units (.claude/.init/)

## Architecture

Three-tier stack:
- **Python SDK** (`src/pykesys_redfish/`) — core Redfish HTTP client, session management (path-prefix base URL support), typed resource wrappers, fleet automation, `rf` CLI
- **Django web backend** (`redfish_web/`) — REST API + APScheduler, SQLite, hosts/inventory/alerts/scheduler apps
- **React frontend** (`frontend/`) — Vite/React 18 SPA ("redfish-observability"), Tailwind CSS
- **Emulator** (`emulator/`) — FastAPI 10-node Redfish emulator, `/sim/` control API, 3 scenarios

## Key Design Decisions

- `RedfishClient` is a context manager; `RedfishSession` owns the httpx transport
- `RedfishSession` extracts path prefix from `base_url` (e.g. `/bmc/1`) and prepends to every URI — enables multi-node emulator routing without API changes
- Resources are lazy-loading with `_data` cache + `refresh()` invalidation
- Both session-token and HTTP Basic auth supported
- Fleet operations use `ThreadPoolExecutor`; each worker gets isolated client
- Tests mock at httpx transport layer via `respx` — no real BMCs needed
- Emulator node URLs: `http://localhost:8888/bmc/{1..10}` — path-prefix handled transparently by SDK

## Last Significant Change

2026-06-16 — Session 2: Full project build:
- SDK, CLI, FleetManager, Django web app, React SPA, FastAPI emulator, Docker compose stack
- `session.py` path-prefix base URL — backward-compatible, enables multi-node emulator
- 27 SDK unit tests + 33 integration tests passing
- Ladder run: caught missing `docs/prompts.md` (LAW 1) + 9 docs files missing TOC/BTT — all fixed
