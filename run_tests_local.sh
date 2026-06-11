#!/usr/bin/env bash
#
# pykesys-redfish Local Test Runner
#
# Runs any combination of the three test suites locally using the project's
# uv environment. No containers, no secrets.
#
# Usage:
#   ./run_tests_local.sh                    # Run SDK tests (default)
#   ./run_tests_local.sh sdk                # SDK unit tests
#   ./run_tests_local.sh django             # Django app tests
#   ./run_tests_local.sh integration        # Integration tests (auto-starts emulator)
#   ./run_tests_local.sh all                # All three suites
#   ./run_tests_local.sh --failed           # Rerun only last SDK test failures
#   ./run_tests_local.sh --ff               # Failed SDK tests first, then others
#   ./run_tests_local.sh <test_path>        # Run specific SDK test path
#   ./run_tests_local.sh clean              # Clean pytest caches
#   ./run_tests_local.sh --help             # Show this help

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTEST_CACHE_DIR="${SCRIPT_DIR}/.pytest_cache"
EMULATOR_PORT="${EMULATOR_PORT:-8888}"
EMULATOR_URL="http://localhost:${EMULATOR_PORT}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

show_help() {
    echo -e "${GREEN}pykesys-redfish Local Test Runner${NC}"
    echo ""
    echo -e "${YELLOW}USAGE:${NC}"
    echo "  ./run_tests_local.sh [OPTIONS | SUITE | TEST_PATH]"
    echo ""
    echo -e "${YELLOW}SUITES:${NC}"
    echo "  (no args)              SDK unit tests (uv run pytest)"
    echo "  sdk                    SDK unit tests"
    echo "  django                 Django app tests (redfish_web/)"
    echo "  integration            Integration tests (auto-starts emulator)"
    echo "  all                    All three suites in order"
    echo ""
    echo -e "${YELLOW}OPTIONS:${NC}"
    echo "  --failed, --lf         Rerun only previously failed SDK tests"
    echo "  --ff                   Run failed SDK tests first, then others"
    echo "  --verbose, -v          Verbose pytest output"
    echo "  --coverage             Enable coverage report"
    echo "  clean                  Remove .pytest_cache"
    echo "  --help, -h             Show this message"
    echo ""
    echo -e "${YELLOW}EXAMPLES:${NC}"
    echo "  ./run_tests_local.sh                          # SDK unit tests"
    echo "  ./run_tests_local.sh all                      # All three suites"
    echo "  ./run_tests_local.sh --failed                 # Rerun SDK failures"
    echo "  ./run_tests_local.sh tests/test_client.py     # Specific SDK test file"
    echo "  ./run_tests_local.sh django                   # Django app tests only"
    echo "  ./run_tests_local.sh integration              # Integration vs emulator"
    echo ""
    echo -e "${YELLOW}EMULATOR:${NC}"
    echo "  Set EMULATOR_PORT to override the emulator port (default: 8888)"
    echo "  If an emulator is already running, integration tests use it directly."
    echo ""
    exit 0
}

# ────────────────────────────────────────────────────────────────────────────
# Helpers

clean_caches() {
    echo -e "${YELLOW}Cleaning pytest cache...${NC}"
    if [ -d "${PYTEST_CACHE_DIR}" ]; then
        SIZE=$(du -sh "${PYTEST_CACHE_DIR}" 2>/dev/null | cut -f1 || echo "unknown")
        echo "  .pytest_cache: ${SIZE}"
        rm -rf "${PYTEST_CACHE_DIR}"
    fi
    echo -e "${GREEN}✓ Cache cleaned${NC}"
    exit 0
}

show_failed_hint() {
    if [ -f "${PYTEST_CACHE_DIR}/v/cache/lastfailed" ]; then
        local count
        count=$(grep -o '"' "${PYTEST_CACHE_DIR}/v/cache/lastfailed" | wc -l | xargs)
        count=$((count / 2))
        if [ "${count}" -gt 0 ]; then
            echo -e "${BLUE}ℹ Previous run: ${count} failed test(s) — use --failed to rerun only those${NC}"
        fi
    fi
}

start_emulator() {
    echo -e "${YELLOW}Starting Redfish emulator on port ${EMULATOR_PORT}...${NC}"
    cd "${SCRIPT_DIR}/emulator"
    pip install -q -r requirements.txt 2>/dev/null || true
    NUM_NODES=10 uvicorn main:app --port "${EMULATOR_PORT}" --log-level warning &
    EMULATOR_PID=$!
    cd "${SCRIPT_DIR}"

    local retries=15
    while [ $retries -gt 0 ]; do
        if curl -sf "${EMULATOR_URL}/redfish/v1/" >/dev/null 2>&1; then
            echo -e "${GREEN}✓ Emulator ready at ${EMULATOR_URL}${NC}"
            return 0
        fi
        sleep 1
        ((retries--))
    done

    echo -e "${RED}✗ Emulator did not respond in time${NC}"
    kill "${EMULATOR_PID}" 2>/dev/null || true
    exit 1
}

# ────────────────────────────────────────────────────────────────────────────
# Parse flags

VERBOSE=""
COVERAGE=""

for arg in "$@"; do
    case "$arg" in
        --verbose|-v) VERBOSE="-v" ;;
        --coverage)   COVERAGE="--cov=pykesys_redfish --cov-report=term-missing" ;;
    esac
done

# ────────────────────────────────────────────────────────────────────────────
# Dispatch

case "${1:-sdk}" in
    --help|-h)   show_help ;;
    clean)       clean_caches ;;

    sdk|"")
        cd "${SCRIPT_DIR}"
        show_failed_hint
        echo -e "${GREEN}=== SDK Unit Tests ===${NC}"
        uv run pytest ${VERBOSE} ${COVERAGE} tests/
        echo -e "${GREEN}✓ SDK tests passed${NC}"
        ;;

    --failed|--lf)
        cd "${SCRIPT_DIR}"
        echo -e "${YELLOW}Rerunning previously failed SDK tests...${NC}"
        uv run pytest --lf ${VERBOSE} ${COVERAGE}
        echo -e "${GREEN}✓ Done${NC}"
        ;;

    --ff)
        cd "${SCRIPT_DIR}"
        echo -e "${YELLOW}Running failed SDK tests first...${NC}"
        uv run pytest --ff ${VERBOSE} ${COVERAGE}
        echo -e "${GREEN}✓ Done${NC}"
        ;;

    django)
        echo -e "${GREEN}=== Django App Tests ===${NC}"
        cd "${SCRIPT_DIR}/redfish_web"
        python -m pytest ${VERBOSE} --tb=short -q
        echo -e "${GREEN}✓ Django tests passed${NC}"
        ;;

    integration)
        echo -e "${GREEN}=== Integration Tests ===${NC}"
        EMULATOR_PID=""
        if curl -sf "${EMULATOR_URL}/redfish/v1/" >/dev/null 2>&1; then
            echo -e "${YELLOW}ℹ Using existing emulator at ${EMULATOR_URL}${NC}"
        else
            start_emulator
        fi
        cd "${SCRIPT_DIR}"
        EMULATOR_URL="${EMULATOR_URL}" uv run pytest tests/integration/ ${VERBOSE} --tb=short -q
        EXIT=$?
        [ -n "${EMULATOR_PID}" ] && kill "${EMULATOR_PID}" 2>/dev/null || true
        if [ $EXIT -eq 0 ]; then
            echo -e "${GREEN}✓ Integration tests passed${NC}"
        else
            echo -e "${RED}✗ Integration tests failed${NC}"
            exit $EXIT
        fi
        ;;

    all)
        cd "${SCRIPT_DIR}"
        echo -e "${GREEN}=== Running All Test Suites ===${NC}"
        echo ""

        echo -e "${BLUE}[1/3] SDK Unit Tests${NC}"
        uv run pytest ${VERBOSE} --tb=short -q tests/
        echo -e "${GREEN}✓ SDK${NC}"
        echo ""

        echo -e "${BLUE}[2/3] Django App Tests${NC}"
        cd "${SCRIPT_DIR}/redfish_web"
        python -m pytest ${VERBOSE} --tb=short -q
        echo -e "${GREEN}✓ Django${NC}"
        echo ""

        echo -e "${BLUE}[3/3] Integration Tests${NC}"
        EMULATOR_PID=""
        if curl -sf "${EMULATOR_URL}/redfish/v1/" >/dev/null 2>&1; then
            echo -e "${YELLOW}ℹ Using existing emulator at ${EMULATOR_URL}${NC}"
        else
            start_emulator
        fi
        cd "${SCRIPT_DIR}"
        EMULATOR_URL="${EMULATOR_URL}" uv run pytest tests/integration/ ${VERBOSE} --tb=short -q
        EXIT=$?
        [ -n "${EMULATOR_PID}" ] && kill "${EMULATOR_PID}" 2>/dev/null || true
        [ $EXIT -ne 0 ] && exit $EXIT
        echo -e "${GREEN}✓ Integration${NC}"

        echo ""
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${GREEN}All suites passed.${NC}"
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        ;;

    *)
        # Specific test path — passed directly to SDK pytest
        cd "${SCRIPT_DIR}"
        echo -e "${YELLOW}Running: $*${NC}"
        uv run pytest ${VERBOSE} ${COVERAGE} "$@"
        ;;
esac
