# run_tests_local.sh

## Name

`run_tests_local.sh` — local test runner for all pykesys-redfish test suites

## Synopsis

```bash
./run_tests_local.sh [SUITE | OPTION | TEST_PATH]
```

## Description

`run_tests_local.sh` runs any combination of the three test suites without Docker or container setup. It uses the project's `uv` environment directly.

The three suites are:

| Suite | Command | What it tests |
|-------|---------|--------------|
| `sdk` | `uv run pytest tests/` | SDK unit tests (default) |
| `django` | `python -m pytest` in `redfish_web/` | Django models, views, serializers |
| `integration` | `uv run pytest tests/integration/` | Full stack vs live emulator |

The integration suite auto-starts the FastAPI emulator (`emulator/`) if it is not already running on `$EMULATOR_PORT`, waits up to 15 seconds for it to respond, runs the tests, then kills it.

## Positional arguments

| Argument | Description |
|----------|-------------|
| *(none)* | Run SDK unit tests (same as `sdk`) |
| `sdk` | SDK unit tests |
| `django` | Django app tests |
| `integration` | Integration tests against the emulator |
| `all` | All three suites in order |
| `--failed`, `--lf` | Rerun only previously failed SDK tests |
| `--ff` | Run failed SDK tests first, then others |
| `clean` | Remove `.pytest_cache` |
| `<test_path>` | Pass directly to `uv run pytest` (SDK tests) |
| `--help`, `-h` | Show usage |

## Options

| Flag | Description |
|------|-------------|
| `--verbose`, `-v` | Pass `-v` to pytest |
| `--coverage` | Enable coverage report (`--cov=pykesys_redfish --cov-report=term-missing`) |

Options can be combined with any suite or test path.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EMULATOR_PORT` | `8888` | Port to start/connect to the emulator |

## Rapid iteration workflow

```bash
# First run — find failures
./run_tests_local.sh sdk

# Rerun only what failed
./run_tests_local.sh --failed

# Verbose output for a specific file
./run_tests_local.sh tests/test_client.py -v

# Clean stale cache
./run_tests_local.sh clean
```

## Cache

Failed test results are stored in `.pytest_cache/` and persist between runs. The `--failed` flag reads this cache to rerun only the tests that failed in the last run. Use `clean` to reset it.

A hint is printed at startup if the previous run had failures:

```
ℹ Previous run: 3 failed test(s) — use --failed to rerun only those
```

## Examples

```bash
# Default: SDK unit tests
./run_tests_local.sh

# All three suites
./run_tests_local.sh all

# SDK tests with coverage
./run_tests_local.sh sdk --coverage

# Only failed from last run
./run_tests_local.sh --failed

# Specific file
./run_tests_local.sh tests/test_fleet.py

# Django tests
./run_tests_local.sh django

# Integration against a custom emulator port
EMULATOR_PORT=9888 ./run_tests_local.sh integration

# Clean pytest cache
./run_tests_local.sh clean
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | All selected tests passed |
| non-zero | Test failures or emulator startup failure |

## See also

- [runtests.sh](runtests-sh.md) — CI-oriented full-suite runner
- [run-dashboard.sh](run-dashboard-sh.md) — interactive test picker (menu option 13)
- [emulator.md](emulator.md) — emulator reference for integration tests
