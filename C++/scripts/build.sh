#!/usr/bin/env bash
# build.sh — configure and build CommandDeck
# Usage: bash scripts/build.sh [options]
#   -t, --type    Debug|Release|RelWithDebInfo (default: Release)
#   -j, --jobs    parallel jobs (default: nproc)
#   -c, --cuda    enable CUDA support
#   -s, --sdl2    enable SDL2 backend
#   -d, --ddc     enable DDC/CI support
#   -a, --asan    enable AddressSanitizer (forces Debug)
#   -v, --verbose cmake --verbose output
#   -C, --clean   remove build dir before configuring
#   --dir         build directory (default: build)
set -euo pipefail

BUILD_TYPE="Release"
BUILD_DIR="build"
JOBS=$(nproc)
OPT_CUDA=OFF
OPT_SDL2=OFF
OPT_DDC=OFF
OPT_ASAN=OFF
VERBOSE=""
CLEAN=0

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--type)     BUILD_TYPE="$2"; shift 2 ;;
        -j|--jobs)     JOBS="$2";       shift 2 ;;
        --dir)         BUILD_DIR="$2";  shift 2 ;;
        -c|--cuda)     OPT_CUDA=ON;     shift ;;
        -s|--sdl2)     OPT_SDL2=ON;     shift ;;
        -d|--ddc)      OPT_DDC=ON;      shift ;;
        -a|--asan)     OPT_ASAN=ON; BUILD_TYPE="Debug"; shift ;;
        -v|--verbose)  VERBOSE="--verbose"; shift ;;
        -C|--clean)    CLEAN=1;         shift ;;
        -h|--help)
            grep "^#" "$0" | head -15 | sed 's/^# //'
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# ── Clean ─────────────────────────────────────────────────────────────────────
if [ "$CLEAN" -eq 1 ] && [ -d "$BUILD_DIR" ]; then
    echo "Removing $BUILD_DIR ..."
    rm -rf "$BUILD_DIR"
fi

# ── Configure ─────────────────────────────────────────────────────────────────
echo ""
echo "Configuring CommandDeck:"
echo "  Build type  : $BUILD_TYPE"
echo "  Build dir   : $BUILD_DIR"
echo "  Jobs        : $JOBS"
echo "  CUDA        : $OPT_CUDA"
echo "  SDL2        : $OPT_SDL2"
echo "  DDC/CI      : $OPT_DDC"
echo "  ASan        : $OPT_ASAN"
echo ""

cmake -B "$BUILD_DIR" \
    -DCMAKE_BUILD_TYPE="$BUILD_TYPE" \
    -DENABLE_CUDA="$OPT_CUDA" \
    -DENABLE_SDL2="$OPT_SDL2" \
    -DENABLE_DDCUTIL="$OPT_DDC" \
    -DENABLE_ASAN="$OPT_ASAN"

# ── Build ─────────────────────────────────────────────────────────────────────
echo ""
cmake --build "$BUILD_DIR" -j"$JOBS" $VERBOSE

echo ""
echo "✓ Build complete: $BUILD_DIR/command_deck"
echo ""
echo "Run with: sudo $BUILD_DIR/command_deck"
echo "      or: make run"
echo ""
