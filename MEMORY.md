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
- **Python SDK** (`src/pykesys_redfish/`) — core Redfish HTTP client, session management, typed resource wrappers, fleet automation
- **Django web backend** (`redfish_web/`) — REST API + APScheduler, SQLite, hosts/inventory/alerts/scheduler apps
- **React frontend** (`frontend/`) — Vite/React 18 SPA ("redfish-observability"), Tailwind CSS

## Key Design Decisions

- `RedfishClient` is a context manager; `RedfishSession` owns the httpx transport
- Resources are lazy-loading with `_data` cache + `refresh()` invalidation
- Both session-token and HTTP Basic auth supported
- Fleet operations use `ThreadPoolExecutor`; each worker gets isolated client
- Tests mock at httpx transport layer via `respx` — no real BMCs needed

## Last Significant Change

2026-06-11 — Constitutional governance adopted (law-mother declaration). Five bugs fixed:
1. `client.py`: index OOB on empty collections → `_member_uri()` with `RedfishNotFoundError`
2. `session.py`: `RedfishTimeoutError` never raised → added `httpx.TimeoutException` handling
3. `client.py`: httpx.Client resource leak on failed `connect()` → `close()` now unconditional
4. `inventory/tasks.py`: failing host ignored `poll_interval` → `_mark_error()` updates `last_seen`
5. `output.py`: `str(None)` showed "None" in fleet table → coerce None before `or "—"` fallback
