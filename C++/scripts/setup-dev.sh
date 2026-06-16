#!/usr/bin/env bash
# setup-dev.sh — install all system dependencies for CommandDeck
# Works on Ubuntu/Debian and Fedora/RHEL.
# Run once after cloning; requires sudo.
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}!${NC} $*"; }
die()  { echo -e "${RED}✗${NC} $*" >&2; exit 1; }

# ── Detect distro ───────────────────────────────────────────────────────────
if command -v apt-get &>/dev/null; then
    PKG_MGR="apt"
elif command -v dnf &>/dev/null; then
    PKG_MGR="dnf"
else
    die "Unsupported package manager — only apt and dnf are supported."
fi
echo "Detected package manager: $PKG_MGR"

# ── Package lists ───────────────────────────────────────────────────────────
APT_PKGS=(
    # Build toolchain
    build-essential cmake pkg-config git
    # Input stack
    libevdev-dev libinput-dev libudev-dev
    # Display / graphics
    libdrm-dev libgbm-dev libegl-dev libgles2-mesa-dev
    # DDC/CI monitor control
    ddcutil libddcutil-dev
    # Optional SDL2 backend
    libsdl2-dev
    # Optional numerical library (calibration solver)
    libeigen3-dev
    # Kernel headers for evdev ioctl
    linux-headers-generic
    # I2C tools (DDC/CI debugging)
    i2c-tools
    # Developer tools
    clang clang-format clang-tidy gdb valgrind strace
    evtest evemu-tools libinput-tools libdrm-tests mesa-utils
)

DNF_PKGS=(
    # Build toolchain
    gcc-c++ cmake pkgconf-pkg-config git
    # Input stack
    libevdev-devel libinput-devel systemd-devel
    # Display / graphics
    libdrm-devel mesa-libgbm-devel mesa-libEGL-devel mesa-libGLES-devel
    # DDC/CI
    ddcutil ddcutil-devel
    # Optional SDL2
    SDL2-devel
    # Optional Eigen
    eigen3-devel
    # Kernel headers
    kernel-headers
    # I2C tools
    i2c-tools
    # Developer tools
    clang clang-tools-extra gdb valgrind strace
)

# ── Install ─────────────────────────────────────────────────────────────────
echo ""
echo "Installing CommandDeck system dependencies..."
echo ""

if [ "$PKG_MGR" = "apt" ]; then
    sudo apt-get update -qq
    sudo apt-get install -y "${APT_PKGS[@]}"
else
    sudo dnf install -y "${DNF_PKGS[@]}"
fi

# ── Load i2c-dev for DDC/CI ──────────────────────────────────────────────────
echo ""
echo "Enabling i2c-dev kernel module..."
sudo modprobe i2c-dev
if ! grep -q "i2c-dev" /etc/modules-load.d/i2c-dev.conf 2>/dev/null; then
    echo "i2c-dev" | sudo tee /etc/modules-load.d/i2c-dev.conf > /dev/null
    ok "i2c-dev configured to load at boot"
else
    ok "i2c-dev already configured"
fi

# ── Add user to required groups ───────────────────────────────────────────────
echo ""
echo "Adding $USER to 'input' and 'video' groups..."
sudo usermod -aG input "$USER"
sudo usermod -aG video "$USER"
ok "Added to groups — log out and back in for this to take effect"

# ── Verify cmake version ─────────────────────────────────────────────────────
CMAKE_VERSION=$(cmake --version 2>/dev/null | head -1 | awk '{print $3}')
REQUIRED="3.20"
if [ "$(printf '%s\n' "$REQUIRED" "$CMAKE_VERSION" | sort -V | head -1)" = "$REQUIRED" ]; then
    ok "CMake $CMAKE_VERSION (>= $REQUIRED required)"
else
    warn "CMake $CMAKE_VERSION found but >= $REQUIRED required."
    warn "Consider installing from https://cmake.org/download/"
fi

# ── CUDA check ────────────────────────────────────────────────────────────────
echo ""
if command -v nvcc &>/dev/null; then
    CUDA_VER=$(nvcc --version | grep "release" | awk '{print $6}' | tr -d ',')
    ok "CUDA compiler found: nvcc $CUDA_VER"
else
    warn "CUDA compiler (nvcc) not found."
    warn "CUDA is optional — needed only for GPU overlay (ENABLE_CUDA=ON)."
    warn "Install from: https://developer.nvidia.com/cuda-downloads"
fi

echo ""
ok "All done! You can now run:"
echo "   cd C++ && make check-deps && make"
echo ""
echo "If you just added yourself to 'input'/'video' groups, log out and back in first."
echo ""
