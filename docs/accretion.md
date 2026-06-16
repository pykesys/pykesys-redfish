# Accretion Log — pykesys-redfish

*Sedimentation record. Each meaningful session deposits a stratum.*

**Mandate**: LAW 26 — Cascade Coherence. Deposit before closing every meaningful session.

---

## Strata

### 2026-06-16 — Session 2: Full Build — SDK, Web App, Emulator, Docs, Touchscreen

**Deposited**:
- `src/pykesys_redfish/` — full SDK: RedfishClient, RedfishSession (path-prefix base URLs), resources, CLI, fleet module
- `redfish_web/` — Django observability: hosts, inventory, alerts, scheduler apps; DRF API; APScheduler polling
- `frontend/` — React 18 + Vite SPA: Dashboard, HostDetail, Alerts pages
- `emulator/` — FastAPI 10-node Redfish emulator with Sim control API and 3 scenarios (healthy/degraded/critical)
- `tests/` (27 SDK unit tests) + `tests/integration/` (33 integration tests against emulator)
- `docker-compose.yml` + `docker-compose.ci.yml` + `Dockerfile.test`
- `docs/quickstart.md`, `docs/architecture.md`, `docs/emulator.md`, `docs/touchscreen.md`
- `docs/project-plan-sdk.md`, `docs/project-plan-web.md` (v0.1–v0.5 milestone plans)
- `docs/sdk.md`, `docs/cli.md`, `docs/fleet.md`, `docs/guide-users.md`, `docs/guide-admin.md`
- `docs/prompts.md` — prompt log created (LAW 1, previously missing)
- TOC + BTT added to 9 docs/ files (ladder Rung 1 auto-fix)

**Discovered**:
- `session.py` path-prefix base URL is backward compatible — empty prefix leaves existing behavior unchanged
- FastAPI TestClient bypasses corporate proxy for emulator smoke tests
- Corporate proxy blocks all localhost TCP — integration tests need Docker-internal networking or `trust_env=False`
- `docs/prompts.md` was missing — LAW 1 violation caught and corrected by ladder

**Constitutional state**: 30 laws (LAW 0-29) + 4 META-LAWs + 6 UPs + 5 Cornerstones — unchanged

---

### 2026-06-11 — Session 1: Constitutional Adoption + Bug Scan

**Deposited**:
- `.claude/LAW-LINEAGE.md` — law-mother declaration (role: mother, established 2026-06-11)
- `.claude/PROJECT_LAWS.md` — 30 constitutional laws (seeded from template-law-claude)
- `.claude/SESSION_CONTEXT.md` — project-specific session context
- `MEMORY.md` — project memory at repo root (LAW 19)
- `.claude/EPIPHANIES.md` — crystal record initialized with session 1 arc
- `.claude/.init/` (41 units) — constitutional enforcement service directory
- `.claude/hooks/` — law-0-enforcer.sh + session-loader.sh
- `.claude/commands/` — ladder, cascade, daughter-cascade, lineage-setup, repatriation
- `src/pykesys_redfish/client.py` — `_member_uri()` guard; `close()` unconditional
- `src/pykesys_redfish/session.py` — `httpx.TimeoutException` → `RedfishTimeoutError` in all 5 HTTP methods
- `redfish_web/inventory/tasks.py` — `_mark_error()` updates `last_seen`
- `src/pykesys_redfish/cli/output.py` — `str(None)` → `"—"` fix in fleet table

**Discovered**:
- Five bugs confirmed by thorough scan: index OOB, dead RedfishTimeoutError, resource leak,
  poll_interval bypass on failure, str(None) display fault
- The constitutional framework lands cleanly on a mature Python project — 27 tests still pass

**Constitutional state**: 30 laws (LAW 0-29) + 4 META-LAWs + 6 UPs + 5 Cornerstones
