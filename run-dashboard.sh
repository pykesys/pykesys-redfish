#!/usr/bin/env bash
#
# pykesys-redfish Dashboard Runner
# Interactive launcher for all project services and tools
#
# Usage:
#   ./run-dashboard.sh                  # Interactive menu
#   ./run-dashboard.sh dev              # Start Django dev server
#   ./run-dashboard.sh frontend         # Start React frontend dev server
#   ./run-dashboard.sh emulator         # Start Redfish BMC emulator
#   ./run-dashboard.sh shell            # Django interactive shell
#   ./run-dashboard.sh migrate          # Run migrations
#   ./run-dashboard.sh test             # Interactive pytest runner
#   ./run-dashboard.sh all              # Start all three services (local)
#   ./run-dashboard.sh stop             # Stop all background services
#   ./run-dashboard.sh status           # Show service status
#   ./run-dashboard.sh help             # Show this help message
#

set -e

DEBUG="true"
DATE=$(date +%Y-%m-%d:%H:%M)
USER=$(whoami)

# Colors
NC='\033[0m'
BLACK='\033[0;30m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
ORANGE='\033[38;5;208m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[0;37m'
BOLD_BLACK='\033[1;30m'
BOLD_RED='\033[1;31m'
BOLD_GREEN='\033[1;32m'
BOLD_YELLOW='\033[1;33m'
BOLD_BLUE='\033[1;34m'
BOLD_MAGENTA='\033[1;35m'
BOLD_CYAN='\033[1;36m'
BOLD_WHITE='\033[1;37m'
BRIGHT_BLACK='\033[0;90m'
BRIGHT_RED='\033[0;91m'
BRIGHT_GREEN='\033[0;92m'
BRIGHT_YELLOW='\033[0;93m'
BRIGHT_BLUE='\033[0;94m'
BRIGHT_MAGENTA='\033[0;95m'
BRIGHT_CYAN='\033[0;96m'
BRIGHT_WHITE='\033[0;97m'

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="${SCRIPT_DIR}/log"
WEB_DIR="${SCRIPT_DIR}/redfish_web"
FRONTEND_DIR="${SCRIPT_DIR}/frontend"
EMULATOR_DIR="${SCRIPT_DIR}/emulator"

# Default ports
WEB_PORT="${WEB_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
EMULATOR_PORT="${EMULATOR_PORT:-8888}"

####
# Banner
function show_banner() {
    echo -e "${BRIGHT_BLUE}"
    echo "╔════════════════════════════════════════════════╗"
    echo "║     pykesys-redfish Dashboard Runner           ║"
    echo "║     DGX SuperPod Observability & Control       ║"
    echo "╚════════════════════════════════════════════════╝"
    if [ "$DEBUG" == "true" ]; then
        echo -e "${BRIGHT_RED}"
        echo "╔════════════════════════════════════════════════╗"
        echo "║              Debug Information                 ║"
        echo "║ Script Dir  : ${SCRIPT_DIR}"
        echo "║ Log Dir     : ${LOG}"
        echo "║ Date        : ${DATE}"
        echo "║ User        : ${USER}"
        echo "╚════════════════════════════════════════════════╝"
        echo -e "${NC}"
    else
        echo -e "${NC}"
    fi
}

####
# Toggle DEBUG mode
function toggle_debug() {
    if [ "$DEBUG" == "true" ]; then
        DEBUG="false"
        echo -e "${YELLOW}Debug mode disabled${NC}"
    else
        DEBUG="true"
        echo -e "${BRIGHT_GREEN}Debug mode enabled${NC}"
    fi
    sleep 1
}

####
# Menu
function show_menu() {
    echo -e "${YELLOW}Services:${NC}\n"
    echo -e "  ${GREEN} 1)${NC} ${BRIGHT_GREEN}Run: Django Dev Server   ${BLUE}(http://localhost:${WEB_PORT})${NC}"
    echo -e "  ${GREEN} 2)${NC} ${BRIGHT_GREEN}Run: React Frontend      ${BLUE}(http://localhost:${FRONTEND_PORT})${NC}"
    echo -e "  ${GREEN} 3)${NC} ${BRIGHT_GREEN}Run: Redfish Emulator    ${BLUE}(http://localhost:${EMULATOR_PORT})${NC}"
    echo -e "  ${GREEN} 4)${NC} ${ORANGE}Run: All Services        ${BLUE}(web + frontend + emulator in background)${NC}"
    echo -e "  ${GREEN} 5)${NC} ${BRIGHT_RED}Stop: All Services       ${BLUE}(stop background processes)${NC}"
    echo -e "  ${GREEN} 6)${NC} ${ORANGE}Status: Services         ${BLUE}(show running services)${NC}"
    echo ""
    echo -e "${YELLOW}Django:${NC}\n"
    echo -e "  ${GREEN} 7)${NC} ${ORANGE}Run: Django Shell        ${BLUE}(interactive Python console)${NC}"
    echo -e "  ${GREEN} 8)${NC} ${ORANGE}Run: Migrations          ${BLUE}(makemigrations + migrate)${NC}"
    echo ""
    echo -e "${YELLOW}Testing:${NC}\n"
    echo -e "  ${GREEN} 9)${NC} ${ORANGE}Run: SDK Unit Tests      ${BLUE}(uv run pytest tests/)${NC}"
    echo -e "  ${GREEN}10)${NC} ${ORANGE}Run: Django Tests        ${BLUE}(redfish_web pytest)${NC}"
    echo -e "  ${GREEN}11)${NC} ${ORANGE}Run: Integration Tests   ${BLUE}(requires emulator on :${EMULATOR_PORT})${NC}"
    echo -e "  ${GREEN}12)${NC} ${ORANGE}Run: All Tests           ${BLUE}(all three suites)${NC}"
    echo -e "  ${GREEN}13)${NC} ${ORANGE}Run: Interactive pytest  ${BLUE}(categorized file picker)${NC}"
    echo ""
    echo -e "${YELLOW}Docker Compose:${NC}\n"
    echo -e "  ${GREEN}14)${NC} ${BRIGHT_GREEN}Docker: Up               ${BLUE}(docker compose up)${NC}"
    echo -e "  ${GREEN}15)${NC} ${BRIGHT_RED}Docker: Down             ${BLUE}(docker compose down)${NC}"
    echo -e "  ${GREEN}16)${NC} ${ORANGE}Docker: Logs             ${BLUE}(docker compose logs -f)${NC}"
    echo ""

    if [ "$DEBUG" == "true" ]; then
        echo -e "  ${CYAN}Debug:${NC} ${BRIGHT_GREEN}ENABLED${NC}  ${MAGENTA}[d to toggle]${NC}"
    else
        echo -e "  ${CYAN}Debug:${NC} ${BRIGHT_BLACK}disabled${NC}  ${MAGENTA}[d to toggle]${NC}"
    fi

    echo ""
    echo -e "  ${BRIGHT_RED}q)${NC} Quit"
    echo ""
}

############
# Service Management

####
# Django dev server
function run_development() {
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}Starting Django Development Server            ${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}Access at: http://localhost:${WEB_PORT}${NC}\n"
    mkdir -p "${LOG}"
    cd "${WEB_DIR}"
    python manage.py runserver "0.0.0.0:${WEB_PORT}" 2>&1 | tee -a "${LOG}/run-web.log"
}

####
# React frontend dev server
function run_frontend() {
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}Starting React Frontend Dev Server            ${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}Access at: http://localhost:${FRONTEND_PORT}${NC}\n"
    mkdir -p "${LOG}"
    cd "${FRONTEND_DIR}"
    if [ ! -d "node_modules" ]; then
        echo -e "${CYAN}Installing npm dependencies...${NC}"
        npm install
    fi
    npm run dev 2>&1 | tee -a "${LOG}/run-frontend.log"
}

####
# Redfish BMC emulator
function run_emulator() {
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}Starting Redfish BMC Emulator                 ${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}Access at: http://localhost:${EMULATOR_PORT}${NC}"
    echo -e "${YELLOW}Docs at:   http://localhost:${EMULATOR_PORT}/docs${NC}\n"
    mkdir -p "${LOG}"
    cd "${EMULATOR_DIR}"
    pip install -q -r requirements.txt 2>/dev/null || true
    NUM_NODES=10 uvicorn main:app --port "${EMULATOR_PORT}" --reload \
        2>&1 | tee -a "${LOG}/run-emulator.log"
}

####
# Django interactive shell
function run_console() {
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}Starting Django Shell                         ${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    cd "${WEB_DIR}"
    python manage.py shell
}

####
# Run Django migrations
function run_migrations() {
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}Running Django Migrations                     ${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    mkdir -p "${LOG}"
    cd "${WEB_DIR}"
    echo -e "${CYAN}Running makemigrations...${NC}"
    python manage.py makemigrations 2>&1 | tee -a "${LOG}/run-migrations.log"
    echo -e "${CYAN}Running migrate...${NC}"
    python manage.py migrate --run-syncdb 2>&1 | tee -a "${LOG}/run-migrations.log"
    echo -e "${GREEN}✓ Migrations complete. Log: ${LOG}/run-migrations.log${NC}"
}

############
# Test Runners

function run_sdk_tests() {
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}SDK Unit Tests                                ${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    mkdir -p "${LOG}"
    cd "${SCRIPT_DIR}"
    uv run pytest tests/ -v --tb=short 2>&1 | tee -a "${LOG}/pytest-sdk-${DATE}.log"
}

function run_django_tests() {
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}Django App Tests                              ${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    mkdir -p "${LOG}"
    cd "${WEB_DIR}"
    python -m pytest -v --tb=short 2>&1 | tee -a "${LOG}/pytest-django-${DATE}.log"
}

function run_integration_tests() {
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}Integration Tests                             ${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    local emulator_pid=""
    local emulator_url="http://localhost:${EMULATOR_PORT}"

    if ! curl -sf "${emulator_url}/redfish/v1/" >/dev/null 2>&1; then
        echo -e "${YELLOW}Emulator not running — starting on port ${EMULATOR_PORT}...${NC}"
        cd "${EMULATOR_DIR}"
        pip install -q -r requirements.txt 2>/dev/null || true
        NUM_NODES=10 uvicorn main:app --port "${EMULATOR_PORT}" --log-level warning &
        emulator_pid=$!
        cd "${SCRIPT_DIR}"
        local retries=15
        while [ $retries -gt 0 ]; do
            curl -sf "${emulator_url}/redfish/v1/" >/dev/null 2>&1 && break
            sleep 1; ((retries--))
        done
        if [ $retries -eq 0 ]; then
            echo -e "${RED}✗ Emulator did not start${NC}"
            kill "$emulator_pid" 2>/dev/null || true
            return 1
        fi
        echo -e "${GREEN}✓ Emulator ready${NC}"
    else
        echo -e "${YELLOW}ℹ Using existing emulator at ${emulator_url}${NC}"
    fi

    mkdir -p "${LOG}"
    cd "${SCRIPT_DIR}"
    EMULATOR_URL="${emulator_url}" uv run pytest tests/integration/ -v --tb=short \
        2>&1 | tee -a "${LOG}/pytest-integration-${DATE}.log"
    local exit_code=$?

    [ -n "${emulator_pid}" ] && kill "${emulator_pid}" 2>/dev/null || true
    return $exit_code
}

function run_all_tests() {
    run_sdk_tests
    run_django_tests
    run_integration_tests
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}All test suites complete.${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

############
# Interactive pytest Runner

build_test_categories() {
    local test_dir="${1:-tests}"
    find "${test_dir}" -maxdepth 1 -name "test_*.py" -type f 2>/dev/null | sort | awk -F'/' '{
        filename = $NF
        sub(/^test_/, "", filename)
        sub(/\.py$/, "", filename)
        n = split(filename, parts, "_")
        category = (n > 1) ? parts[n] : filename
        if (categories[category] == "") {
            categories[category] = $0
            category_list[++num_categories] = category
        } else {
            categories[category] = categories[category] "|" $0
        }
    }
    END {
        for (i = 1; i <= num_categories; i++)
            for (j = i + 1; j <= num_categories; j++)
                if (category_list[i] > category_list[j]) {
                    temp = category_list[i]; category_list[i] = category_list[j]; category_list[j] = temp
                }
        for (i = 1; i <= num_categories; i++) {
            cat = category_list[i]; print cat ":::" categories[cat]
        }
    }'
}

show_test_type_menu() {
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}Interactive pytest Test Runner                 ${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${YELLOW}Select Test Category (SDK tests/):${NC}"
    echo ""

    local idx=1
    while read -r line; do
        local category count files
        category=$(echo "$line" | cut -d':' -f1)
        files=$(echo "$line" | cut -d':' -f4-)
        count=$(echo "$files" | tr '|' '\n' | wc -l | xargs)
        printf "  ${CYAN}%2d${NC}) ${BOLD_GREEN}%-20s${NC} ${BLUE}(%d file" "$idx" "$category" "$count"
        [ "$count" -gt 1 ] && echo "s)${NC}" || echo ")${NC}"
        ((idx++))
    done < <(build_test_categories "tests")

    local total
    total=$(find tests -maxdepth 1 -name "test_*.py" -type f 2>/dev/null | wc -l | xargs)
    echo ""
    printf "  ${YELLOW}%2s${NC}) Run ${BOLD_GREEN}entire SDK suite${NC} (all %d files)\n" "a" "$total"
    echo ""
    printf "  ${MAGENTA}%2s${NC}) Back\n" "b"
    printf "  ${BRIGHT_RED}%2s${NC}) Quit\n" "q"
    echo ""
}

run_single_test_with_spinner() {
    local test_file="${1}" category="${2:-unknown}"
    local filename log_file
    filename=$(basename "$test_file" .py)
    log_file="${LOG}/pytest-${category}-${filename}-${DATE}.log"

    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}Running: ${BOLD_GREEN}$(basename "$test_file")${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    mkdir -p "${LOG}"

    local spin_chars='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    {
        echo "Category: $category | File: $test_file | Date: $DATE" > "$log_file"
        cd "${SCRIPT_DIR}"
        uv run pytest "$test_file" -v --no-cov >> "$log_file" 2>&1
    } &
    local pid=$!

    while kill -0 "$pid" 2>/dev/null; do
        for i in $(seq 0 $((${#spin_chars}-1))); do
            kill -0 "$pid" 2>/dev/null || break
            printf "\r${ORANGE}%s${NC} %s..." "${spin_chars:$i:1}" "$filename"
            sleep 0.1
        done
    done
    wait "$pid"
    local exit_status=$?
    printf "\r\033[K"

    if [ $exit_status -eq 0 ]; then
        echo -e "${GREEN}✓ Passed: ${BOLD_WHITE}$filename${NC}"
    else
        echo -e "${RED}✗ Failed: ${BOLD_WHITE}$filename${NC} (exit: $exit_status)"
    fi
    echo -e "${CYAN}  Log: ${log_file}${NC}"
    echo ""
    return $exit_status
}

function run_tests() {
    cd "${SCRIPT_DIR}"
    [ ! -d "tests" ] && echo -e "${RED}Error: tests/ not found${NC}" && return 1

    while true; do
        show_test_type_menu
        read -rp "Select category: " type_choice
        echo ""

        [[ "$type_choice" =~ ^[qQ]$ ]] && return 0
        [[ "$type_choice" =~ ^[bB]$ ]] && return 0

        if [[ "$type_choice" =~ ^[aA]$ ]]; then
            mkdir -p "${LOG}"
            uv run pytest tests/ -v --no-cov 2>&1 | tee -a "${LOG}/pytest-full-${DATE}.log"
            read -rp "Press Enter to continue..."
            continue
        fi

        [[ ! "$type_choice" =~ ^[0-9]+$ ]] && echo -e "${BRIGHT_RED}Invalid.${NC}" && sleep 2 && continue

        local categories_cache=() files_cache=() idx=0
        while read -r line; do
            categories_cache[$idx]=$(echo "$line" | cut -d':' -f1)
            files_cache[$idx]=$(echo "$line" | cut -d':' -f4-)
            ((idx++))
        done < <(build_test_categories "tests")

        local num_categories=${#categories_cache[@]}
        [[ "$type_choice" -lt 1 || "$type_choice" -gt "$num_categories" ]] && \
            echo -e "${BRIGHT_RED}Invalid (1-${num_categories}).${NC}" && sleep 2 && continue

        local sel_idx=$((type_choice - 1))
        local sel_cat="${categories_cache[$sel_idx]}"
        local sel_files="${files_cache[$sel_idx]}"

        while true; do
            echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            echo -e "${GREEN}Category: ${BOLD_GREEN}${sel_cat}${NC}"
            echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            echo ""
            echo -e "${YELLOW}Test Files:${NC}"
            echo ""
            local files=()
            while read -r f; do files+=("$f"); done < <(echo "$sel_files" | tr '|' '\n')
            local num_files=${#files[@]}
            for i in "${!files[@]}"; do
                printf "  ${CYAN}%2d${NC}) %s\n" "$((i+1))" "$(basename "${files[$i]}" .py)"
            done
            echo ""
            printf "  ${YELLOW}%2s${NC}) Run all in category\n" "a"
            printf "  ${MAGENTA}%2s${NC}) Back\n" "b"
            printf "  ${BRIGHT_RED}%2s${NC}) Quit\n" "q"
            echo ""
            read -rp "Select a file: " file_choice
            echo ""

            [[ "$file_choice" =~ ^[qQ]$ ]] && return 0
            [[ "$file_choice" =~ ^[bB]$ ]] && break

            if [[ "$file_choice" =~ ^[aA]$ ]]; then
                for f in "${files[@]}"; do
                    run_single_test_with_spinner "$f" "$sel_cat" || true
                done
                read -rp "Press Enter to continue..."
                continue
            fi

            [[ ! "$file_choice" =~ ^[0-9]+$ || "$file_choice" -lt 1 || "$file_choice" -gt "$num_files" ]] && \
                echo -e "${BRIGHT_RED}Invalid.${NC}" && sleep 2 && continue

            local sel_file="${files[$((file_choice-1))]}"
            run_single_test_with_spinner "$sel_file" "$sel_cat" || true

            read -rp "View log? (y/N): " view_log
            [[ "$view_log" =~ ^[Yy]$ ]] && less "${LOG}/pytest-${sel_cat}-$(basename "$sel_file" .py)-${DATE}.log"
            read -rp "Press Enter to continue..."
        done
    done
}

############
# Background Service Management

function run_all() {
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}Starting All Services in Background           ${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    mkdir -p "${LOG}"

    # Django dev server
    echo -e "${CYAN}Starting Django dev server...${NC}"
    cd "${WEB_DIR}"
    python manage.py runserver "0.0.0.0:${WEB_PORT}" > "${LOG}/run-web.log" 2>&1 &
    WEB_PID=$!
    echo "$WEB_PID" > "${SCRIPT_DIR}/.web.pid"
    echo -e "${GREEN}✓ Django (PID: $WEB_PID) — http://localhost:${WEB_PORT}${NC}"
    echo -e "  Log: ${LOG}/run-web.log"

    # React frontend
    echo -e "${CYAN}Starting React frontend...${NC}"
    cd "${FRONTEND_DIR}"
    [ ! -d "node_modules" ] && npm install -q
    npm run dev > "${LOG}/run-frontend.log" 2>&1 &
    FRONTEND_PID=$!
    echo "$FRONTEND_PID" > "${SCRIPT_DIR}/.frontend.pid"
    echo -e "${GREEN}✓ Frontend (PID: $FRONTEND_PID) — http://localhost:${FRONTEND_PORT}${NC}"
    echo -e "  Log: ${LOG}/run-frontend.log"

    # Emulator
    echo -e "${CYAN}Starting Redfish emulator...${NC}"
    cd "${EMULATOR_DIR}"
    pip install -q -r requirements.txt 2>/dev/null || true
    NUM_NODES=10 uvicorn main:app --port "${EMULATOR_PORT}" --log-level warning > "${LOG}/run-emulator.log" 2>&1 &
    EMULATOR_PID=$!
    echo "$EMULATOR_PID" > "${SCRIPT_DIR}/.emulator.pid"
    echo -e "${GREEN}✓ Emulator (PID: $EMULATOR_PID) — http://localhost:${EMULATOR_PORT}${NC}"
    echo -e "  Log: ${LOG}/run-emulator.log"

    echo ""
    echo -e "${GREEN}All services started. Use './run-dashboard.sh stop' to stop them.${NC}"
    echo -e "${CYAN}Tailing logs (Ctrl+C to stop watching — services keep running)...${NC}"
    echo ""
    cd "${SCRIPT_DIR}"
    tail -f "${LOG}/run-web.log" "${LOG}/run-frontend.log" "${LOG}/run-emulator.log"
}

function stop_services() {
    echo -e "${YELLOW}Stopping all background services...${NC}\n"
    for svc in web frontend emulator; do
        local pid_file="${SCRIPT_DIR}/.${svc}.pid"
        if [ -f "$pid_file" ]; then
            local pid
            pid=$(cat "$pid_file")
            if ps -p "$pid" > /dev/null 2>&1; then
                kill "$pid"
                echo -e "${GREEN}✓ Stopped ${svc} (PID: $pid)${NC}"
            else
                echo -e "${YELLOW}⚠ ${svc} not running (stale PID)${NC}"
            fi
            rm "$pid_file"
        else
            echo -e "${BRIGHT_BLACK}○ ${svc} — no PID file${NC}"
        fi
    done
    echo ""
    echo -e "${GREEN}Done.${NC}"
}

function show_status() {
    echo -e "${CYAN}Service Status:${NC}\n"
    for svc in web frontend emulator; do
        local pid_file="${SCRIPT_DIR}/.${svc}.pid"
        if [ -f "$pid_file" ]; then
            local pid
            pid=$(cat "$pid_file")
            if ps -p "$pid" > /dev/null 2>&1; then
                echo -e "  ${GREEN}✓ ${svc} running (PID: $pid)${NC}"
            else
                echo -e "  ${RED}✗ ${svc} not running (stale PID)${NC}"
            fi
        else
            echo -e "  ${YELLOW}○ ${svc} not started${NC}"
        fi
    done

    echo ""
    echo -e "${CYAN}Port checks:${NC}"
    for port_label in "${WEB_PORT}:Django" "${FRONTEND_PORT}:Frontend" "${EMULATOR_PORT}:Emulator"; do
        local port label
        port="${port_label%%:*}"
        label="${port_label##*:}"
        if lsof -i ":${port}" > /dev/null 2>&1; then
            echo -e "  ${GREEN}✓ :${port} ${label}${NC}"
        else
            echo -e "  ${YELLOW}○ :${port} ${label} — not listening${NC}"
        fi
    done
    echo ""
}

############
# Docker Compose

function docker_up() {
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}docker compose up                             ${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    cd "${SCRIPT_DIR}"
    docker compose up
}

function docker_down() {
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}docker compose down                           ${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    cd "${SCRIPT_DIR}"
    docker compose down
}

function docker_logs() {
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}docker compose logs -f                        ${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    cd "${SCRIPT_DIR}"
    docker compose logs -f
}

############
# Main

function main() {
    if [[ $# -gt 0 ]]; then
        case "$1" in
            stop)                 stop_services; exit 0 ;;
            status)               show_status; exit 0 ;;
            dev|development)      run_development; exit 0 ;;
            frontend)             run_frontend; exit 0 ;;
            emulator)             run_emulator; exit 0 ;;
            shell|console)        run_console; exit 0 ;;
            migrate|migrations)   run_migrations; exit 0 ;;
            test|tests)           run_tests; exit 0 ;;
            all)                  run_all; exit 0 ;;
            docker-up)            docker_up; exit 0 ;;
            docker-down)          docker_down; exit 0 ;;
            docker-logs)          docker_logs; exit 0 ;;
            help|--help|-h)
                show_banner
                echo "Usage: $0 [command]"
                echo ""
                echo "Commands:"
                echo "  dev, development    Start Django development server (:${WEB_PORT})"
                echo "  frontend            Start React frontend dev server (:${FRONTEND_PORT})"
                echo "  emulator            Start Redfish BMC emulator (:${EMULATOR_PORT})"
                echo "  shell, console      Django interactive shell"
                echo "  migrate             Run makemigrations + migrate"
                echo "  test, tests         Interactive pytest runner"
                echo "  all                 Start all services in background"
                echo "  stop                Stop all background services"
                echo "  status              Show service status"
                echo "  docker-up           docker compose up"
                echo "  docker-down         docker compose down"
                echo "  docker-logs         docker compose logs -f"
                echo "  help                Show this message"
                echo ""
                echo "Environment overrides:"
                echo "  WEB_PORT      Django port (default: 8000)"
                echo "  FRONTEND_PORT React port  (default: 5173)"
                echo "  EMULATOR_PORT Emulator port (default: 8888)"
                exit 0
                ;;
            *)
                echo -e "${RED}Unknown command: $1${NC}"
                echo "Run '$0 help' for usage."
                exit 1
                ;;
        esac
    fi

    # Interactive menu
    show_banner

    while true; do
        show_menu
        read -rp "Select: " choice
        echo ""

        case $choice in
            1)   run_development ;;
            2)   run_frontend ;;
            3)   run_emulator ;;
            4)   run_all ;;
            5)   stop_services ;;
            6)   show_status ;;
            7)   run_console ;;
            8)   run_migrations ;;
            9)   run_sdk_tests ;;
            10)  run_django_tests ;;
            11)  run_integration_tests ;;
            12)  run_all_tests ;;
            13)  run_tests ;;
            14)  docker_up ;;
            15)  docker_down ;;
            16)  docker_logs ;;
            d|D) toggle_debug; continue ;;
            q|Q) echo -e "${BRIGHT_GREEN}Goodbye!${NC}"; exit 0 ;;
            *)   echo -e "${BRIGHT_RED}Invalid choice.${NC}\n"; continue ;;
        esac

        echo ""
        echo -e "${BRIGHT_CYAN}Press Enter to continue...${NC}"
        read -r
        clear
        show_banner
    done
}

main "$@"
