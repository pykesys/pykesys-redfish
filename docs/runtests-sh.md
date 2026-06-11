# runtests.sh

## Name

`runtests.sh` — full test suite runner for CI and pre-push verification

## Synopsis

```bash
./runtests.sh [SUITE]
```

## Description

`runtests.sh` runs any or all of the three pykesys-redfish test suites in sequence. It is designed for CI pipelines and pre-push verification, where you want a deterministic, no-interaction run with a clear exit code.

The three suites run in order:

| # | Suite | Command | Notes |
|---|-------|---------|-------|
| 1 | SDK unit tests | `uv run pytest --tb=short -q tests/` | Always run first |
| 2 | Django app tests | `python -m pytest --tb=short -q` in `redfish_web/` | Requires Django deps |
| 3 | Integration tests | `uv run pytest tests/integration/` | Auto-starts emulator |

For the integration suite, if an emulator is not already running at `$EMULATOR_URL`, the script starts one from `emulator/`, waits up to 15 seconds for it to be ready, runs the tests, then kills it.

## Arguments

| Argument | Description |
|----------|-------------|
| *(none)*, `all` | Run all three suites |
| `sdk` | SDK unit tests only |
| `django` | Django app tests only |
| `integration` | Integration tests only |
| `--help`, `-h` | Show usage |

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EMULATOR_PORT` | `8888` | Port for the emulator (integration suite) |
| `EMULATOR_URL` | `http://localhost:$EMULATOR_PORT` | Override full emulator URL |

## Exit behaviour

- Each suite runs with `set -e`. Any test failure stops execution and exits with a non-zero code.
- A success banner is printed only if all selected suites pass.
- The integration suite's emulator child process is killed on exit regardless of whether tests passed or failed.

## CI usage

```yaml
# GitHub Actions example
- name: Run tests
  run: ./runtests.sh

# Run only unit suites (no emulator needed)
- name: SDK + Django tests
  run: ./runtests.sh sdk && ./runtests.sh django
```

```bash
# docker-compose.ci.yml already handles the full stack:
docker compose -f docker-compose.ci.yml up \
  --abort-on-container-exit \
  --exit-code-from tests
```

## Examples

```bash
# All suites
./runtests.sh

# SDK tests only
./runtests.sh sdk

# Django tests only
./runtests.sh django

# Integration tests against an already-running emulator
EMULATOR_URL=http://localhost:8888 ./runtests.sh integration

# Integration tests against a custom port
EMULATOR_PORT=9888 ./runtests.sh integration
```

## Output

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Suite 1/3: SDK Unit Tests
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
27 passed in 0.49s
✓ SDK tests passed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Suite 2/3: Django App Tests
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
...
✓ Django tests passed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Suite 3/3: Integration Tests (emulator)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Starting Redfish emulator on port 8888...
✓ Emulator ready at http://localhost:8888
...
✓ Integration tests passed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
All suites passed.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | All selected suites passed |
| non-zero | At least one suite failed or emulator did not start |

## See also

- [run_tests_local.sh](run-tests-local-sh.md) — interactive/iterative local runner
- [run-dashboard.sh](run-dashboard-sh.md) — interactive menu launcher
- [emulator.md](emulator.md) — emulator reference
