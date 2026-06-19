# pykesys-redfish — Architecture Document


[↑ Back to Top](#table-of-contents)

## Table of Contents

- [1. System Overview](#1-system-overview)
- [2. Repository Layout](#2-repository-layout)
- [3. SDK Architecture](#3-sdk-architecture-srcpykesys_redfish)
- [4. Django Application Architecture](#4-django-application-architecture-redfish_web)
- [5. Frontend Architecture](#5-frontend-architecture-frontend)
- [6. C++ Command Deck Architecture](#6-c-command-deck-architecture-c)
- [7. Technology Stack](#7-technology-stack)
- [8. Key Design Decisions](#8-key-design-decisions)
- [9. Deployment Topologies](#9-deployment-topologies)
- [10. Security Considerations](#10-security-considerations)
- [11. Cross-Cutting Concerns](#11-cross-cutting-concerns)

---


[↑ Back to Top](#table-of-contents)

## 1. System Overview

pykesys-redfish is a layered system for managing and observing server hardware via the DMTF Redfish standard. It is organized into three independently usable layers that share a common SDK core.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     OPERATORS / DGX FLOOR STAFF                              │
│   touch glass · keyboard · browser · scripts · CI/CD · monitoring tools     │
└──────┬───────────────────────────────────┬──────────────────────────────────┘
       │ bare-metal touch                  │ HTTP / REST
       ▼                                   ▼
┌──────────────────────┐       ┌────────────────────────┐
│  C++ Command Deck    │       │   redfish_web          │
│  (C++/  directory)   │       │   Django + React SPA   │
│                      │       │   (observability layer)│
│  - DRM/KMS display   │       └───────────┬────────────┘
│  - evdev 10-pt touch │                   │
│  - OpenGL ES 3 UI    │       ┌────────────▼────────────┐
│  - CUDA ML overlays  │──────►│   pykesys_redfish SDK   │
│  - DDC/CI control    │       │   RedfishClient · Fleet │
└──────────────────────┘       └───────────┬─────────────┘
                                           │ HTTPS / Redfish REST
                    ┌──────────────────────┼──────────────────────┐
                    ▼                      ▼                      ▼
             ┌───────────┐         ┌───────────┐          ┌───────────┐
             │  iDRAC 9  │         │  iLO 5/6  │    ···   │  OpenBMC  │
             └───────────┘         └───────────┘          └───────────┘
                    │                      │                      │
             ┌───────────┐         ┌───────────┐          ┌───────────┐
             │  Server   │         │  Server   │          │  Server   │
             └───────────┘         └───────────┘          └───────────┘
```

---


[↑ Back to Top](#table-of-contents)

## 2. Repository Layout

```
pykesys-redfish/
├── src/pykesys_redfish/       # Python SDK + CLI + Fleet library
│   ├── __init__.py
│   ├── client.py
│   ├── session.py
│   ├── exceptions.py
│   ├── resources/             # Typed resource wrappers
│   ├── cli/                   # `rf` CLI (Typer + Rich)
│   └── fleet/                 # FleetManager (concurrent multi-BMC)
├── redfish_web/               # Django observability application
│   ├── redfish_web/           # Django project settings/urls
│   ├── hosts/                 # BMC host registry
│   ├── inventory/             # Snapshot + sensor + log storage
│   ├── alerts/                # Alert rules + events
│   └── scheduler/             # APScheduler background polling
├── frontend/                  # React 18 + Vite + Tailwind SPA
│   └── src/
│       ├── pages/             # Dashboard, HostDetail, Alerts
│       └── components/        # HealthBadge, FleetGrid, SensorTable, …
├── tests/                     # SDK test suite (pytest + respx)
├── docs/                      # All documentation
└── pyproject.toml             # SDK packaging (uv / hatchling)
```

---


[↑ Back to Top](#table-of-contents)

## 3. SDK Architecture (`src/pykesys_redfish/`)

### 3.1 Layer Diagram

```
┌──────────────────────────────────────────────────────────┐
│                    Application Code                       │
│         scripts · CLI commands · Django views            │
└──────────────────────────┬───────────────────────────────┘
                           │ uses
┌──────────────────────────▼───────────────────────────────┐
│                   RedfishClient                           │
│  context manager · resource accessors · raw HTTP pass-   │
│  through (get / post / patch / delete)                    │
└──────────────────────────┬───────────────────────────────┘
                           │ delegates to
┌──────────────────────────▼───────────────────────────────┐
│                   RedfishSession                          │
│  httpx.Client · session token lifecycle · _raise_for_    │
│  status() · auth header injection                        │
└──────────────────────────┬───────────────────────────────┘
                           │ HTTP
┌──────────────────────────▼───────────────────────────────┐
│                   BMC (HTTPS / Redfish)                   │
└──────────────────────────────────────────────────────────┘
```

### 3.2 Resource Class Hierarchy

```
RedfishResource (base.py)
├── lazy _data cache — fetched on first property access
├── refresh() — invalidates cache
└── _get(*keys) — safe nested dict traversal

    ├── ComputerSystem (system.py)
    │   ├── Properties: power_state, health, bios_version, hostname, …
    │   ├── Actions: power_on/off, reset, graceful_shutdown/restart, nmi
    │   ├── Boot: set_boot_once, clear_boot_override
    │   ├── LED: identify / identify_off
    │   └── Sub-resources: processors(), memory(), storage(), log_entries()
    │
    ├── Chassis (chassis.py)
    │   ├── Properties: chassis_type, health, indicator_led
    │   └── Sensors: temperatures(), fans(), power_supplies(), power_consumed_watts()
    │
    ├── Manager (manager.py)
    │   ├── Properties: firmware_version, manager_type, health
    │   ├── Config: set_protocol_enabled(), set_ntp_servers()
    │   └── Actions: reset(), reset_to_defaults()
    │
    ├── Storage (storage.py)
    │   └── drives() → list[Drive]
    │
    ├── Drive (storage.py)
    │   └── Properties: capacity_gib, protocol, media_type, predicted_life_left_pct
    │
    └── AccountService (accounts.py)
        └── CRUD: accounts(), create_account(), delete_account(), set_lockout_policy()
```

### 3.3 Authentication Flow

```
                    ┌──────────────────────┐
                    │ RedfishClient.__enter│
                    └──────────┬───────────┘
                               │
               ┌───────────────▼──────────────┐
               │  auth="session" (default)     │
               │  POST /redfish/v1/            │
               │    SessionService/Sessions/   │
               │  ◄── X-Auth-Token header      │
               │  ◄── Location: /sessions/1    │
               └───────────────┬──────────────┘
                               │ token stored on session object
               ┌───────────────▼──────────────┐
               │  All requests:                │
               │  X-Auth-Token: <token>        │
               └───────────────┬──────────────┘
                               │
               ┌───────────────▼──────────────┐
               │ RedfishClient.__exit          │
               │  DELETE /sessions/1           │
               └──────────────────────────────┘
```

Fallback: `auth="basic"` injects HTTP Basic credentials on every request — no session created or destroyed.

### 3.4 Fleet Module

```
FleetManager
│
├── hosts: list[str]           — BMC URLs
├── max_workers: int (16)      — thread pool size
│
├── run(fn) → list[dict]
│   └── ThreadPoolExecutor
│       └── per host: _run_on_host(host, fn)
│           ├── RedfishClient(host).__enter__
│           ├── result = fn(rf, host)
│           ├── RedfishClient.__exit__
│           └── return result  (errors captured as {"host":…, "error":…})
│
├── collect_inventory()  → run(collect_system_inventory)
├── power_all(reset_type) → run(power_reset)
├── health_summary()     → collect_inventory() + summarize_health()
├── export_csv(results, path)
└── export_json(results, path)
```

Error isolation: each host runs in its own thread with its own client. A failure on one host never affects others — it returns `{"host": "…", "error": "…"}` and the rest continue.

---


[↑ Back to Top](#table-of-contents)

## 4. Django Application Architecture (`redfish_web/`)

### 4.1 Application Layer Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                      React SPA (frontend/)                        │
│   Dashboard · HostDetail · Alerts · api.js (fetch wrappers)      │
└────────────────────────────┬─────────────────────────────────────┘
                             │ HTTPS · DRF JSON API
┌────────────────────────────▼─────────────────────────────────────┐
│                    Django (redfish_web/)                          │
│  ┌──────────┐  ┌───────────┐  ┌────────┐  ┌───────────────────┐ │
│  │  hosts   │  │ inventory │  │ alerts │  │    scheduler      │ │
│  │  app     │  │  app      │  │  app   │  │    app            │ │
│  └────┬─────┘  └─────┬─────┘  └───┬────┘  └────────┬──────────┘ │
│       │              │             │                 │            │
│  ┌────▼──────────────▼─────────────▼─────────────────▼─────────┐ │
│  │              Django ORM  (SQLite / PostgreSQL)               │ │
│  └─────────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              pykesys_redfish SDK (imported)                  │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
                             │ HTTPS · Redfish REST
                    ┌────────▼────────┐
                    │   BMC Fleet     │
                    └─────────────────┘
```

### 4.2 Django App Responsibilities

| App | Models | Key Responsibility |
|-----|--------|--------------------|
| `hosts` | `BMCHost` | Host registry, credential storage, power/boot action proxy |
| `inventory` | `InventorySnapshot` `SensorReading` `LogEntry` | Persist poll results; serve historical data |
| `alerts` | `AlertRule` `AlertEvent` | Evaluate rules post-poll; dispatch Slack notifications |
| `scheduler` | — (APScheduler) | Drive the poll cycle; wire inventory → alert evaluation |

### 4.3 Data Model

```
BMCHost
│  id, host(unique), display_name, username, password
│  verify_ssl, enabled, poll_interval, tags
│  last_seen, last_error
│
├──── InventorySnapshot (many)
│     │  polled_at, power_state, health, bios_version
│     │  model, manufacturer, serial_number, hostname
│     │  total_memory_gib, processor_count, processor_model
│     │  raw_json
│     │
│     └──── SensorReading (many)
│            name, reading, unit, status, upper_threshold_critical
│
├──── LogEntry (many)
│     entry_id(unique per host), occurred_at
│     severity, message, message_id
│
└──── AlertEvent (many) ◄── AlertRule
      triggered_at, resolved_at, message, notified

AlertRule (independent)
  name, field, operator, value, severity
  enabled, notify_slack_webhook, notify_email
```

### 4.4 Request / Response Flow — Fleet Dashboard

```
Browser                 Django                  pykesys_redfish SDK     BMC
   │                       │                           │                  │
   │  GET /api/fleet/       │                           │                  │
   │──────────────────────►│                           │                  │
   │                       │  BMCHost.objects.all()    │                  │
   │                       │  host.snapshots.first()   │                  │
   │                       │  (no live BMC call —      │                  │
   │                       │   reads cached snapshots) │                  │
   │◄──────────────────────│                           │                  │
   │  [{host, latest_snapshot}, …]                     │                  │
   │                       │                           │                  │
```

### 4.5 Poll Cycle — Background Flow

```
APScheduler (every 30s)
  │
  ▼
run_poll_cycle()   [scheduler/jobs.py]
  │
  ├── BMCHost.objects.filter(enabled=True)
  │   for each host where last_seen + poll_interval <= now:
  │
  ▼
poll_host(host)   [inventory/tasks.py]
  │
  ├── RedfishClient(host.base_url, …).__enter__
  │   ├── rf.system().summary()           → InventorySnapshot.create()
  │   ├── rf.chassis().temperatures()     → SensorReading.create() ×N
  │   ├── rf.chassis().fans()             → SensorReading.create() ×N
  │   └── rf.system().log_entries()       → LogEntry.get_or_create() ×N
  │   host.last_seen = now
  │   RedfishClient.__exit__
  │
  └── evaluate_rules(snapshot)   [alerts/notifications.py]
      │
      ├── for each enabled AlertRule:
      │   rule.matches(snapshot)?
      │   ├── YES → _ensure_open_event()
      │   │         AlertEvent.create() if no open event exists
      │   │         dispatch() → POST Slack webhook
      │   └── NO  → _resolve_open_events()
      │              UPDATE resolved_at = now
```

### 4.6 API URL Structure

```
/api/
├── hosts/                          GET, POST
│   └── {id}/
│       ├──                         GET, PUT, PATCH, DELETE
│       ├── poll/                   POST
│       ├── power/                  POST  { reset_type }
│       ├── boot/                   POST  { target, enabled }
│       ├── snapshots/              GET (paginated)
│       │   └── {snapshot_id}/      GET (with sensors embedded)
│       ├── logs/                   GET (paginated)
│       └── sensors/                GET (latest snapshot only)
│
├── fleet/                          GET (all hosts + latest snapshot)
│
└── alerts/
    ├── rules/                      GET, POST
    │   └── {id}/                   GET, PUT, PATCH, DELETE
    └── events/                     GET (?open=true, ?host=id)
        └── {id}/resolve/           POST
```

All endpoints served by Django REST Framework. All responses are JSON. Pagination via `?page=N`.

---


[↑ Back to Top](#table-of-contents)

## 5. Frontend Architecture (`frontend/`)

### 5.1 Component Tree

```
App (BrowserRouter)
│
├── Nav (links: Dashboard · Alerts)
│
├── Route "/"           → Dashboard
│   ├── FleetGrid
│   │   └── HostCard ×N  (click → /hosts/:id)
│   └── SummaryStrip     (Total · Healthy · Warning · Critical)
│
├── Route "/hosts/:id"  → HostDetail
│   ├── Tab: Overview   → key-value panel (snapshot fields)
│   ├── Tab: Sensors    → SensorTable
│   ├── Tab: Logs       → LogTable
│   └── Tab: Actions    → power buttons · boot override · poll-now
│
└── Route "/alerts"     → Alerts
    ├── Tab: Rules       → rules table + create modal
    └── Tab: Events      → events table + resolve button
```

### 5.2 Data Fetching Pattern

All API calls go through `src/api.js` — a thin fetch wrapper. Components own their own state and load on mount:

```
Component mounts
  │
  ▼
useEffect(() => { load(); }, [])
  │
  ├── api.getFleet()  →  fetch("/api/fleet/")
  │                     sets hosts state
  │
  └── setInterval(load, 30_000)   ← Dashboard only
      re-fetches every 30s without a full page reload
```

No global state manager (Redux/Zustand). Each page fetches what it needs. The fleet dashboard is the only page with auto-refresh.

### 5.3 Build & Serving

```
Development:
  npm run dev (Vite dev server :5173)
    └── /api/* → proxy → Django :8000
    └── all other routes → React SPA

Production:
  npm run build
    └── output → redfish_web/staticfiles/spa/
                 index.html + assets/index-*.js + assets/index-*.css

  python manage.py collectstatic
    └── WhiteNoise serves /static/* including the SPA bundle

  Django URL catch-all:
    re_path(r"^(?!api/|admin/|static/).*", TemplateView("index.html"))
    └── serves the SPA shell for all non-API routes
    └── React Router handles client-side routing
```

---


[↑ Back to Top](#table-of-contents)

## 6. C++ Command Deck Architecture (`C++/`)

The C++ command deck runs directly on DGX hardware with no compositor. It is the physical operator interface: touch panels, status displays, and real-time CUDA overlays. Unlike the Django web layer (which requires a network browser), the command deck is always present on the physical console.

### 6.1 Layer diagram

```
┌─────────────────────────────────────────────────────────────────┐
│              C++ Command Deck Application                        │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │ InputThread  │    │ RenderThread │    │   CUDAThread     │  │
│  │              │    │ (main)       │    │                  │  │
│  │ epoll_wait   │    │ GL ES 3.x    │    │ Visualization    │  │
│  │ MTTracker    │───►│ EGL/GBM/KMS  │◄───│ kernels          │  │
│  │ Gestures     │    │ Renderer     │    │ colormap_kernel  │  │
│  │              │    │ draw_finger  │    │ gaussian_splat   │  │
│  └──────┬───────┘    └──────┬───────┘    │ gpu_bars_kernel  │  │
│         │                   │            └──────────────────┘  │
│  ┌──────▼───────────────────▼──────────────────────────────┐  │
│  │         SPSCQueue<TouchEvent,256> + SPSCQueue<KeyEvent,64>│  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ DDCControl — brightness, input, power via DDC/CI (I2C)    │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
         │ HTTPS                        │ DRM page flip
   pykesys_redfish SDK            TD2423D / IFP55G1 display
```

### 6.2 Input pipeline

```
/dev/input/event*                    (Linux character device)
    │  struct input_event stream
    ▼
libevdev (TouchDevice)               (thin ioctl wrapper)
    │
    ▼
MTTracker                            (MT Type B state machine)
    │  per SYN_REPORT:
    │  TouchEvent { x, y, touch_major, touch_minor, pressure }
    ▼
SPSCQueue<TouchEvent, 256>           (lock-free thread boundary)
    │
    ▼
TouchIndicator[] update              (render thread, 60 Hz)
    │  + TapDetector, SwipeDetector, PinchDetector (input thread)
```

### 6.3 Render pipeline

```
TouchIndicator[40]
    │  for each active slot:
    ▼
draw_finger(ind, now)                (4 layers, back to front)
    ├── draw_trail()                 comet trail (16-pt ring buffer)
    ├── draw_ring() [if pressure]    pressure halo
    ├── draw_ellipse(major, minor)   contact footprint
    ├── draw_ellipse(dot)            precision centre
    └── draw_ring() [if ripple]      DOWN burst animation

draw_overlay()                       CUDA texture (if visible)
    │  GL_TRIANGLE_STRIP / GL_TRIANGLE_FAN
    ▼
EGLContext::swap_and_flip()         ← cudaGraphicsUnmapResources BEFORE this
    │  gbm_surface_lock_front_buffer
    │  drmModePageFlip
    │  select() blocks until vblank
    ▼
Display hardware (TD2423D / IFP55G1)
```

### 6.4 CUDA/GL interop

```
GL texture (overlay_tex_)            (physical GPU VRAM)
    │
    │  cudaGraphicsGLRegisterImage()
    ▼
CUDAOverlay::cuda_resource_          (CUDA handle to same memory)
    │
    │  Before each kernel:
    │    cudaGraphicsMapResources()  ← GL must not read while mapped
    │    cudaCreateSurfaceObject()
    │
    ▼
CUDA kernels (colormap, density, GPU bars)
    │  surf2Dwrite(pixel, surf, x*4, y)  ← writes pixels directly
    │
    │  After each kernel:
    │    cudaGraphicsUnmapResources() ← returns ownership to GL
    │    cudaStreamSynchronize()
    ▼
Renderer::draw_overlay()             (GL reads the texture, blends at 60%)
```

Zero CPU involvement in the data path. NVML → CUDA kernel → GL texture → display.

### 6.5 Key design decisions specific to the C++ layer

| Decision | Rationale |
|----------|-----------|
| Direct DRM/KMS, no compositor | Eliminates compositor latency; application owns the display; no dependency on X11/Wayland being installed |
| Dedicated input thread + SPSC queue | GL context is bound to one thread; epoll wakes instantly on kernel delivery; SPSC gives <1μs cross-thread latency without locks |
| Per-slot color identity | MT Type B tracking IDs increment monotonically; slot index is stable within a session — better basis for color assignment |
| `ABS_MT_TOUCH_MAJOR` for ellipse sizing | Provides real physical contact geometry; enables palm rejection and pen vs finger distinction without a separate driver |
| `has_abs()` guard on optional axes | Same binary works on devices that report TOUCH_MAJOR and on those that don't; graceful degradation to default radius |
| CUDA GL interop over CPU texture upload | On DGX, training activations never leave GPU VRAM; visualization kernels run between training steps with zero PCIe traffic |
| PCI bus ID matching for display GPU | Multi-GPU systems require the CUDA context to be on the same physical GPU as OpenGL; sysfs provides the ground truth |

[↑ Back to Top](#table-of-contents)

---


[↑ Back to Top](#table-of-contents)

## 7. Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| HTTP client | `httpx` | Sync + async, connection pooling, modern API |
| CLI framework | `typer` | Type-annotated Click; auto-generates `--help` |
| CLI output | `rich` | Tables, color, progress — zero boilerplate |
| Fleet concurrency | `ThreadPoolExecutor` | BMCs are network-bound; threads sufficient, no GIL issue |
| Web framework | `Django 4.2 LTS` | Batteries-included ORM, admin, migrations; LTS until April 2026 |
| REST API | `djangorestframework` | Serializers, viewsets, pagination, browsable API |
| Static files | `whitenoise` | Serves SPA bundle from Django without a separate nginx |
| Background scheduler | `apscheduler` + `django-apscheduler` | Embedded scheduler, no Redis dependency, job state in DB |
| Database | SQLite (dev) / PostgreSQL (prod) | SQLite for zero-config dev; swap to Postgres for concurrent writes at scale |
| Frontend framework | `React 18` | Functional components, hooks, broad ecosystem |
| Frontend build | `Vite 5` | Sub-second HMR, Rollup-based production build |
| Styling | `Tailwind CSS 3` | Utility-first, no CSS naming overhead, small production bundle |
| Routing | `React Router v6` | Client-side routing; works with Django catch-all |
| SDK packaging | `hatchling` + `uv` | Modern PEP 517 build, fast lockfile-based installs |
| Test mocking | `respx` | httpx-native mock transport; no monkeypatching |
| Test runner | `pytest` + `pytest-django` | Fixtures, parametrize, `@pytest.mark.django_db` |
| Package index | `pypi.apple.com` | Apple internal mirror; required for proxy-gated environments |

---


[↑ Back to Top](#table-of-contents)

## 8. Key Design Decisions

### 7.1 SDK is a dependency of the web app, not a subpackage

`pykesys_redfish` is installed into the Django virtualenv as a path dependency (`pip install -e ../`). This means:
- The SDK can be developed, tested, and versioned independently of the web app
- Django views use the same `RedfishClient` API that CLI users and script authors use
- Breaking changes in the SDK surface as test failures in both suites

### 7.2 Resource objects are lazy-cached, not live

`RedfishResource._data` is populated on the first property access, not at construction time. This avoids unnecessary network calls when only one property is needed. Callers call `.refresh()` to invalidate and re-fetch.

### 7.3 Snapshots are point-in-time, not live

The web app never calls BMC APIs during a user-facing HTTP request (with the exception of explicit `/poll/`, `/power/`, and `/boot/` actions). The dashboard and detail pages read from the database — the scheduler handles all live BMC traffic. This keeps request latency predictable and decouples UI availability from BMC reachability.

### 7.4 Alert evaluation is synchronous and post-poll

`evaluate_rules()` runs immediately after `poll_host()` in the same scheduler job, within the same transaction scope. This keeps the alert logic simple and auditable. The trade-off is that alerts fire on the poll interval (≥30s latency), not in real-time — acceptable for hardware health which changes slowly.

### 7.5 No Redis / Celery in v0.1

APScheduler with `DjangoJobStore` stores job metadata in the Django database. This eliminates the operational overhead of running a message broker for the polling use case. For deployments requiring distributed workers or sub-second task scheduling, the scheduler app is the only component that needs to change.

### 7.6 SPA served by Django (same origin)

The React app is built into `staticfiles/spa/` and served by Django/WhiteNoise. This means:
- No CORS configuration needed
- Cookie-based session auth works without custom headers
- A single process serves both API and UI in development
- In production, nginx/ALB can front both at the same origin

### 7.7 Passwords stored plaintext in v0.1

BMC credentials in `BMCHost.password` are stored as-is in the database. This is explicitly noted as a v0.1 limitation. Production deployments should either:
- Encrypt the field at rest using a KMS-backed field encryption library
- Store credentials in an external vault and resolve them at poll time

---


[↑ Back to Top](#table-of-contents)

## 9. Deployment Topologies

### 8.1 Single-Process Development

```
Workstation
├── python manage.py runserver :8000   (Django API + static files)
└── npm run dev :5173                  (Vite SPA + /api proxy to :8000)
```

### 8.2 Single-Server Production

```
Server
└── gunicorn redfish_web.wsgi          (Django serves API + SPA bundle)
    APScheduler thread (in-process)    (poll cycle every 30s)
    db.sqlite3                         (or PostgreSQL on same/different host)
```

### 8.3 Containerized

```
┌─────────────────────────────────────────────┐
│  Docker Compose / Kubernetes                │
│                                             │
│  ┌──────────────┐   ┌───────────────────┐  │
│  │  web         │   │  db               │  │
│  │  Django +    │──►│  PostgreSQL        │  │
│  │  APScheduler │   └───────────────────┘  │
│  │  :8000       │                          │
│  └──────────────┘                          │
│         ▲                                  │
│  ┌──────┴──────┐                           │
│  │  nginx/ALB  │  :443                     │
│  └─────────────┘                           │
└─────────────────────────────────────────────┘
         │ HTTPS
    BMC Management Network
```

### 8.4 CLI-Only (No Web App)

```
Workstation / CI runner
└── uv run rf --host https://bmc-host -u admin -p password info
└── python script.py  (using FleetManager directly)
```

The SDK has no Django dependency and can be used entirely standalone.

---


[↑ Back to Top](#table-of-contents)

## 10. Security Considerations

| Concern | Current State | Recommended Hardening |
|---------|--------------|----------------------|
| BMC credentials at rest | Plaintext in SQLite/Postgres | Encrypt field with Fernet; use vault at poll time |
| BMC TLS verification | `verify_ssl` per host (default True) | Import BMC CA bundle; never set `verify_ssl=False` in production |
| Django `SECRET_KEY` | Defaults to hardcoded dev key | Set `DJANGO_SECRET_KEY` env var from secret manager |
| API authentication | None in v0.1 (open API) | Milestone v0.3: session auth + RBAC (Viewer/Operator/Admin) |
| BMC management network | Assumed OOB; not enforced by app | Ensure Django host has a route to BMC VLAN; block BMC VLAN from untrusted networks |
| HTTPS enforcement | Django serves HTTP in dev | In production: terminate TLS at nginx/ALB; set `SECURE_SSL_REDIRECT=True` |
| CSRF | Django CSRF middleware enabled | React SPA must include `X-CSRFToken` header on POST/PATCH/DELETE (v0.3) |

---


[↑ Back to Top](#table-of-contents)

## 11. Cross-Cutting Concerns

### Logging

Both layers use Python's standard `logging` module. Key loggers:
- `pykesys_redfish.session` — logs request errors at WARNING
- `inventory.tasks` — logs `Poll failed for {host}` at WARNING
- `scheduler.jobs` — logs `Polling {host}` at INFO, scheduler start/stop

Configure via `LOGGING` in Django settings or `logging.basicConfig()` in scripts.

### Error Handling

| Layer | Error | Behavior |
|-------|-------|---------|
| SDK | HTTP 401/403 | Raises `RedfishAuthError` |
| SDK | HTTP 404 | Raises `RedfishNotFoundError` |
| SDK | Network timeout | Raises `RedfishTimeoutError` |
| Fleet | Any host failure | Captured as `{"error": "…"}`; other hosts continue |
| Django poll | Any exception | `host.last_error` written; shown in dashboard card |
| Django API | SDK error on power/boot | Returns `502 Bad Gateway` with `{"error": "…"}` |
| React | API fetch failure | Shows error message in component; does not crash |

### Testing Strategy

```
Layer         Tool        Scope
──────────────────────────────────────────────────────
SDK           pytest      Unit — all resource methods, error handling
              respx       Mock httpx at transport layer; zero real BMC calls
Django        pytest      Unit/integration — models, serializers, API endpoints
              SQLite      In-memory test DB (no external DB needed)
React         —           Not yet covered (v0.2 candidate: Vitest + React Testing Library)
```
