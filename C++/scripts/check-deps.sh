#!/usr/bin/env bash
# check-deps.sh — verify all CommandDeck build dependencies are present
# Prints a status table and exits non-zero if any required dep is missing.
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
PASS=0; WARN=0; FAIL=0

row() {
    local status=$1 name=$2 detail=$3
    case $status in
        ok)   echo -e "  ${GREEN}✓${NC}  $(printf '%-30s' "$name") $detail"; ((PASS++)) ;;
        warn) echo -e "  ${YELLOW}!${NC}  $(printf '%-30s' "$name") $detail"; ((WARN++)) ;;
        fail) echo -e "  ${RED}✗${NC}  $(printf '%-30s' "$name") $detail"; ((FAIL++)) ;;
    esac
}

check_pkg() {
    local name=$1 pkg=$2
    if pkg-config --exists "$pkg" 2>/dev/null; then
        local ver; ver=$(pkg-config --modversion "$pkg" 2>/dev/null || echo "?")
        row ok "$name" "($pkg $ver)"
    else
        row fail "$name" "(pkg-config: $pkg NOT FOUND)"
    fi
}

check_cmd() {
    local name=$1 cmd=$2
    if command -v "$cmd" &>/dev/null; then
        local ver; ver=$("$cmd" --version 2>/dev/null | head -1 || echo "?")
        row ok "$name" "($ver)"
    else
        row fail "$name" "($cmd not in PATH)"
    fi
}

check_cmd_optional() {
    local name=$1 cmd=$2
    if command -v "$cmd" &>/dev/null; then
        local ver; ver=$("$cmd" --version 2>/dev/null | head -1 || echo "?")
        row ok "$name" "(optional — $ver)"
    else
        row warn "$name" "(optional — $cmd not found)"
    fi
}

check_pkg_optional() {
    local name=$1 pkg=$2
    if pkg-config --exists "$pkg" 2>/dev/null; then
        local ver; ver=$(pkg-config --modversion "$pkg" 2>/dev/null || echo "?")
        row ok "$name" "(optional — $pkg $ver)"
    else
        row warn "$name" "(optional — $pkg not found)"
    fi
}

# ── Header ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}CommandDeck — Dependency Check${NC}"
echo "────────────────────────────────────────────────────────"

# ── Build tools ──────────────────────────────────────────────────────────────
echo ""
echo "Build tools:"
check_cmd  "CMake >= 3.20"     cmake
check_cmd  "C++ compiler"      g++
check_cmd  "pkg-config"        pkg-config
check_cmd  "make"              make

# CMake version gate
if command -v cmake &>/dev/null; then
    CMAKE_VER=$(cmake --version | head -1 | awk '{print $3}')
    REQUIRED="3.20"
    if [ "$(printf '%s\n' "$REQUIRED" "$CMAKE_VER" | sort -V | head -1)" != "$REQUIRED" ]; then
        row fail "CMake version" "need >= 3.20, found $CMAKE_VER"
    fi
fi

# ── Required libraries ────────────────────────────────────────────────────────
echo ""
echo "Required libraries:"
check_pkg "libevdev"    libevdev
check_pkg "libinput"   libinput
check_pkg "libudev"    libudev
check_pkg "libdrm"     libdrm
check_pkg "gbm"        gbm
check_pkg "egl"        egl
check_pkg "glesv2"     glesv2

# ── Optional libraries ────────────────────────────────────────────────────────
echo ""
echo "Optional libraries:"
check_pkg_optional "ddcutil (DDC/CI)"    ddcutil
check_pkg_optional "SDL2 (alt backend)" sdl2
check_pkg_optional "eigen3 (calibrate)" eigen3

# ── CUDA ─────────────────────────────────────────────────────────────────────
echo ""
echo "CUDA (optional — needed for ENABLE_CUDA=ON):"
if command -v nvcc &>/dev/null; then
    NVCC_VER=$(nvcc --version | grep release | awk '{print $6}' | tr -d ',')
    row ok "CUDA compiler (nvcc)" "($NVCC_VER)"
else
    row warn "CUDA compiler (nvcc)" "(not found — install CUDA Toolkit)"
fi
if command -v nvidia-smi &>/dev/null; then
    GPU=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo "?")
    row ok "NVIDIA GPU" "($GPU)"
else
    row warn "nvidia-smi" "(not found — no NVIDIA GPU?)"
fi

# ── Kernel / device ───────────────────────────────────────────────────────────
echo ""
echo "Kernel / device:"
if ls /dev/input/event* &>/dev/null; then
    COUNT=$(ls /dev/input/event* 2>/dev/null | wc -l)
    row ok "/dev/input/event*" "($COUNT event nodes found)"
else
    row warn "/dev/input/event*" "(no event nodes — is any input device connected?)"
fi

if ls /dev/dri/card* &>/dev/null; then
    COUNT=$(ls /dev/dri/card* 2>/dev/null | wc -l)
    row ok "/dev/dri/card*" "($COUNT DRM device(s) found)"
else
    row fail "/dev/dri/card*" "(no DRM devices found)"
fi

if lsmod 2>/dev/null | grep -q i2c_dev; then
    row ok "i2c-dev kernel module" "(loaded)"
else
    row warn "i2c-dev kernel module" "(not loaded — run: sudo modprobe i2c-dev)"
fi

# Groups check
if id -nG "$USER" 2>/dev/null | grep -qw input; then
    row ok "User in 'input' group" ""
else
    row warn "User in 'input' group" "(run: sudo usermod -aG input $USER)"
fi
if id -nG "$USER" 2>/dev/null | grep -qw video; then
    row ok "User in 'video' group" ""
else
    row warn "User in 'video' group" "(run: sudo usermod -aG video $USER)"
fi

# ── Developer tools ───────────────────────────────────────────────────────────
echo ""
echo "Developer tools (optional):"
check_cmd_optional "clang-format"  clang-format
check_cmd_optional "clang-tidy"    clang-tidy
check_cmd_optional "gdb"           gdb
check_cmd_optional "valgrind"      valgrind
check_cmd_optional "strace"        strace
check_cmd_optional "evtest"        evtest
check_cmd_optional "ddcutil (CLI)" ddcutil

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "────────────────────────────────────────────────────────"
echo -e "  ${GREEN}✓ Passed${NC}: $PASS   ${YELLOW}! Warnings${NC}: $WARN   ${RED}✗ Failed${NC}: $FAIL"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo -e "${RED}Required dependencies are missing. Run: bash scripts/setup-dev.sh${NC}"
    exit 1
elif [ "$WARN" -gt 0 ]; then
    echo -e "${YELLOW}Some optional features unavailable. Run: bash scripts/setup-dev.sh to install all.${NC}"
    exit 0
else
    echo -e "${GREEN}All dependencies satisfied. Run: make${NC}"
    exit 0
fi
