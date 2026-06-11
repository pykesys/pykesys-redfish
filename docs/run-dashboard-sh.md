# run-dashboard.sh

## Name

`run-dashboard.sh` — interactive development launcher for the pykesys-redfish stack

## Synopsis

```bash
./run-dashboard.sh [command]
```

## Description

`run-dashboard.sh` is the primary development launcher for pykesys-redfish. It provides an interactive numbered menu for starting and stopping the three project services (Django, React frontend, Redfish emulator), running tests, and managing Docker Compose. It can also be driven non-interactively by passing a command argument.

All three services can be started in the background simultaneously (`all` command), with PID files tracked in the project root (`.web.pid`, `.frontend.pid`, `.emulator.pid`). The `stop` command kills them all.

## Commands

| Command | Description |
|---------|-------------|
| `dev`, `development` | Start Django dev server on `$WEB_PORT` (default: 8000) |
| `frontend` | Start React Vite dev server on `$FRONTEND_PORT` (default: 5173) |
| `emulator` | Start Redfish BMC emulator on `$EMULATOR_PORT` (default: 8888) |
| `shell`, `console` | Open Django interactive Python shell |
| `migrate`, `migrations` | Run `makemigrations` + `migrate` |
| `test`, `tests` | Launch interactive categorized pytest runner |
| `all` | Start all three services in background, tail logs |
| `stop` | Kill all background services via PID files |
| `status` | Show running status and port checks |
| `docker-up` | `docker compose up` |
| `docker-down` | `docker compose down` |
| `docker-logs` | `docker compose logs -f` |
| `help`, `--help`, `-h` | Print command reference |

## Interactive menu

When invoked with no arguments, the script shows a numbered menu:

```
  Services:
   1) Run: Django Dev Server      (http://localhost:8000)
   2) Run: React Frontend         (http://localhost:5173)
   3) Run: Redfish Emulator       (http://localhost:8888)
   4) Run: All Services           (web + frontend + emulator in background)
   5) Stop: All Services
   6) Status: Services

  Django:
   7) Run: Django Shell
   8) Run: Migrations

  Testing:
   9) Run: SDK Unit Tests
  10) Run: Django Tests
  11) Run: Integration Tests
  12) Run: All Tests
  13) Run: Interactive pytest

  Docker Compose:
  14) Docker: Up
  15) Docker: Down
  16) Docker: Logs

  d) Toggle debug info display
  q) Quit
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_PORT` | `8000` | Django dev server port |
| `FRONTEND_PORT` | `5173` | React Vite dev server port |
| `EMULATOR_PORT` | `8888` | Redfish emulator port |

## Service URLs

| Service | URL |
|---------|-----|
| Django web app + SPA | `http://localhost:8000` |
| React dev server | `http://localhost:5173` |
| Redfish emulator | `http://localhost:8888` |
| Emulator OpenAPI docs | `http://localhost:8888/docs` |
| Django admin | `http://localhost:8000/admin/` |

## Background service management

The `all` command starts all three services and writes their PIDs to:

```
.web.pid
.frontend.pid
.emulator.pid
```

The `stop` command reads these files and sends SIGTERM to each process. `status` checks whether each PID is still alive and whether each port is listening.

## Interactive pytest runner (menu option 13)

The interactive test runner (`run_tests`) scans `tests/` for `test_*.py` files, groups them by the last underscore-delimited word in the filename (the "category"), and presents a two-level menu:

1. Select a category (e.g. `client`, `fleet`, `resources`)
2. Select an individual file or run all in category

Each test file runs with `uv run pytest <file> -v --no-cov` and produces a timestamped log in `log/`.

## Logging

All service output is tee'd to `log/`:

| File | Content |
|------|---------|
| `log/run-web.log` | Django dev server output |
| `log/run-frontend.log` | Vite dev server output |
| `log/run-emulator.log` | Emulator output |
| `log/run-migrations.log` | Migration output |
| `log/pytest-sdk-<date>.log` | SDK test run |
| `log/pytest-django-<date>.log` | Django test run |
| `log/pytest-integration-<date>.log` | Integration test run |

## Examples

```bash
# Interactive menu
./run-dashboard.sh

# Start just the Django dev server
./run-dashboard.sh dev

# Start all services in background and watch logs
./run-dashboard.sh all

# Check what's running
./run-dashboard.sh status

# Kill all background services
./run-dashboard.sh stop

# Run Django migrations
./run-dashboard.sh migrate

# Override service ports
WEB_PORT=9000 EMULATOR_PORT=9888 ./run-dashboard.sh all
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Clean exit (quit from menu or command completed) |
| 1 | Unknown command or service start failure |

## See also

- [run.sh](run-sh.md) — production gunicorn startup
- [run_tests_local.sh](run-tests-local-sh.md) — non-interactive test runner
- [runtests.sh](runtests-sh.md) — CI full-suite runner
- [emulator.md](emulator.md) — emulator reference
