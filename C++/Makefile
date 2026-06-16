# CommandDeck — convenience wrapper around CMake
# Usage:
#   make              → release build
#   make debug        → debug build
#   make cuda         → release build with CUDA
#   make sdl2         → release build with SDL2 backend
#   make full         → all optional features enabled
#   make clean        → remove build directories
#   make run          → build release then run
#   make check-deps   → verify all system dependencies
#   make format       → clang-format all source files
#   make tidy         → clang-tidy static analysis
#   make asan         → debug build with AddressSanitizer

BUILD_DIR   ?= build
DEBUG_DIR   ?= build-debug
CUDA_DIR    ?= build-cuda
JOBS        ?= $(shell nproc)
BINARY      := $(BUILD_DIR)/command_deck

.PHONY: all release debug cuda sdl2 full clean run check-deps format tidy asan help

# ── Default target ─────────────────────────────────────────────────────────
all: release

# ── Build targets ──────────────────────────────────────────────────────────
release:
	@cmake -B $(BUILD_DIR) -DCMAKE_BUILD_TYPE=Release
	@cmake --build $(BUILD_DIR) -j$(JOBS)
	@echo "\n✓ Build complete: $(BUILD_DIR)/command_deck"

debug:
	@cmake -B $(DEBUG_DIR) -DCMAKE_BUILD_TYPE=Debug
	@cmake --build $(DEBUG_DIR) -j$(JOBS)
	@echo "\n✓ Debug build complete: $(DEBUG_DIR)/command_deck"

cuda:
	@cmake -B $(CUDA_DIR) -DCMAKE_BUILD_TYPE=Release -DENABLE_CUDA=ON
	@cmake --build $(CUDA_DIR) -j$(JOBS)
	@echo "\n✓ CUDA build complete: $(CUDA_DIR)/command_deck"

sdl2:
	@cmake -B build-sdl2 -DCMAKE_BUILD_TYPE=Release -DENABLE_SDL2=ON
	@cmake --build build-sdl2 -j$(JOBS)

full:
	@cmake -B build-full \
		-DCMAKE_BUILD_TYPE=Release \
		-DENABLE_CUDA=ON \
		-DENABLE_SDL2=OFF \
		-DENABLE_DDCUTIL=ON
	@cmake --build build-full -j$(JOBS)
	@echo "\n✓ Full build complete: build-full/command_deck"

asan:
	@cmake -B build-asan \
		-DCMAKE_BUILD_TYPE=Debug \
		-DENABLE_ASAN=ON
	@cmake --build build-asan -j$(JOBS)
	@echo "\n✓ ASan build complete: build-asan/command_deck"

# ── Run ────────────────────────────────────────────────────────────────────
run: release
	@echo "Running $(BINARY) ..."
	@sudo $(BINARY)

run-debug: debug
	@sudo $(DEBUG_DIR)/command_deck

# ── Clean ──────────────────────────────────────────────────────────────────
clean:
	@rm -rf build build-debug build-cuda build-sdl2 build-full build-asan
	@echo "✓ Build directories removed"

# ── Development tools ──────────────────────────────────────────────────────
check-deps:
	@bash scripts/check-deps.sh

format:
	@find src include -name "*.cpp" -o -name "*.hpp" -o -name "*.cu" -o -name "*.cuh" \
		| xargs clang-format -i --style=file
	@echo "✓ Formatted all source files"

tidy: release
	@find src -name "*.cpp" | xargs \
		clang-tidy \
		--extra-arg=-std=c++20 \
		-p $(BUILD_DIR)/compile_commands.json \
		2>&1 | tee clang-tidy.log
	@echo "✓ clang-tidy complete — see clang-tidy.log"

# ── Help ───────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "CommandDeck build targets:"
	@echo "  make              Release build (default)"
	@echo "  make debug        Debug build (-O0 -g3)"
	@echo "  make cuda         Release + CUDA/OpenGL interop"
	@echo "  make sdl2         Release + SDL2 display backend"
	@echo "  make full         Release + CUDA + DDC/CI"
	@echo "  make asan         Debug + AddressSanitizer"
	@echo "  make clean        Remove all build directories"
	@echo "  make run          Build release then run (sudo)"
	@echo "  make check-deps   Verify system dependencies"
	@echo "  make format       clang-format all sources"
	@echo "  make tidy         clang-tidy static analysis"
	@echo ""
	@echo "Variables:"
	@echo "  BUILD_DIR=<dir>   Override release build dir (default: build)"
	@echo "  JOBS=<n>          Parallel jobs (default: nproc=$(shell nproc))"
	@echo ""
