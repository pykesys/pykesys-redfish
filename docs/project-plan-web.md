# redfish_web Django Observability App — Project Plan & Milestones

## Overview

`redfish_web` is a Django + React SPA observability platform for Redfish-managed BMC fleets. It provides a fleet dashboard, per-host hardware detail, background polling, and alert notifications. This document tracks delivered milestones and planned enhancement phases.

---

## Milestone v0.1 — Foundation ✅ (Delivered)

**Goal:** Running web app with live fleet visibility, basic alerting, and background polling.

### Delivered

**Backend (Django 4.2 + DRF)**
- `hosts` app: `BMCHost` model — CRUD, `/api/hosts/`, per-host `power` and `boot` action endpoints
- `inventory` app: `InventorySnapshot`, `SensorReading`, `LogEntry` models; `poll_host()` function using the pykesys-redfish SDK; `/api/fleet/`, `/api/hosts/{id}/snapshots|sensors|logs/`
- `alerts` app: `AlertRule`, `AlertEvent` models; `evaluate_rules()` post-poll; Slack webhook dispatch; `/api/alerts/rules/` and `/api/alerts/events/`
- `scheduler` app: APScheduler `BackgroundScheduler` — `run_poll_cycle()` every 30s, per-host interval gating
- Django admin registered for all models
- Test suite: 20 tests, all passing

**Frontend (React 18 + Vite + Tailwind CSS)**
- `Dashboard` — fleet host grid, health color-coding, 30s auto-refresh, summary counters (Total / Healthy / Warning / Critical)
- `HostDetail` — tabs: Overview (snapshot fields) | Sensors (table) | Logs (table) | Actions (power buttons, boot override, poll-now)
- `Alerts` — Rules CRUD modal + Events timeline with resolve button
- `HealthBadge`, `PowerBadge`, `FleetGrid`, `SensorTable`, `LogTable` components
- Vite proxy `/api` → Django in dev; Vite builds to `staticfiles/spa/` for production

### Definition of Done
- `pytest` → 20/20 passing
- `npm run build` succeeds, bundle < 250 kB gzipped
- `runserver` + `npm run dev` → fleet dashboard visible at `localhost:5173`

---

## Milestone v0.2 — Historical Trending & Charts

**Goal:** Turn snapshots into time-series charts so operators can see how health and sensor readings evolve over time. Answer questions like "when did this server start running hot?" or "how long has it been in Warning state?".

### Backend Changes

**Snapshot retention policy**:
- New setting `SNAPSHOT_RETENTION_DAYS = 30` (default)
- Management command `python manage.py prune_snapshots` — deletes snapshots older than retention threshold, keeps one snapshot per hour beyond 24h (downsampling)
- Run via APScheduler daily

**New API endpoints**:
- `GET /api/hosts/{id}/health-history/` — returns `[{polled_at, health, power_state}]` for a configurable time window (`?hours=24`, `?days=7`)
- `GET /api/hosts/{id}/sensor-history/?name=Inlet+Temp&hours=24` — time-series for a named sensor

### Frontend Changes

**New `HistoryChart` component** (using [Recharts](https://recharts.org)):
- Line chart of sensor reading over time with threshold annotation line
- Area chart of health state transitions (colored bands: green=OK, yellow=Warning, red=Critical)

**HostDetail tab additions**:
- New **"History"** tab: health timeline area chart + sensor picker with line chart
- Dashboard host cards: small sparkline showing last 24h health state

### New Files
```
redfish_web/inventory/
└── management/commands/prune_snapshots.py

frontend/src/components/
└── HistoryChart.jsx
frontend/src/pages/
└── HostDetail.jsx   (updated — History tab added)
```

### New Dependency
```
package.json: "recharts": "^2.13"
```

### Acceptance Criteria
- `prune_snapshots` tested with snapshots at various ages
- `GET /api/hosts/1/health-history/?hours=24` returns correct time-ordered data
- HistoryChart renders without error when given an empty dataset

---

## Milestone v0.3 — Authentication, RBAC & Audit Log

**Goal:** Make the app production-safe. Lock down the API and UI behind login, enforce role-based access so read-only users can't trigger power actions, and maintain an audit log of every state-changing operation.

### Backend Changes

**Django auth integration**:
- Login page at `/login/` (Django `LoginView`)
- `@login_required` on all DRF views via custom `IsAuthenticated` permission class
- Session-based auth for SPA (cookie + CSRF) — no token overhead for same-origin requests
- API token auth (`rest_framework.authtoken`) for external tools and the `rf` CLI

**Roles** (via Django Groups):
- `Viewer` — read-only: GET all endpoints, no POST/PATCH/DELETE
- `Operator` — Viewer + power/boot/poll actions, no host CRUD
- `Admin` — full access including host CRUD, alert rule management, user management

**Custom DRF permission classes**:
- `IsViewer`, `IsOperator`, `IsAdmin` — checked per-view/per-action

**Audit log model** (`hosts` app):
```python
class AuditEvent(Model):
    user = ForeignKey(User, on_delete=SET_NULL, null=True)
    action = CharField()       # "power_reset", "boot_override", "create_host", etc.
    host = ForeignKey(BMCHost, null=True, on_delete=SET_NULL)
    detail = JSONField()       # { reset_type: "GracefulRestart" }
    timestamp = DateTimeField(auto_now_add=True)
    ip_address = GenericIPAddressField(null=True)
```
- Written on every POST/PATCH/DELETE in views via a reusable `log_audit()` helper
- `GET /api/audit/` — paginated, filterable by user/host/action

**Management command**: `create_default_groups` — idempotent setup of Viewer/Operator/Admin groups

### Frontend Changes
- Login page (simple form, CSRF-aware)
- User menu in nav bar: logged-in username, logout button
- Role-gated UI: Actions tab hidden for Viewer role; power buttons disabled with tooltip
- `GET /api/auth/me/` — returns `{username, role}` used to drive frontend permissions

### New Files
```
redfish_web/
├── accounts/
│   ├── models.py      # AuditEvent
│   ├── views.py       # /api/auth/me/, /api/audit/
│   ├── urls.py
│   ├── permissions.py # IsViewer, IsOperator, IsAdmin
│   └── management/commands/create_default_groups.py
frontend/src/
├── pages/Login.jsx
├── context/AuthContext.jsx
└── components/ProtectedRoute.jsx
```

### Acceptance Criteria
- Unauthenticated `GET /api/fleet/` returns 403
- Viewer token cannot POST to `/api/hosts/{id}/power/`
- Operator token can POST power but cannot DELETE a host
- Every power action creates an `AuditEvent` row
- Login page renders and submits without CSRF errors

---

## Milestone v0.4 — Firmware Management Center

**Goal:** Give operators a fleet-wide view of firmware versions and a guided workflow for rolling out firmware updates — knowing which hosts are outdated, staging updates, and tracking progress.

### Backend Changes

**Firmware inventory snapshot** (extends `inventory` app):
```python
class FirmwareComponent(Model):
    snapshot = ForeignKey(InventorySnapshot, on_delete=CASCADE)
    component_id = CharField()      # "BIOS", "BMC", "NIC.1", etc.
    name = CharField()
    version = CharField()
    updateable = BooleanField()
```
- `poll_host()` extended to also fetch `UpdateService/FirmwareInventory/` and persist `FirmwareComponent` rows per snapshot

**Firmware baseline model** (`inventory` app):
```python
class FirmwareBaseline(Model):
    component_id = CharField()
    name = CharField()
    target_version = CharField()
    notes = TextField(blank=True)
```
- Operators define the "desired" version per component
- `GET /api/firmware/compliance/` — cross-joins baseline vs. latest snapshot per host, returns a compliance matrix

**Firmware update job**:
```python
class FirmwareUpdateJob(Model):
    host = ForeignKey(BMCHost, on_delete=CASCADE)
    component_id = CharField()
    image_uri = URLField()
    status = CharField()   # pending, running, completed, failed
    redfish_task_id = CharField(blank=True)
    started_at = DateTimeField(null=True)
    completed_at = DateTimeField(null=True)
    log = TextField(blank=True)
```
- `POST /api/firmware/jobs/` — queues an update
- APScheduler job checks running jobs every 60s via `UpdateService/Tasks/{id}` Redfish polling
- `GET /api/firmware/jobs/` — job list with status

### Frontend Changes

**New `Firmware` page** (`/firmware`):
- **Compliance Matrix tab**: table with hosts as rows, firmware components as columns, cell = version string colored green (matches baseline) / red (outdated) / gray (unknown)
- **Jobs tab**: list of active and completed update jobs with progress indicator
- **"Update All Outdated"** button — opens confirmation modal listing affected hosts, then bulk-queues `FirmwareUpdateJob` rows

**Nav bar**: add Firmware link

### New Files
```
redfish_web/inventory/
├── models.py         (FirmwareComponent, FirmwareBaseline, FirmwareUpdateJob added)
└── firmware_jobs.py  (APScheduler job: poll Redfish Task status)
frontend/src/pages/
└── Firmware.jsx
```

### Acceptance Criteria
- `FirmwareComponent` rows created during `poll_host()` test with mocked firmware endpoint
- Compliance matrix API returns correct outdated/compliant status
- Update job transitions from `pending` → `running` → `completed` in test with mocked Task endpoint
- Firmware page renders compliance matrix without error on empty data

---

## Milestone v0.5 — Bulk Operations, Grouping & Maintenance Windows

**Goal:** Enable operators to act on logical groups of servers (by tag, rack, or role) and schedule maintenance windows — power events, firmware rollouts, and PXE reboots — at a future time, with rollback controls.

### Backend Changes

**Host groups** (extends `hosts` app):
```python
class HostGroup(Model):
    name = CharField(unique=True)
    description = TextField(blank=True)
    hosts = ManyToManyField(BMCHost, blank=True)
    tags = JSONField(default=list)   # auto-include hosts matching these tags
```
- `GET /api/groups/` — CRUD
- `GET /api/groups/{id}/hosts/` — resolved host list (explicit + tag-matched)

**Maintenance window model**:
```python
class MaintenanceWindow(Model):
    name = CharField()
    group = ForeignKey(HostGroup, on_delete=CASCADE)
    scheduled_at = DateTimeField()
    action = CharField()       # "power_reset", "pxe_boot_reset", "firmware_update"
    action_params = JSONField() # { reset_type: "GracefulRestart" } or { baseline_id: 3 }
    status = CharField()        # scheduled, running, completed, failed, cancelled
    created_by = ForeignKey(User, on_delete=SET_NULL, null=True)
    results = JSONField(default=list)  # per-host result after execution
```
- APScheduler scans for `scheduled_at <= now, status=scheduled` every 60s and executes
- Execution uses `FleetManager.run()` concurrently
- `POST /api/windows/{id}/cancel/` — cancel if not yet started

**Playbook / multi-step sequences**:
```python
class Playbook(Model):
    name = CharField()
    steps = JSONField()  # [{"action": "set_boot_once", "params": {"target": "Pxe"}}, {"action": "reset", "params": {"type": "GracefulRestart"}}, {"action": "wait_power_state", "params": {"state": "On", "timeout": 300}}]
```
- Executes steps in order per host; stops on error unless `continue_on_error: true`
- Built-in steps: `set_boot_once`, `power_reset`, `wait_power_state`, `poll_inventory`, `send_slack`

### Frontend Changes

**`Groups` page** (`/groups`):
- Group list + create/edit modal (name, description, host multi-select + tag filter)
- Per-group host grid (reuses `FleetGrid`)

**`Windows` page** (`/windows`):
- Scheduled windows list with countdown timer
- "New Window" modal: pick group + action + datetime
- Running window progress: per-host status indicators

**Nav bar**: Groups, Windows links added

**Dashboard enhancement**: host cards show group membership as tag chips

### New Files
```
redfish_web/
├── groups/
│   ├── models.py        # HostGroup
│   ├── views.py
│   ├── serializers.py
│   └── urls.py
├── windows/
│   ├── models.py        # MaintenanceWindow, Playbook
│   ├── views.py
│   ├── executor.py      # window and playbook execution engine
│   └── urls.py
frontend/src/pages/
├── Groups.jsx
└── Windows.jsx
frontend/src/components/
└── Countdown.jsx
```

### Acceptance Criteria
- `HostGroup` with tag filter returns correct host subset when tags match
- `MaintenanceWindow` with `scheduled_at` in the past transitions to `running` on next scheduler tick in tests
- Playbook step `wait_power_state` times out and marks host as failed after `timeout` seconds
- "New Window" modal submits without validation errors

---

## Backlog / Out of Scope for Now

- Multi-cluster / multi-datacenter aggregation (separate deployment per datacenter, unified dashboard TBD)
- Email notification transport (v0.1 has Slack; email requires SMTP config)
- PagerDuty / OpsGenie native integration (Slack webhook is sufficient for most cases)
- Mobile-responsive layout hardening
- Dark mode
- Export to PDF / Excel

---

## Dependency Map

```
v0.1 ──► v0.2 (charting needs snapshot history)
     └──► v0.3 (auth needed before v0.4/v0.5 expose sensitive operations)
               └──► v0.4 (firmware update jobs use auth + audit log)
               └──► v0.5 (maintenance windows use auth + groups)
                         └──► v0.5 also consumes v0.4 firmware update action
```
