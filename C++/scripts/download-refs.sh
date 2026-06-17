#!/usr/bin/env bash
# download-refs.sh — download all reference documentation for CommandDeck
#
# Fetches kernel docs, library API docs, specifications, and source repos
# into C++/refs/ so they are available offline on DGX nodes or air-gapped systems.
#
# Usage:
#   bash scripts/download-refs.sh            # download everything
#   bash scripts/download-refs.sh --section kernel   # one section only
#   bash scripts/download-refs.sh --list     # print all sections and exit
#   bash scripts/download-refs.sh --check    # verify what is already present
#   bash scripts/download-refs.sh --clean    # remove all downloaded refs
#
# Requirements:  wget  git
# Proxy note:    if behind a corporate proxy, set:
#   export HTTPS_PROXY=http://proxy.example.com:8080
#   export NO_PROXY=localhost,127.0.0.1
#
set -euo pipefail

REFS_DIR="$(cd "$(dirname "$0")/.." && pwd)/refs"
SECTION=""

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33d'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
YELLOW='\033[1;33m'  # fix the typo above
ok()    { echo -e "  ${GREEN}✓${NC} $*"; }
warn()  { echo -e "  ${YELLOW}!${NC} $*"; }
die()   { echo -e "  ${RED}✗${NC} $*" >&2; }
info()  { echo -e "  ${BLUE}→${NC} $*"; }
header(){ echo -e "\n${BOLD}${BLUE}── $* ──${NC}"; }

# wget exit code meanings — used in error messages
wget_exit_msg() {
    case $1 in
        1) echo "generic error (bad URL, missing argument, or unexpected condition)" ;;
        2) echo "parse error in command-line options" ;;
        3) echo "file I/O error — cannot write to destination directory" ;;
        4) echo "network failure — DNS resolution failed, connection refused, or timeout" ;;
        5) echo "SSL/TLS error — certificate verification failed" ;;
        6) echo "authentication failure — username/password rejected (HTTP 401)" ;;
        7) echo "protocol error — server sent unexpected response" ;;
        8) echo "server error — server returned 4xx or 5xx HTTP status" ;;
        *) echo "unknown error (exit code $1)" ;;
    esac
}

# ── Pre-flight: verify required tools are installed ────────────────────────────

WGET_OK=0
GIT_OK=0

check_tools() {
    local missing=0

    echo "Checking required tools..."

    # ── wget ──
    if command -v wget &>/dev/null; then
        local wver; wver=$(wget --version 2>/dev/null | head -1 | grep -o '[0-9]\+\.[0-9]\+[^ ]*' | head -1 || echo "?")
        ok "wget $wver"
        WGET_OK=1
    else
        die "wget not found"
        echo ""
        echo "    Install wget:"
        if command -v apt-get &>/dev/null; then
            echo "      sudo apt-get install wget"
        elif command -v dnf &>/dev/null; then
            echo "      sudo dnf install wget"
        elif command -v brew &>/dev/null; then
            echo "      brew install wget"
        else
            echo "      Download from https://www.gnu.org/software/wget/"
        fi
        missing=$((missing+1))
    fi

    # ── git ──
    if command -v git &>/dev/null; then
        local gver; gver=$(git --version 2>/dev/null | awk '{print $3}' || echo "?")
        ok "git $gver"
        GIT_OK=1
    else
        die "git not found"
        echo ""
        echo "    Install git:"
        if command -v apt-get &>/dev/null; then
            echo "      sudo apt-get install git"
        elif command -v dnf &>/dev/null; then
            echo "      sudo dnf install git"
        elif command -v brew &>/dev/null; then
            echo "      brew install git"
        else
            echo "      Download from https://git-scm.com/downloads"
        fi
        missing=$((missing+1))
    fi

    if [ "$missing" -gt 0 ]; then
        echo ""
        die "$missing required tool(s) missing — install them and re-run."
        exit 1
    fi
    echo ""
}

# ── Connectivity probe: one lightweight HEAD request before bulk downloading ───

NETWORK_OK=0

check_connectivity() {
    [ "$WGET_OK" -eq 0 ] && return  # no wget, skip

    echo "Probing network connectivity..."
    local probe_url="https://www.kernel.org/"
    local tmpout; tmpout=$(mktemp)

    # Use --spider (HEAD request) to check reachability without downloading
    if wget --spider --timeout=10 --tries=1 -o "$tmpout" "$probe_url" 2>&1; then
        ok "Reached $probe_url"
        NETWORK_OK=1
    else
        local exit_code=$?
        # Parse the wget output for a more specific message
        local detail=""
        if grep -qi "unable to resolve" "$tmpout" 2>/dev/null; then
            detail="DNS resolution failed — is the network interface up?"
        elif grep -qi "connection refused" "$tmpout" 2>/dev/null; then
            detail="connection refused — firewall or proxy blocking outbound HTTPS?"
        elif grep -qi "timed out\|timeout" "$tmpout" 2>/dev/null; then
            detail="connection timed out — slow network or proxy required?"
        elif grep -qi "407\|proxy auth" "$tmpout" 2>/dev/null; then
            detail="proxy requires authentication — set HTTPS_PROXY with credentials"
        elif grep -qi "403\|forbidden" "$tmpout" 2>/dev/null; then
            detail="HTTP 403 Forbidden — proxy or firewall blocking the request"
        else
            detail="$(wget_exit_msg $exit_code)"
        fi

        warn "Cannot reach $probe_url"
        info "Reason: $detail"
        info "wget output:"
        sed 's/^/    /' "$tmpout"
        echo ""
        info "If you are behind a corporate proxy, set:"
        info "  export HTTPS_PROXY=http://proxy.example.com:8080"
        info "  export NO_PROXY=localhost,127.0.0.1"
        info "Then re-run this script."
        echo ""
        warn "Proceeding anyway — individual failures will be reported per download."
    fi
    rm -f "$tmpout"
    echo ""
}

# ── Download helpers ───────────────────────────────────────────────────────────

wget_page() {
    [ "$WGET_OK" -eq 0 ] && { warn "$3 — skipped (wget not available)"; return; }

    local url="$1" dest="$2" desc="$3"

    # Skip if already downloaded
    if [ -d "$dest" ] && [ "$(find "$dest" -name '*.html' | wc -l)" -gt 0 ]; then
        ok "$desc (already downloaded)"
        return 0
    fi

    mkdir -p "$dest"
    echo "  Downloading $desc ..."

    local tmplog; tmplog=$(mktemp)
    local exit_code=0

    wget \
        --mirror \
        --convert-links \
        --adjust-extension \
        --page-requisites \
        --no-parent \
        --directory-prefix="$dest" \
        --timeout=30 \
        --tries=3 \
        --no-verbose \
        -o "$tmplog" \
        "$url" || exit_code=$?

    if [ "$exit_code" -eq 0 ]; then
        local count; count=$(find "$dest" -not -type d | wc -l)
        ok "$desc ($count files)"
    else
        # Parse wget's log for the most informative line
        local detail=""
        if grep -qi "unable to resolve\|no address" "$tmplog" 2>/dev/null; then
            detail="DNS failure — cannot resolve hostname"
        elif grep -qi "connection refused" "$tmplog" 2>/dev/null; then
            detail="connection refused"
        elif grep -qi "timed out\|timeout" "$tmplog" 2>/dev/null; then
            detail="connection timed out"
        elif grep -qi "ERROR 404" "$tmplog" 2>/dev/null; then
            detail="HTTP 404 Not Found — URL may have moved"
        elif grep -qi "ERROR 403" "$tmplog" 2>/dev/null; then
            detail="HTTP 403 Forbidden — proxy or auth required"
        elif grep -qi "ERROR 407" "$tmplog" 2>/dev/null; then
            detail="HTTP 407 Proxy Authentication Required"
        elif grep -qi "ERROR [45][0-9][0-9]" "$tmplog" 2>/dev/null; then
            detail=$(grep -o "ERROR [45][0-9][0-9][^']*" "$tmplog" | head -1)
        elif grep -qi "certificate\|SSL\|TLS" "$tmplog" 2>/dev/null; then
            detail="SSL/TLS error — try adding --no-check-certificate if using a self-signed proxy"
        else
            detail="$(wget_exit_msg $exit_code)"
        fi

        warn "$desc — FAILED (exit $exit_code: $detail)"
        info "wget log:"
        grep -v "^$" "$tmplog" | tail -5 | sed 's/^/    /'
        FAILED=$((FAILED+1))
        # Clean up empty directory
        [ -d "$dest" ] && rmdir --ignore-fail-on-non-empty "$dest" 2>/dev/null || true
    fi
    rm -f "$tmplog"
}

wget_single() {
    [ "$WGET_OK" -eq 0 ] && { warn "$4 — skipped (wget not available)"; return; }

    local url="$1" dest="$2" filename="$3" desc="$4"

    if [ -f "$dest/$filename" ]; then
        ok "$desc (already downloaded)"
        return 0
    fi

    mkdir -p "$dest"
    echo "  Downloading $desc ..."

    local tmplog; tmplog=$(mktemp)
    local exit_code=0

    wget \
        --timeout=30 \
        --tries=3 \
        --no-verbose \
        -o "$tmplog" \
        -O "$dest/$filename" \
        "$url" || exit_code=$?

    if [ "$exit_code" -eq 0 ] && [ -s "$dest/$filename" ]; then
        local size; size=$(du -sh "$dest/$filename" 2>/dev/null | cut -f1)
        ok "$desc ($size)"
    else
        local detail=""
        if grep -qi "unable to resolve\|no address" "$tmplog" 2>/dev/null; then
            detail="DNS failure"
        elif grep -qi "ERROR 404" "$tmplog" 2>/dev/null; then
            detail="HTTP 404 Not Found — file may have been moved or renamed"
        elif grep -qi "ERROR 403" "$tmplog" 2>/dev/null; then
            detail="HTTP 403 Forbidden"
        elif grep -qi "timed out\|timeout" "$tmplog" 2>/dev/null; then
            detail="connection timed out"
        elif grep -qi "certificate\|SSL" "$tmplog" 2>/dev/null; then
            detail="SSL/TLS error"
        else
            detail="$(wget_exit_msg $exit_code)"
        fi

        warn "$desc — FAILED (exit $exit_code: $detail)"
        info "wget log:"
        grep -v "^$" "$tmplog" | tail -5 | sed 's/^/    /'
        rm -f "$dest/$filename"
        FAILED=$((FAILED+1))
    fi
    rm -f "$tmplog"
}

git_clone() {
    [ "$GIT_OK" -eq 0 ] && { warn "$3 — skipped (git not available)"; return; }

    local url="$1" dest="$2" desc="$3" depth="${4:-1}"

    if [ -d "$dest/.git" ]; then
        ok "$desc (already cloned — pulling)"
        git -C "$dest" pull --quiet --ff-only 2>/dev/null \
            || warn "$desc — pull failed (offline or upstream changed)"
        return 0
    fi

    echo "  Cloning $desc ..."

    local tmplog; tmplog=$(mktemp)
    local exit_code=0

    git clone --depth "$depth" "$url" "$dest" >"$tmplog" 2>&1 || exit_code=$?

    if [ "$exit_code" -eq 0 ]; then
        local commits; commits=$(git -C "$dest" rev-list --count HEAD 2>/dev/null || echo "?")
        ok "$desc ($commits commit(s) fetched)"
    else
        local detail=""
        if grep -qi "could not resolve\|name or service not known" "$tmplog" 2>/dev/null; then
            detail="DNS failure — cannot resolve $(echo "$url" | grep -o '[^/]*\.[^/]*/' | head -1)"
        elif grep -qi "repository.*not found\|does not exist" "$tmplog" 2>/dev/null; then
            detail="repository not found — URL may have changed"
        elif grep -qi "authentication\|permission denied" "$tmplog" 2>/dev/null; then
            detail="authentication required — repo may be private"
        elif grep -qi "timed out\|timeout" "$tmplog" 2>/dev/null; then
            detail="connection timed out"
        elif grep -qi "proxy\|407" "$tmplog" 2>/dev/null; then
            detail="proxy error — set HTTPS_PROXY if behind a corporate proxy"
        else
            detail="git exit code $exit_code"
        fi

        warn "$desc — FAILED ($detail)"
        info "git output:"
        grep -v "^$" "$tmplog" | tail -5 | sed 's/^/    /'
        [ -d "$dest" ] && rm -rf "$dest"
        FAILED=$((FAILED+1))
    fi
    rm -f "$tmplog"
}

# ── Section definitions ────────────────────────────────────────────────────────

section_kernel() {
    header "Linux Kernel — Input & DRM/KMS documentation"
    local d="$REFS_DIR/kernel"

    wget_page \
        "https://www.kernel.org/doc/html/latest/input/multi-touch-protocol.html" \
        "$d/input" \
        "MT protocol spec (kernel.org)"

    wget_page \
        "https://www.kernel.org/doc/html/latest/input/event-codes.html" \
        "$d/input" \
        "Input event codes reference (kernel.org)"

    wget_page \
        "https://www.kernel.org/doc/html/latest/input/input.html" \
        "$d/input" \
        "Linux input subsystem overview (kernel.org)"

    wget_page \
        "https://www.kernel.org/doc/html/latest/gpu/drm-kms.html" \
        "$d/drm-kms" \
        "DRM/KMS kernel documentation (kernel.org)"

    wget_page \
        "https://www.kernel.org/doc/html/latest/i2c/dev-interface.html" \
        "$d/i2c" \
        "i2c-dev userspace interface (kernel.org)"

    git_clone \
        "https://github.com/dvdhrm/docs" \
        "$d/drm-howto-src" \
        "DRM howto source (dvdhrm/docs)"
}

section_libevdev() {
    header "libevdev — evdev C wrapper library"
    local d="$REFS_DIR/libevdev"

    wget_page \
        "https://www.freedesktop.org/software/libevdev/doc/latest/" \
        "$d/api" \
        "libevdev API reference (freedesktop.org)"

    git_clone \
        "https://gitlab.freedesktop.org/libevdev/libevdev.git" \
        "$d/src" \
        "libevdev source (gitlab.freedesktop.org)"

    git_clone \
        "https://gitlab.freedesktop.org/libevdev/evtest.git" \
        "$d/evtest-src" \
        "evtest source"
}

section_libinput() {
    header "libinput — input handling library"
    local d="$REFS_DIR/libinput"

    wget_page \
        "https://wayland.freedesktop.org/libinput/doc/latest/" \
        "$d/api" \
        "libinput documentation (freedesktop.org)"

    wget_page \
        "https://wayland.freedesktop.org/libinput/doc/latest/api/group__touch.html" \
        "$d/api" \
        "libinput touch event API"

    wget_page \
        "https://wayland.freedesktop.org/libinput/doc/latest/api/group__gestures.html" \
        "$d/api" \
        "libinput gesture API"

    wget_page \
        "https://wayland.freedesktop.org/libinput/doc/latest/touchscreen-support.html" \
        "$d/api" \
        "libinput touchscreen support guide"

    wget_page \
        "https://wayland.freedesktop.org/libinput/doc/latest/palm-detection.html" \
        "$d/api" \
        "libinput palm detection"

    wget_page \
        "https://wayland.freedesktop.org/libinput/doc/latest/device-configuration-via-udev.html" \
        "$d/api" \
        "libinput udev configuration"

    git_clone \
        "https://gitlab.freedesktop.org/libinput/libinput.git" \
        "$d/src" \
        "libinput source"
}

section_libdrm() {
    header "libdrm + GBM — DRM/KMS userspace library"
    local d="$REFS_DIR/libdrm"

    git_clone \
        "https://gitlab.freedesktop.org/mesa/drm.git" \
        "$d/src" \
        "libdrm source (mesa/drm)"

    git_clone \
        "https://gitlab.freedesktop.org/mesa/kmscube.git" \
        "$d/kmscube-src" \
        "kmscube (DRM/KMS/EGL example)"
}

section_mesa() {
    header "Mesa — EGL, GBM, OpenGL ES"
    local d="$REFS_DIR/mesa"

    wget_page \
        "https://docs.mesa3d.org/egl.html" \
        "$d/egl" \
        "Mesa EGL documentation"

    # GBM has no standalone HTML doc page — the authoritative reference is the
    # gbm.h header itself. Download it directly from the Mesa source tree.
    wget_single \
        "https://gitlab.freedesktop.org/mesa/mesa/-/raw/main/src/gbm/main/gbm.h" \
        "$d/gbm" \
        "gbm.h" \
        "GBM API header (Mesa source)"

    wget_single \
        "https://registry.khronos.org/EGL/specs/eglspec.1.5.pdf" \
        "$d/specs" \
        "eglspec.1.5.pdf" \
        "EGL 1.5 specification (Khronos)"

    wget_page \
        "https://registry.khronos.org/EGL/sdk/docs/man/" \
        "$d/egl-refpages" \
        "EGL reference pages (Khronos)"

    wget_single \
        "https://registry.khronos.org/OpenGL/specs/es/3.2/es_spec_3.2.pdf" \
        "$d/specs" \
        "es_spec_3.2.pdf" \
        "OpenGL ES 3.2 specification (Khronos)"

    wget_page \
        "https://registry.khronos.org/OpenGL-Refpages/es3/" \
        "$d/gles3-refpages" \
        "OpenGL ES 3.0 reference pages (Khronos)"
}

section_ddcutil() {
    header "ddcutil — DDC/CI monitor control"
    local d="$REFS_DIR/ddcutil"

    wget_page \
        "https://www.ddcutil.com/" \
        "$d/site" \
        "ddcutil website"

    wget_page \
        "https://www.ddcutil.com/api_main/" \
        "$d/api" \
        "ddcutil C API reference"

    # VCP feature code page was removed from ddcutil.com.
    # The canonical reference is the ddcutil command itself — run on a live system:
    #   ddcutil vcpinfo --verbose > refs/ddcutil/vcp/vcpinfo.txt
    # We generate the file here if ddcutil is installed, otherwise skip silently.
    if command -v ddcutil &>/dev/null; then
        mkdir -p "$d/vcp"
        if ddcutil vcpinfo --verbose > "$d/vcp/vcpinfo.txt" 2>/dev/null; then
            ok "VCP feature codes (generated via ddcutil vcpinfo)"
        else
            warn "VCP feature codes — ddcutil vcpinfo failed (no monitor connected?)"
        fi
    else
        warn "VCP feature codes — ddcutil not installed; skipping local generation"
        echo ""
        echo "    Install ddcutil, then re-run this script:"
        if command -v brew &>/dev/null; then
            echo "      brew install ddcutil          # macOS (Homebrew)"
        fi
        if command -v apt-get &>/dev/null; then
            echo "      sudo apt-get install ddcutil  # Ubuntu/Debian"
        fi
        if command -v dnf &>/dev/null; then
            echo "      sudo dnf install ddcutil      # Fedora/RHEL"
        fi
        echo "    Then generate manually:"
        echo "      ddcutil vcpinfo --verbose > refs/ddcutil/vcp/vcpinfo.txt"
        echo ""
    fi

    wget_page \
        "https://www.ddcutil.com/i2c_permissions/" \
        "$d/i2c" \
        "ddcutil i2c permissions guide"

    git_clone \
        "https://github.com/rockowitz/ddcutil.git" \
        "$d/src" \
        "ddcutil source (GitHub)"
}

section_sdl2() {
    header "SDL2 — Simple DirectMedia Layer"
    local d="$REFS_DIR/sdl2"

    wget_page \
        "https://wiki.libsdl.org/SDL2/SDL_TouchFingerEvent" \
        "$d/wiki" \
        "SDL2 TouchFingerEvent"

    wget_page \
        "https://wiki.libsdl.org/SDL2/SDL_MultiGestureEvent" \
        "$d/wiki" \
        "SDL2 MultiGestureEvent"

    wget_page \
        "https://wiki.libsdl.org/SDL2/README/kmsdrm" \
        "$d/wiki" \
        "SDL2 KMS/DRM backend README"

    git_clone \
        "https://github.com/libsdl-org/SDL.git" \
        "$d/src" \
        "SDL2 source (libsdl-org/SDL)" \
        1
}

section_cuda() {
    header "CUDA — NVIDIA GPU computing"
    local d="$REFS_DIR/cuda"

    wget_page \
        "https://docs.nvidia.com/cuda/cuda-c-programming-guide/" \
        "$d/programming-guide" \
        "CUDA C++ Programming Guide (NVIDIA)"

    wget_page \
        "https://docs.nvidia.com/cuda/cuda-runtime-api/" \
        "$d/runtime-api" \
        "CUDA Runtime API reference (NVIDIA)"

    git_clone \
        "https://github.com/NVIDIA/cuda-samples.git" \
        "$d/samples" \
        "NVIDIA CUDA samples" \
        1

    ok "GL interop sample: refs/cuda/samples/Samples/2_Concepts_and_Techniques/simpleGL/"
    ok "Vulkan/CUDA sample: refs/cuda/samples/Samples/5_Domain_Specific/vulkanCUDA/"
}

section_vulkan() {
    header "Vulkan — external memory / semaphore extensions"
    local d="$REFS_DIR/vulkan"

    wget_page \
        "https://registry.khronos.org/vulkan/specs/1.3-extensions/man/html/VK_KHR_external_memory_fd.html" \
        "$d/specs" \
        "VK_KHR_external_memory_fd spec"

    wget_page \
        "https://registry.khronos.org/vulkan/specs/1.3-extensions/man/html/VK_KHR_external_semaphore_fd.html" \
        "$d/specs" \
        "VK_KHR_external_semaphore_fd spec"

    wget_page \
        "https://registry.khronos.org/vulkan/specs/1.3-extensions/man/html/VK_KHR_timeline_semaphore.html" \
        "$d/specs" \
        "VK_KHR_timeline_semaphore spec"

    wget_page \
        "https://vulkan.lunarg.com/sdk/home" \
        "$d/sdk" \
        "Vulkan SDK download page (LunarG)"
}

section_viewsonic() {
    header "ViewSonic TD2423D — display documentation"
    local d="$REFS_DIR/viewsonic"

    # ViewSonic restructured their site — the old /global/products/lcd/TD2423D.php
    # URL 404s. The product page is now at /us/td2423d/ or region-specific paths.
    # Search manually: https://www.viewsonic.com/us/td2423d.html
    warn "ViewSonic product page — URL changed; open manually in a browser"
    info "Search: https://www.viewsonic.com/us/td2423d.html"
    info "Or:     https://www.viewsonic.com (search TD2423D)"
    mkdir -p "$d/product"
    cat > "$d/product/README.txt" <<'EOF'
ViewSonic TD2423D product page URL has changed.
Find the current page by searching for "TD2423D" at https://www.viewsonic.com
or by trying regional URLs such as:
  https://www.viewsonic.com/us/td2423d.html

Once found, download the page manually with:
  wget --convert-links --page-requisites -P refs/viewsonic/product <URL>
EOF

    # PDF manual — URL changed along with the product page.
    # Try the US direct download path; fall back to a note if it 404s.
    local pdf_url="https://www.viewsonic.com/dam/pdf/TD2423D_UG_ENG.pdf"
    local pdf_alt="https://www.viewsonic.com/dam/pdf/user-guide/TD2423D_UG_ENG.pdf"
    mkdir -p "$d/manuals"
    echo "  Trying TD2423D User Guide PDF..."

    local tmplog; tmplog=$(mktemp)
    local exit_code=0
    wget --timeout=30 --tries=2 --no-verbose \
        -o "$tmplog" -O "$d/manuals/TD2423D_UG_ENG.pdf" \
        "$pdf_url" 2>/dev/null || exit_code=$?

    if [ "$exit_code" -eq 0 ] && [ -s "$d/manuals/TD2423D_UG_ENG.pdf" ]; then
        local size; size=$(du -sh "$d/manuals/TD2423D_UG_ENG.pdf" 2>/dev/null | cut -f1)
        ok "TD2423D User Guide PDF ($size)"
    else
        rm -f "$d/manuals/TD2423D_UG_ENG.pdf"
        # Try alternate path
        exit_code=0
        wget --timeout=30 --tries=2 --no-verbose \
            -o "$tmplog" -O "$d/manuals/TD2423D_UG_ENG.pdf" \
            "$pdf_alt" 2>/dev/null || exit_code=$?

        if [ "$exit_code" -eq 0 ] && [ -s "$d/manuals/TD2423D_UG_ENG.pdf" ]; then
            local size; size=$(du -sh "$d/manuals/TD2423D_UG_ENG.pdf" 2>/dev/null | cut -f1)
            ok "TD2423D User Guide PDF ($size, alternate path)"
        else
            rm -f "$d/manuals/TD2423D_UG_ENG.pdf"
            warn "TD2423D User Guide PDF — both known URLs returned errors"
            info "Find the current PDF link on the product page and download manually:"
            info "  wget -O refs/viewsonic/manuals/TD2423D_UG_ENG.pdf <PDF_URL>"
            cat > "$d/manuals/README.txt" <<'EOF'
TD2423D User Guide PDF could not be downloaded automatically.
ViewSonic's PDF URLs change when the site is updated.

To download manually:
  1. Go to https://www.viewsonic.com/us/td2423d.html (or your region)
  2. Find "Downloads" or "Support" tab
  3. Download the User Guide PDF
  4. Save it here as: refs/viewsonic/manuals/TD2423D_UG_ENG.pdf
EOF
        fi
    fi
    rm -f "$tmplog"

    # linux-hardware.org returns 403 to wget (deliberate bot blocking).
    # The page works fine in a browser — note the URL for manual access.
    warn "linux-hardware.org — blocks automated downloads (403); browser-only"
    info "View manually: https://linux-hardware.org/?id=usb:0543-9881"
    mkdir -p "$d/hw-db"
    cat > "$d/hw-db/README.txt" <<'EOF'
linux-hardware.org blocks wget with HTTP 403 (deliberate anti-bot policy).
The page is accessible in a browser at:
  https://linux-hardware.org/?id=usb:0543-9881

Key information from that page (VID:PID 0543:9881, ViewSonic touch controller):
  - USB Vendor ID:  0x0543  (ViewSonic Corporation)
  - USB Product ID: 0x9881  (TD2423D touchscreen controller)
  - Linux driver:   hid-multitouch (in-tree, no download needed)
  - Kernel module:  usbhid -> hid-multitouch
  - Protocol:       HID Multi-Touch (Type B, 10 points)
EOF
    ok "linux-hardware.org — key device info written to refs/viewsonic/hw-db/README.txt"
}

# ── CLI ────────────────────────────────────────────────────────────────────────

ALL_SECTIONS=(kernel libevdev libinput libdrm mesa ddcutil sdl2 cuda vulkan viewsonic)

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Options:
  --section NAME   Download only this section
  --list           Print all section names and exit
  --check          Show download status of each section
  --clean          Remove all downloaded refs
  -h, --help       Show this help

Sections: ${ALL_SECTIONS[*]}

Environment:
  HTTPS_PROXY      Corporate proxy URL (e.g. http://proxy.example.com:8080)
  NO_PROXY         Comma-separated hosts to bypass proxy

Examples:
  bash scripts/download-refs.sh
  bash scripts/download-refs.sh --section libinput
  HTTPS_PROXY=http://proxy:8080 bash scripts/download-refs.sh
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --section) SECTION="$2"; shift 2 ;;
        --list)
            echo "Sections: ${ALL_SECTIONS[*]}"
            exit 0 ;;
        --check)
            echo ""
            echo "Downloaded sections:"
            for s in "${ALL_SECTIONS[@]}"; do
                d="$REFS_DIR/$s"
                count=$(find "$d" -not -name '*.gitkeep' -not -type d 2>/dev/null | wc -l)
                if [ "$count" -gt 0 ]; then
                    echo -e "  ${GREEN}✓${NC} $s ($count files)"
                else
                    echo -e "  ${YELLOW}○${NC} $s (empty — run: $0 --section $s)"
                fi
            done
            echo ""
            exit 0 ;;
        --clean)
            echo "Removing downloaded refs..."
            find "$REFS_DIR" -mindepth 2 -not -name '.gitkeep' -delete 2>/dev/null || true
            ok "Cleaned (directory structure preserved)"
            exit 0 ;;
        -h|--help) usage ;;
        *) echo "Unknown option: $1" >&2; usage ;;
    esac
done

# ── Main ───────────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}CommandDeck — Reference Documentation Downloader${NC}"
echo "Output: $REFS_DIR"
echo ""

check_tools
check_connectivity

FAILED=0

run_section() {
    local name=$1
    if declare -f "section_$name" &>/dev/null; then
        "section_$name"
    else
        die "Unknown section: $name"
        FAILED=$((FAILED+1))
    fi
}

if [ -n "$SECTION" ]; then
    run_section "$SECTION"
else
    for s in "${ALL_SECTIONS[@]}"; do
        run_section "$s"
    done
fi

# ── Summary ────────────────────────────────────────────────────────────────────
echo ""
echo "────────────────────────────────────────────────────────"
total=$(find "$REFS_DIR" -not -name '*.gitkeep' -not -type d 2>/dev/null | wc -l)

if [ "$FAILED" -eq 0 ]; then
    ok "All downloads complete — $total files in refs/"
else
    warn "$FAILED download(s) failed — $total files retrieved"
    echo ""
    echo "  Re-run failed sections individually for more detail:"
    echo "    bash scripts/download-refs.sh --section <name>"
    echo ""
    echo "  If all sections fail, check:"
    echo "    1. Network connectivity: ping kernel.org"
    echo "    2. Proxy settings:       echo \$HTTPS_PROXY"
    echo "    3. DNS resolution:       nslookup kernel.org"
fi

echo ""
echo "  Rewrite touchscreen.md links to local paths:"
echo "    bash scripts/update-ref-links.sh"
echo ""
