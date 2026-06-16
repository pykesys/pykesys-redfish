# CommandDeck — C++ Source

C++ implementation of the ViewSonic TD2423D command-deck application for Linux. Uses the full input stack (evdev/libinput), DRM/KMS display output, OpenGL ES 3 via EGL/GBM, optional DDC/CI monitor control, and optional CUDA/OpenGL interop for ML visualization overlays.

**See [../docs/touchscreen.md](../docs/touchscreen.md) for the complete implementation guide**, including all source code, API documentation, and Appendix C for this development environment.

---

## Quick start

```bash
# 1. Install system dependencies (once)
sudo bash scripts/setup-dev.sh

# 2. Check everything is installed
make check-deps

# 3. Build and run
make
sudo ./build/command_deck
```

## Build targets

| Command | Description |
|---------|-------------|
| `make` | Release build |
| `make debug` | Debug build (-O0 -g3) |
| `make cuda` | Release + CUDA/OpenGL interop |
| `make sdl2` | Release + SDL2 display backend |
| `make full` | Release + CUDA + DDC/CI |
| `make asan` | Debug + AddressSanitizer |
| `make clean` | Remove all build directories |
| `make check-deps` | Verify system dependencies |
| `make format` | clang-format all sources |
| `make tidy` | clang-tidy static analysis |

## Directory layout

```
C++/
├── CMakeLists.txt       Main build file
├── Makefile             Convenience wrapper
├── scripts/
│   ├── setup-dev.sh     Install all system dependencies
│   ├── check-deps.sh    Verify dependencies (prints status table)
│   ├── build.sh         Scriptable build with all options
│   └── install-cuda.sh  Guided CUDA Toolkit installer
├── src/
│   ├── main.cpp
│   ├── input_loop.cpp   epoll-based touch + keyboard loop
│   ├── mt_tracker.cpp   Multi-touch Type B slot tracker
│   ├── gesture/         Tap, swipe, pinch recognizers
│   ├── display/         DRM device + EGL/GBM context
│   ├── ddc/             DDC/CI brightness/contrast control
│   └── cuda/            CUDA/OpenGL texture interop
├── include/             Header files
├── .clang-format        Code style (LLVM, 4-space indent, 100 col)
├── .clangd              Language server config (points at build/)
└── .vscode/             VSCode tasks, launch, and settings
```
