#!/usr/bin/env bash
#
# pykesys-redfish Test Runner
#
# Runs all three test suites: SDK unit tests, Django app tests, and integration
# tests against the live emulator. Designed for CI and local full-suite runs.
#
# Usage:
#   ./runtests.sh                   # Run all suites
#   ./runtests.sh sdk               # SDK unit tests only
#   ./runtests.sh django            # Django app tests only
#   ./runtests.sh integration       # Integration tests (starts emulator)
#   ./runtests.sh --help

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

EMULATOR_PORT="${EMULATOR_PORT:-8888}"
EMULATOR_URL="http://localhost:${EMULATOR_PORT}"

show_help() {
    echo -e "${GREEN}pykesys-redfish Test Runner${NC}"
    echo ""
    echo -e "${YELLOW}USAGE:${NC}"
    echo "  ./runtests.sh [SUITE]"
    echo ""
    echo -e "${YELLOW}SUITES:${NC}"
    echo "  (no args)       Run all three suites in order"
    echo "  sdk             SDK unit tests (uv run pytest)"
    echo "  django          Django app tests (redfish_web/pytest.ini)"
    echo "  integration     Integration tests against live emulator"
    echo ""
    echo -e "${YELLOW}ENVIRONMENT:${NC}"
    echo "  EMULATOR_PORT   Emulator listen port (default: 8888)"
    echo ""
    exit 0
}

run_sdk_tests() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Suite 1/3: SDK Unit Tests${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    cd "${SCRIPT_DIR}"
    uv run pytest --tb=short -q
    echo -e "${GREEN}✓ SDK tests passed${NC}"
}

run_django_tests() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Suite 2/3: Django App Tests${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    cd "${SCRIPT_DIR}/redfish_web"
    python -m pytest --tb=short -q
    echo -e "${GREEN}✓ Django tests passed${NC}"
}

start_emulator() {
    echo -e "${YELLOW}Starting emulator on port ${EMULATOR_PORT}...${NC}"
    cd "${SCRIPT_DIR}/emulator"
    pip install -q -r requirements.txt --index-url https://pypi.apple.com/simple 2>/dev/null || \
    pip install -q -r requirements.txt 2>/dev/null || true
    NUM_NODES=10 uvicorn main:app --port "${EMULATOR_PORT}" --log-level warning &
    EMULATOR_PID=$!

    # Wait for emulator to be ready
    local retries=15
    while [ $retries -gt 0 ]; do
        if curl -sf "${EMULATOR_URL}/redfish/v1/" >/dev/null 2>&1; then
            echo -e "${GREEN}✓ Emulator ready at ${EMULATOR_URL}${NC}"
            return 0
        fi
        sleep 1
        ((retries--))
    done

    echo -e "${RED}✗ Emulator did not start in time${NC}"
    kill "${EMULATOR_PID}" 2>/dev/null || true
    exit 1
}

run_integration_tests() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Suite 3/3: Integration Tests (emulator)${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # Use existing emulator if already running
    if curl -sf "${EMULATOR_URL}/redfish/v1/" >/dev/null 2>&1; then
        echo -e "${YELLOW}ℹ Using already-running emulator at ${EMULATOR_URL}${NC}"
        EMULATOR_PID=""
    else
        start_emulator
    fi

    cd "${SCRIPT_DIR}"
    EMULATOR_URL="${EMULATOR_URL}" uv run pytest tests/integration/ --tb=short -q
    local exit_code=$?

    if [ -n "${EMULATOR_PID}" ]; then
        kill "${EMULATOR_PID}" 2>/dev/null || true
    fi

    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}✓ Integration tests passed${NC}"
    else
        echo -e "${RED}✗ Integration tests failed${NC}"
        exit $exit_code
    fi
}

case "${1:-all}" in
    --help|-h)  show_help ;;
    sdk)        run_sdk_tests ;;
    django)     run_django_tests ;;
    integration) run_integration_tests ;;
    all)
        run_sdk_tests
        run_django_tests
        run_integration_tests
        echo ""
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${GREEN}All suites passed.${NC}"
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        ;;
    *)
        echo -e "${RED}Unknown suite: $1${NC}"
        echo "Run './runtests.sh --help' for usage."
        exit 1
        ;;
esac
