# pykesys-redfish

**Constitutional boot script. Read these files at every session start (LAW 0 + LAW 15):**

1. `.claude/SESSION_CONTEXT.md` — session state and project identity
2. `.claude/PROJECT_LAWS.md` — 30 constitutional laws (LAW 0-29)
3. `MEMORY.md` — project memory (LAW 19)
4. `.claude/CONSTITUTION-VERSION.md` — current constitutional counts
5. `.claude/RE-ACTION.md` — canonical lessons learned

**Law-mother**: this project is a constitutional source (`role: mother` in `.claude/LAW-LINEAGE.md`).
**Seeded from**: ../template-law-claude on 2026-06-11.

---

## Always

- Log prompts to `docs/prompts.md` BEFORE acting (LAW 1)
- Update `SESSION_CONTEXT.md` at session end — automatically, no asking (LAW 0)
- Deposit accretion stratum in `docs/accretion.md` before final commit (LAW 26)

---

## Project Layout

```
src/pykesys_redfish/
├── client.py          # RedfishClient — core HTTP + session management
├── session.py         # Session token lifecycle
├── exceptions.py      # RedfishError hierarchy
├── resources/         # Typed wrappers for Redfish resource types
├── cli/               # `rf` CLI (Typer + Rich)
└── fleet/             # FleetManager for concurrent multi-BMC operations
tests/                 # pytest suite (uses respx to mock httpx)
docs/                  # Markdown documentation
```

## Setup

```bash
uv sync --extra dev
```

## Running Tests

```bash
uv run pytest
```

## Running the CLI

```bash
uv run rf --help
uv run rf --host 192.168.1.100 -u admin -p password info
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `RF_HOST` | Default BMC hostname/IP |
| `RF_USER` | Default username |
| `RF_PASS` | Default password |
| `RF_VERIFY_SSL` | Set to `false` to skip TLS verification (dev only) |

## Key Conventions

- `RedfishClient` is a context manager — always use `with RedfishClient(...) as rf:`
- Resources are lazy: properties fetch from the cached `_data` dict populated on first access
- CLI commands re-use `RedfishClient` via the shared `pass_context` pattern
- Fleet operations use `ThreadPoolExecutor`; each worker gets its own client instance
- Tests mock at the httpx transport layer via `respx` — never hit real BMCs in tests
