#!/usr/bin/env bash
# install-cuda.sh — guided CUDA Toolkit installer for Ubuntu/Debian (DGX target)
# Downloads and installs the CUDA Toolkit and NVIDIA driver from the official repo.
# Tested on Ubuntu 22.04 (DGX BaseOS).
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
die()  { echo -e "${RED}✗ $*${NC}" >&2; exit 1; }
ok()   { echo -e "${GREEN}✓ $*${NC}"; }
warn() { echo -e "${YELLOW}! $*${NC}"; }

# ── Pre-checks ────────────────────────────────────────────────────────────────
command -v apt-get &>/dev/null || die "This script requires apt-get (Ubuntu/Debian)."
[ "$(id -u)" -eq 0 ] || die "Run as root: sudo bash scripts/install-cuda.sh"

# ── Detect Ubuntu version ──────────────────────────────────────────────────────
UBUNTU_VER=$(lsb_release -rs 2>/dev/null || echo "22.04")
UBUNTU_CODENAME=$(lsb_release -cs 2>/dev/null || echo "jammy")
ARCH=$(uname -m)
echo ""
echo "Detected: Ubuntu $UBUNTU_VER ($UBUNTU_CODENAME) on $ARCH"

# Map to CUDA pin file
case "$UBUNTU_VER" in
    22.04) CUDA_DISTRO="ubuntu2204" ;;
    20.04) CUDA_DISTRO="ubuntu2004" ;;
    *)     warn "Untested Ubuntu version $UBUNTU_VER — trying ubuntu2204 pinning"; CUDA_DISTRO="ubuntu2204" ;;
esac

case "$ARCH" in
    x86_64)  CUDA_ARCH="x86_64" ;;
    aarch64) CUDA_ARCH="sbsa"   ;;
    *)        die "Unsupported architecture: $ARCH" ;;
esac

CUDA_VERSION="${CUDA_VERSION:-12.5}"    # override with: CUDA_VERSION=12.3 sudo bash ...
DRIVER_VERSION="${DRIVER_VERSION:-555}" # override with: DRIVER_VERSION=550 sudo bash ...

echo "CUDA Toolkit version : $CUDA_VERSION"
echo "NVIDIA driver version: $DRIVER_VERSION"
echo ""

# ── Already installed? ─────────────────────────────────────────────────────────
if command -v nvcc &>/dev/null; then
    CURRENT=$(nvcc --version | grep release | awk '{print $6}' | tr -d ',')
    warn "nvcc $CURRENT already installed. Continuing will upgrade/reinstall."
    read -r -p "Continue? [y/N] " reply
    [[ "${reply,,}" == "y" ]] || exit 0
fi

# ── Add CUDA repo ─────────────────────────────────────────────────────────────
echo "Adding NVIDIA package repository..."
KEYRING_URL="https://developer.download.nvidia.com/compute/cuda/repos/${CUDA_DISTRO}/${CUDA_ARCH}/cuda-keyring_1.1-1_all.deb"
KEYRING_DEB="/tmp/cuda-keyring.deb"

wget -q -O "$KEYRING_DEB" "$KEYRING_URL" || die "Failed to download CUDA keyring from $KEYRING_URL"
dpkg -i "$KEYRING_DEB"
rm -f "$KEYRING_DEB"
apt-get update -qq
ok "NVIDIA repository added"

# ── Install CUDA Toolkit ──────────────────────────────────────────────────────
echo ""
echo "Installing CUDA Toolkit $CUDA_VERSION and NVIDIA driver $DRIVER_VERSION..."
CUDA_PKG="cuda-toolkit-$(echo "$CUDA_VERSION" | tr '.' '-')"
DRIVER_PKG="nvidia-driver-$DRIVER_VERSION"

apt-get install -y "$CUDA_PKG" "$DRIVER_PKG"
ok "CUDA Toolkit installed"

# ── Environment variables ─────────────────────────────────────────────────────
CUDA_PATH_FILE="/etc/profile.d/cuda.sh"
if [ ! -f "$CUDA_PATH_FILE" ]; then
    cat > "$CUDA_PATH_FILE" <<'EOF'
export CUDA_HOME=/usr/local/cuda
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
EOF
    ok "CUDA PATH written to $CUDA_PATH_FILE"
else
    ok "$CUDA_PATH_FILE already exists"
fi

# ── Verify ─────────────────────────────────────────────────────────────────────
source "$CUDA_PATH_FILE" 2>/dev/null || true

echo ""
if command -v nvcc &>/dev/null; then
    ok "Installation complete: $(nvcc --version | grep release)"
    echo ""
    echo "NOTE: A reboot is required to load the new NVIDIA driver."
    echo "After reboot, verify with: nvidia-smi && nvcc --version"
else
    warn "nvcc not found in PATH yet — source /etc/profile.d/cuda.sh or reboot."
fi
echo ""
