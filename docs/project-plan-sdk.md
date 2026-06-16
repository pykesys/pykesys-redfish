# pykesys-redfish SDK — Project Plan & Milestones


[↑ Back to Top](#table-of-contents)

## Table of Contents

- [Overview](#overview)
- [Milestone v0.1 — Foundation ✅ (Delivered)](#milestone-v01--foundation--delivered)
- [Milestone v0.2 — Async Support & Performance](#milestone-v02--async-support--performance)
- [Milestone v0.3 — Extended Resource Coverage](#milestone-v03--extended-resource-coverage)
- [Milestone v0.4 — CLI Enhancements & Fleet-Level Commands](#milestone-v04--cli-enhancements--fleet-level-commands)
- [Milestone v0.5 — Observability Integrations & Exporter](#milestone-v05--observability-integrations--exporter)
- [Backlog / Out of Scope for Now](#backlog--out-of-scope-for-now)
- [Dependency Map](#dependency-map)

---


[↑ Back to Top](#table-of-contents)

## Overview

`pykesys-redfish` is a Python SDK, CLI, and fleet automation library for the DMTF Redfish BMC management API. This document tracks delivered milestones and planned enhancement phases.

---


[↑ Back to Top](#table-of-contents)

## Milestone v0.1 — Foundation ✅ (Delivered)

**Goal:** Working SDK, CLI, and fleet module with full test coverage.

### Delivered
- `RedfishClient` — context-manager HTTP client with session token auth, Basic auth fallback, TLS control
- Exception hierarchy: `RedfishAuthError`, `RedfishNotFoundError`, `RedfishConflictError`, `RedfishServerError`, `RedfishTimeoutError`
- Resource classes: `ComputerSystem`, `Chassis`, `Manager`, `Storage`, `Drive`, `AccountService`
- `ComputerSystem` actions: power on/off/reset, graceful shutdown/restart, NMI, boot override, UID LED
- `rf` CLI (Typer + Rich): `info`, `power`, `boot`, `logs`, `firmware`, `accounts` subcommands
- `FleetManager` — `ThreadPoolExecutor`-based concurrent multi-BMC operations
- Fleet functions: `collect_inventory()`, `power_all()`, `health_summary()`, `export_csv()`, `export_json()`
- Test suite: 27 tests, `respx` mocks, zero real BMC required
- Docs: `docs/sdk.md`, `docs/cli.md`, `docs/fleet.md`

### Definition of Done
- `uv run pytest` → 27/27 passing
- `uv run rf --help` renders correctly
- `FleetManager.collect_inventory()` documented and tested

---


[↑ Back to Top](#table-of-contents)

## Milestone v0.2 — Async Support & Performance

**Goal:** Make the library competitive for large-scale fleet operations by introducing a native async client. Fleet inventory across 1,000 BMCs should complete in under 60 seconds.

### Scope
- `AsyncRedfishClient` — `httpx.AsyncClient`-based, same API surface as `RedfishClient` but async/await
- `AsyncFleetManager` — replaces `ThreadPoolExecutor` with `asyncio.gather` + semaphore-bounded concurrency
- Async resource methods: `await system.power_on()`, `await chassis.temperatures()`, etc.
- `async with AsyncRedfishClient(...)` context manager
- Connection pooling: shared `httpx.AsyncClient` per host across multiple operations
- Retry logic: configurable `max_retries` with exponential backoff on 500/503
- CLI: `rf --async` flag routes through async paths for `rf fleet` commands

### New Files
```
src/pykesys_redfish/
├── async_client.py        # AsyncRedfishClient
├── async_session.py       # AsyncRedfishSession
└── fleet/
    └── async_manager.py   # AsyncFleetManager
```

### Acceptance Criteria
- `AsyncFleetManager` polls 100 mock hosts concurrently in tests in < 2s
- Sync `RedfishClient` still works unchanged — no breaking changes
- `uv run pytest` all green including new async tests

---


[↑ Back to Top](#table-of-contents)

## Milestone v0.3 — Extended Resource Coverage

**Goal:** Cover the full Redfish resource tree. Operators should not need raw `rf.get()` calls for common operations.

### Scope

**VirtualMedia** (`Manager` sub-resource):
- `manager.virtual_media()` → list of `VirtualMedia` objects
- `VirtualMedia.insert(image_uri, media_type="DVD")` — mount remote ISO
- `VirtualMedia.eject()` — unmount
- CLI: `rf media list`, `rf media mount <uri>`, `rf media eject`

**UpdateService / Firmware Tasks**:
- `update_service.firmware_inventory()` → list with version + updateable flag
- `update_service.simple_update(image_uri, targets)` → returns `Task`
- `Task` resource: `task.wait(timeout=600)` — polls until `Completed` or `Exception`
- CLI: `rf firmware update` already exists; add `rf firmware task-status <task-id>`

**BIOS Settings**:
- `system.bios()` → `Bios` resource
- `bios.attributes` — dict of all BIOS attributes
- `bios.set_attributes(**kwargs)` — stage changes (applied on next reboot)
- `bios.reset_to_defaults()` — factory reset BIOS
- CLI: `rf bios get [attr]`, `rf bios set key=value ...`, `rf bios reset`

**EventService**:
- `event_service.subscriptions()` → list
- `event_service.subscribe(destination, event_types)` → subscription URI
- `event_service.unsubscribe(uri)`
- CLI: `rf events subscribe <url>`, `rf events list`, `rf events unsubscribe <uri>`

**NetworkAdapters / PCIeDevices** (read-only inventory):
- `system.network_adapters()` → list of dicts
- `system.pcie_devices()` → list of dicts

### New Files
```
src/pykesys_redfish/resources/
├── virtual_media.py
├── bios.py
├── task.py
└── event_service.py
src/pykesys_redfish/cli/commands/
├── media.py
├── bios.py
└── events.py
```

### Acceptance Criteria
- All new resource classes have unit tests with respx fixtures
- `rf bios get`, `rf media mount`, `rf events subscribe` all in `--help`
- `Task.wait()` tested with a mock that transitions through `Running` → `Completed`

---


[↑ Back to Top](#table-of-contents)

## Milestone v0.4 — CLI Enhancements & Fleet-Level Commands

**Goal:** Make `rf` the primary daily-driver for operators. Add fleet-wide CLI operations and richer output.

### Scope

**Fleet subcommand group** (`rf fleet`):
- `rf fleet info` — Rich table across all hosts from `RF_FLEET` env var (comma-separated host list) or `--hosts-file hosts.txt`
- `rf fleet power-all <reset-type>` — concurrent power action with per-host result summary
- `rf fleet health` — aggregate health rollup table (OK/Warning/Critical counts, error hosts)
- `rf fleet inventory --out inventory.csv` — export CSV

**Output format flag** (global `--format`):
- `--format table` (default, Rich)
- `--format json` — machine-readable JSON to stdout
- `--format csv` — CSV to stdout (for piping)

**Interactive host selection** (`rf shell`):
- REPL loop: enter commands without re-specifying `--host` every time
- History via readline
- `connect <host>`, `disconnect`, `status`, then any command without `--host`

**Shell completion**:
- `rf --install-completion` already provided by Typer
- Add `RF_HOST` / `RF_USER` / `RF_PASS` detection to completion hints

**`--watch` flag** for status commands:
- `rf power status --watch` — re-polls every 5s, updates in-place using Rich Live

### New Files
```
src/pykesys_redfish/cli/commands/
└── fleet.py           # rf fleet subcommands
src/pykesys_redfish/cli/
└── shell.py           # rf shell REPL
```

### Acceptance Criteria
- `rf fleet info --hosts-file /dev/stdin` works from a pipe
- `--format json` output is valid JSON (tested with `json.loads`)
- `--format csv` output parses with `csv.DictReader`
- `rf shell` enters and exits cleanly in tests

---


[↑ Back to Top](#table-of-contents)

## Milestone v0.5 — Observability Integrations & Exporter

**Goal:** Make pykesys-redfish a first-class citizen in monitoring stacks. Emit Prometheus metrics, OpenTelemetry traces, and accept Redfish push events.

### Scope

**Prometheus Metrics Exporter** (`rf export prometheus`):
- Starts an HTTP server on `:9610` (configurable)
- Polls configured BMC hosts on a scrape interval
- Exposes gauges: `redfish_power_state`, `redfish_health_status` (labeled by host/model/serial)
- Exposes gauges per sensor: `redfish_temperature_celsius`, `redfish_fan_rpm`
- Docker-ready: `CMD ["rf", "export", "prometheus", "--hosts-file", "/etc/hosts.txt"]`
- Optional: Prometheus client pushgateway push mode

**OpenTelemetry Traces**:
- `RedfishClient` optionally wraps each request in an OTEL span
- Span attributes: `http.url`, `redfish.host`, `redfish.resource_type`, `http.status_code`
- Enabled via `OTEL_EXPORTER_OTLP_ENDPOINT` env var (zero-config)
- Dependency: `opentelemetry-sdk` in `[optional-dependencies]` `otel` extra

**Redfish Event Webhook Receiver** (`rf events receive`):
- Starts an HTTPS server on `:4443`
- Accepts Redfish event POST payloads
- Forwards to stdout (JSON Lines), Slack webhook, or PagerDuty Events API
- Usable as a sidecar in Kubernetes for centralized event collection

**Structured Logging**:
- All SDK HTTP calls emit structured log records (JSON) when `RF_LOG_FORMAT=json`
- Fields: `timestamp`, `host`, `method`, `uri`, `status_code`, `duration_ms`
- Compatible with Splunk, Datadog, and ELK ingest

### New Files
```
src/pykesys_redfish/
├── exporter/
│   ├── prometheus.py    # metrics collection + HTTP server
│   └── pagerduty.py     # PagerDuty event dispatch
└── cli/commands/
    └── export.py        # rf export prometheus|otlp
```

### New Optional Dependencies
```toml
[project.optional-dependencies]
otel    = ["opentelemetry-sdk>=1.25", "opentelemetry-exporter-otlp-proto-grpc>=1.25"]
metrics = ["prometheus-client>=0.21"]
```

### Acceptance Criteria
- `rf export prometheus` starts, `/metrics` endpoint returns valid Prometheus text format
- OTEL spans appear in a local Jaeger instance when `OTEL_EXPORTER_OTLP_ENDPOINT` is set
- Webhook receiver accepts a sample Redfish event JSON payload and emits it to stdout

---


[↑ Back to Top](#table-of-contents)

## Backlog / Out of Scope for Now

- Windows PowerShell module wrapper
- Go client (separate repo)
- WBEM/WS-Management bridge
- Ansible collection (`community.redfish` already exists)
- Swordfish (storage-focused Redfish extension) resources

---


[↑ Back to Top](#table-of-contents)

## Dependency Map

```
v0.1 ──► v0.2 (async) ──► v0.4 (CLI fleet uses async paths)
     └──► v0.3 (resources) ──► v0.4 (rf bios, rf media, rf events cmds)
                           └──► v0.5 (exporter uses UpdateService Task)
```
