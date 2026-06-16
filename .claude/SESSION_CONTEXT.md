# SESSION_CONTEXT — pykesys-redfish

**Role**: Law-mother (constitutional source)
**Seeded from**: ../template-law-claude on 2026-06-11
**Constitutional state**: 30 laws (LAW 0-29), full adoption
**Last Updated**: 2026-06-16 — Session 2: full build — docs, emulator, Django web, touchscreen tutorial, ladder + cascade

---

## Table of Contents

- [Current State](#current-state)
- [Project Identity](#project-identity)
- [Constitutional Architecture](#constitutional-architecture)
- [Key Files to Read on Restoration](#key-files-to-read-on-restoration)
- [Restoration Instructions](#restoration-instructions)
- [Ladder Run Log](#ladder-run-log)
- [History](#history)

---

## Current State

**Branch**: main
**Status**: Clean — constitutional adoption complete, 5 bugs fixed, all tests passing (27/27)
**What's working**: Full SDK + CLI + Django web + React frontend stack

---

## Project Identity

pykesys-redfish is a Python SDK, CLI, and fleet automation framework for the DMTF Redfish BMC
management API.

**Three-tier stack**:
- `src/pykesys_redfish/` — core SDK: `RedfishClient` (context manager), `RedfishSession`
  (httpx transport + session-token/basic-auth), `resources/` (lazy-loading typed wrappers),
  `fleet/` (ThreadPoolExecutor fan-out), `cli/` (Typer+Rich `rf` CLI)
- `redfish_web/` — Django + DRF backend: hosts, inventory, alerts, scheduler apps;
  APScheduler for background polling; SQLite; whitenoise static files
- `frontend/` — Vite/React 18 SPA ("redfish-observability"), Tailwind CSS, React Router v6

**Test suite**: 27 tests, respx mocks at httpx transport layer, 74% coverage.

---

## Constitutional Architecture

- **30 laws (LAW 0-29)** — see `.claude/PROJECT_LAWS.md`
- 4 META-LAWs
- 6 Universal Principles — see `.claude/LEXICON.md`
- 5 Cornerstones + deepenings — see `.claude/FOUNDATIONS.md`
- Four Books: LAW / ACTION / RE-ACTION / EPIPHANIES
- 41 constitutional service units in `.claude/.init/`
- Hooks: `.claude/hooks/law-0-enforcer.sh` (Stop hook) + `session-loader.sh` (UserPromptSubmit)

---

## Key Files to Read on Restoration

**Read in this order:**
1. `.claude/SESSION_CONTEXT.md` (this file)
2. `.claude/PROJECT_LAWS.md` (30 laws LAW 0-29)
3. `MEMORY.md` (project identity + last significant change)
4. `.claude/CONSTITUTION-VERSION.md` (current counts)
5. `.claude/RE-ACTION.md` (canonical lessons)
6. `.claude/FOUNDATIONS.md` (cornerstones + deepenings)
7. `.claude/LEXICON.md` (universal principles)

---

## Restoration Instructions

**When returning to this project:**

1. Read this file
2. Run `uv run pytest --tb=short -q` to verify green baseline
3. Check `git status` for any staged/unstaged work
4. Resume from MEMORY.md `## Last Significant Change`

---

## Ladder Run Log

*Written by /ladder at session open. Proof of execution.*

### 2026-06-16 — Ladder Run

Rung 2: PASS (30 law units, 4 meta-law units)
Rung 3: PASS (first node: "Log prompts to `docs/prompts.md` BEFORE acting (LAW 1)")
Rung 4: FAIL→FIXED — stratum deposited for 2026-06-16 session
Rung 5: PASS (Last change: "2026-06-11 — Constitutional governance adopted (law-mother declaration). Five bugs fixed: ...")
Rung 8: PASS (30 laws, LAW 0-29 — "✓ All constitutional invariants satisfied")
Rung 11: SKIP (law-mother)
Full State: FIXED — Rung 1 (9 docs/ files: TOC+BTT added); LAW 1 (docs/prompts.md created); Rung 4 (stratum deposited)

---

## History

**2026-06-11 — Session 1: Constitutional adoption + bug fixes**
- Declared pykesys-redfish a Law-mother
- Full constitutional framework seeded from template-law-claude
- 5 bugs found and fixed (see MEMORY.md)
- All 27 tests passing
