#!/usr/bin/env bash
# update-ref-links.sh — rewrite Appendix B links in touchscreen.md to local paths
#
# After running download-refs.sh, this script finds all downloaded files and
# updates the corresponding links in docs/touchscreen.md so they resolve locally.
# Original online URLs are preserved as comments.
#
# Usage:
#   bash scripts/update-ref-links.sh            # update links in touchscreen.md
#   bash scripts/update-ref-links.sh --dry-run  # preview changes without writing
#   bash scripts/update-ref-links.sh --restore  # revert to online-only links
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REFS_DIR="$SCRIPT_DIR/../refs"
DOC="$REPO_ROOT/docs/touchscreen.md"
BACKUP="$DOC.bak"
DRY_RUN=0
RESTORE=0

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()    { echo -e "  ${GREEN}✓${NC} $*"; }
warn()  { echo -e "  ${YELLOW}!${NC} $*"; }

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run) DRY_RUN=1; shift ;;
        --restore) RESTORE=1; shift ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

[ -f "$DOC" ] || { echo "touchscreen.md not found at $DOC" >&2; exit 1; }

# ── Restore mode ───────────────────────────────────────────────────────────────
if [ "$RESTORE" -eq 1 ]; then
    if [ -f "$BACKUP" ]; then
        cp "$BACKUP" "$DOC"
        ok "Restored from $BACKUP"
    else
        warn "No backup found at $BACKUP — nothing to restore"
    fi
    exit 0
fi

# ── Build URL → local-path mapping ────────────────────────────────────────────
# Format: "online_url|local_relative_path|description"
# local_relative_path is relative to docs/ so links resolve from touchscreen.md

declare -A URL_TO_LOCAL

map_if_exists() {
    local url="$1" local_path="$2"
    # local_path is relative to REFS_DIR
    if [ -d "$REFS_DIR/$local_path" ] || [ -f "$REFS_DIR/$local_path" ]; then
        # Convert to a path relative to docs/
        URL_TO_LOCAL["$url"]="../C++/refs/$local_path"
    fi
}

# Kernel documentation
map_if_exists \
    "https://www.kernel.org/doc/html/latest/input/multi-touch-protocol.html" \
    "kernel/input/www.kernel.org/doc/html/latest/input/multi-touch-protocol.html"

map_if_exists \
    "https://www.kernel.org/doc/html/latest/input/event-codes.html" \
    "kernel/input/www.kernel.org/doc/html/latest/input/event-codes.html"

map_if_exists \
    "https://www.kernel.org/doc/html/latest/input/input.html" \
    "kernel/input/www.kernel.org/doc/html/latest/input/input.html"

map_if_exists \
    "https://www.kernel.org/doc/html/latest/gpu/drm-kms.html" \
    "kernel/drm-kms/www.kernel.org/doc/html/latest/gpu/drm-kms.html"

map_if_exists \
    "https://www.kernel.org/doc/html/latest/i2c/dev-interface.html" \
    "kernel/i2c/www.kernel.org/doc/html/latest/i2c/dev-interface.html"

map_if_exists \
    "https://github.com/dvdhrm/docs/tree/master/drm-howto" \
    "kernel/drm-howto-src"

# libevdev
map_if_exists \
    "https://www.freedesktop.org/software/libevdev/doc/latest/" \
    "libevdev/api"

map_if_exists \
    "https://gitlab.freedesktop.org/libevdev/libevdev" \
    "libevdev/src"

# libinput
map_if_exists \
    "https://wayland.freedesktop.org/libinput/doc/latest/" \
    "libinput/api"

map_if_exists \
    "https://wayland.freedesktop.org/libinput/doc/latest/api/group__touch.html" \
    "libinput/api"

map_if_exists \
    "https://wayland.freedesktop.org/libinput/doc/latest/api/group__gestures.html" \
    "libinput/api"

map_if_exists \
    "https://wayland.freedesktop.org/libinput/doc/latest/touchscreen-support.html" \
    "libinput/api"

map_if_exists \
    "https://wayland.freedesktop.org/libinput/doc/latest/palm-detection.html" \
    "libinput/api"

map_if_exists \
    "https://wayland.freedesktop.org/libinput/doc/latest/device-configuration-via-udev.html" \
    "libinput/api"

map_if_exists \
    "https://gitlab.freedesktop.org/libinput/libinput" \
    "libinput/src"

# libdrm + kmscube
map_if_exists \
    "https://gitlab.freedesktop.org/mesa/drm" \
    "libdrm/src"

map_if_exists \
    "https://gitlab.freedesktop.org/mesa/kmscube" \
    "libdrm/kmscube-src"

# Mesa / EGL / GLES
map_if_exists \
    "https://docs.mesa3d.org/egl.html" \
    "mesa/egl"

map_if_exists \
    "https://docs.mesa3d.org/gbm.html" \
    "mesa/gbm"

map_if_exists \
    "https://registry.khronos.org/EGL/specs/eglspec.1.5.pdf" \
    "mesa/specs/eglspec.1.5.pdf"

map_if_exists \
    "https://registry.khronos.org/EGL/sdk/docs/man/" \
    "mesa/egl-refpages"

map_if_exists \
    "https://registry.khronos.org/OpenGL/specs/es/3.2/es_spec_3.2.pdf" \
    "mesa/specs/es_spec_3.2.pdf"

map_if_exists \
    "https://registry.khronos.org/OpenGL-Refpages/es3/" \
    "mesa/gles3-refpages"

# ddcutil
map_if_exists \
    "https://www.ddcutil.com/" \
    "ddcutil/site"

map_if_exists \
    "https://www.ddcutil.com/api_main/" \
    "ddcutil/api"

map_if_exists \
    "https://www.ddcutil.com/vcp_feature_codes/" \
    "ddcutil/vcp"

map_if_exists \
    "https://www.ddcutil.com/i2c_permissions/" \
    "ddcutil/i2c"

map_if_exists \
    "https://github.com/rockowitz/ddcutil" \
    "ddcutil/src"

# SDL2
map_if_exists \
    "https://wiki.libsdl.org/SDL2/SDL_TouchFingerEvent" \
    "sdl2/wiki"

map_if_exists \
    "https://wiki.libsdl.org/SDL2/SDL_MultiGestureEvent" \
    "sdl2/wiki"

map_if_exists \
    "https://wiki.libsdl.org/SDL2/README/kmsdrm" \
    "sdl2/wiki"

map_if_exists \
    "https://github.com/libsdl-org/SDL" \
    "sdl2/src"

# CUDA
map_if_exists \
    "https://docs.nvidia.com/cuda/cuda-c-programming-guide/" \
    "cuda/programming-guide"

map_if_exists \
    "https://docs.nvidia.com/cuda/cuda-runtime-api/" \
    "cuda/runtime-api"

map_if_exists \
    "https://github.com/NVIDIA/cuda-samples" \
    "cuda/samples"

# Vulkan
map_if_exists \
    "https://registry.khronos.org/vulkan/specs/1.3-extensions/man/html/VK_KHR_external_memory_fd.html" \
    "vulkan/specs"

map_if_exists \
    "https://registry.khronos.org/vulkan/specs/1.3-extensions/man/html/VK_KHR_external_semaphore_fd.html" \
    "vulkan/specs"

map_if_exists \
    "https://registry.khronos.org/vulkan/specs/1.3-extensions/man/html/VK_KHR_timeline_semaphore.html" \
    "vulkan/specs"

# ViewSonic
map_if_exists \
    "https://www.viewsonic.com/global/products/lcd/TD2423D.php" \
    "viewsonic/product"

map_if_exists \
    "https://www.viewsonic.com/global/products/pdf/TD2423D_UG_ENG.pdf" \
    "viewsonic/manuals/TD2423D_UG_ENG.pdf"

map_if_exists \
    "https://linux-hardware.org/?id=usb:0543-9881" \
    "viewsonic/hw-db"

# ── Report mapping ─────────────────────────────────────────────────────────────
echo ""
echo -e "Found ${#URL_TO_LOCAL[@]} local replacements:"
for url in "${!URL_TO_LOCAL[@]}"; do
    echo "  $url"
    echo "    → ${URL_TO_LOCAL[$url]}"
done

if [ "${#URL_TO_LOCAL[@]}" -eq 0 ]; then
    warn "No local files found — run: bash scripts/download-refs.sh first"
    exit 0
fi

# ── Apply rewrites ─────────────────────────────────────────────────────────────
if [ "$DRY_RUN" -eq 1 ]; then
    echo ""
    warn "Dry-run mode — no files modified"
    exit 0
fi

# Backup
cp "$DOC" "$BACKUP"
ok "Backup saved to $(basename "$BACKUP")"

# Apply each URL replacement: add local link alongside the online link
# Pattern: [text](URL)  →  [text](local_path) ([online](URL))
TMPFILE=$(mktemp)
cp "$DOC" "$TMPFILE"

REPLACED=0
for url in "${!URL_TO_LOCAL[@]}"; do
    local="${URL_TO_LOCAL[$url]}"
    # Replace markdown links: ([^)]*)(URL) → ([^)]*)(local) ([online](URL))
    # Only replace if not already replaced (no "online" marker present)
    if grep -qF "$url" "$TMPFILE" && ! grep -qF "[online]($url)" "$TMPFILE"; then
        # Use perl for reliable in-place multi-line safe substitution
        perl -i -pe "s|\Q($url)\E|(${local}) ([online]($url))|g" "$TMPFILE"
        REPLACED=$((REPLACED+1))
    fi
done

mv "$TMPFILE" "$DOC"
ok "Updated $REPLACED link(s) in $(basename "$DOC")"
echo ""
echo "To restore original online-only links:"
echo "  bash scripts/update-ref-links.sh --restore"
echo ""
