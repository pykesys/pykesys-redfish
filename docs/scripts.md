# Scripts Reference

Shell scripts for running, testing, and managing the pykesys-redfish stack.

## Table of Contents

- [Overview](#overview)
- [run.sh — Production startup](#runsh--production-startup)
- [run-dashboard.sh — Interactive launcher](#run-dashboardsh--interactive-launcher)
- [run_tests_local.sh — Local test runner](#run_tests_localsh--local-test-runner)
- [runtests.sh — Full test suite](#runtestssh--full-test-suite)
- [Choosing the right script](#choosing-the-right-script)

---

## Overview

| Script | Purpose | When to use |
|--------|---------|-------------|
| [`run.sh`](run-sh.md) | Start the Django web app via gunicorn | Production / staging |
| [`run-dashboard.sh`](run-dashboard-sh.md) | Interactive menu for all services and tools | Day-to-day development |
| [`run_tests_local.sh`](run-tests-local-sh.md) | Run any test suite locally | Quick test iterations |
| [`runtests.sh`](runtests-sh.md) | Run all three suites in sequence | CI / pre-push verification |

All scripts are in the project root and are executable (`chmod +x`).

[↑ Back to Top](#table-of-contents)

---

## run.sh — Production startup

Starts the Django web app (`redfish_web/`) via gunicorn. Runs migrations and collects static files before binding.

```bash
./run.sh
```

See [run-sh.md](run-sh.md) for full reference.

[↑ Back to Top](#table-of-contents)

---

## run-dashboard.sh — Interactive launcher

Interactive menu for starting services, running tests, managing Docker Compose, and debugging. The primary development launcher.

```bash
./run-dashboard.sh          # interactive menu
./run-dashboard.sh dev      # start Django dev server
./run-dashboard.sh all      # start all three services in background
./run-dashboard.sh status   # show running service status
```

See [run-dashboard-sh.md](run-dashboard-sh.md) for full reference.

[↑ Back to Top](#table-of-contents)

---

## run_tests_local.sh — Local test runner

Run any combination of the three test suites (SDK, Django, integration) without Docker. Supports `--failed`/`--ff` for rapid iteration.

```bash
./run_tests_local.sh              # SDK unit tests
./run_tests_local.sh all          # all three suites
./run_tests_local.sh --failed     # rerun SDK failures
./run_tests_local.sh integration  # integration tests vs emulator
```

See [run-tests-local-sh.md](run-tests-local-sh.md) for full reference.

[↑ Back to Top](#table-of-contents)

---

## runtests.sh — Full test suite

Runs all three test suites in sequence: SDK unit tests, Django app tests, integration tests. Designed for CI and pre-push verification. Auto-starts the emulator for integration tests.

```bash
./runtests.sh           # all suites
./runtests.sh sdk       # SDK only
./runtests.sh django    # Django only
./runtests.sh integration  # integration only
```

See [runtests-sh.md](runtests-sh.md) for full reference.

[↑ Back to Top](#table-of-contents)

---

## Choosing the right script

```
Day-to-day development:
  → run-dashboard.sh    (interactive menu, service management)

Quick test check:
  → run_tests_local.sh  (fast, no Docker, suite picker)

Pre-push / CI:
  → runtests.sh         (all suites, deterministic, exit code)

Production / staging:
  → run.sh              (gunicorn, production-grade)
```

[↑ Back to Top](#table-of-contents)
