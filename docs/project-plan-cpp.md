# C++ Command Deck — Project Plan & Milestones

## Overview

The C++ command deck is a standalone application that runs directly on the DGX SuperPod hardware — no desktop compositor, no window manager — using the full Linux input stack (evdev/libinput), DRM/KMS display output, OpenGL ES 3 via EGL/GBM, DDC/CI monitor control, and optional CUDA/OpenGL interop for real-time ML visualization overlays.

It is designed to serve as the operator interface for managing the pod: touching panels controls BMC power and boot, the CUDA overlay displays live GPU utilization from the Redfish fleet layer, and all ten simultaneous touch points are tracked with per-slot visual identity.

See [docs/touchscreen.md](touchscreen.md) for the full implementation guide and hardware specs.
See [docs/guide-devs-touch.md](guide-devs-touch.md) for the effects→code developer guide.

---

## Table of Contents

- [Milestone v0.1 — Scaffold ✅ (Delivered)](#milestone-v01--scaffold--delivered)
- [Milestone v0.2 — Full Input + Render + CUDA ✅ (Delivered)](#milestone-v02--full-input--render--cuda--delivered)
- [Milestone v0.3 — UI Panels and Data Widgets](#milestone-v03--ui-panels-and-data-widgets)
- [Milestone v0.4 — Redfish Integration](#milestone-v04--redfish-integration)
- [Milestone v0.5 — Multi-Display + IFP55G1 Bridge](#milestone-v05--multi-display--ifp55g1-bridge)
- [Dependency Map](#dependency-map)

---

## Milestone v0.1 — Scaffold ✅ (Delivered)

**Goal:** Buildable project skeleton with CMake, directories, and stub source files.

### Delivered
- `C++/CMakeLists.txt` — full build definition with `ENABLE_CUDA`, `ENABLE_SDL2`, `ENABLE_DDCUTIL`, `ENABLE_ASAN`, `ENABLE_TSAN` feature gates
- `C++/Makefile` — human-facing targets: `make`, `make debug`, `make cuda`, `make full`, `make asan`, `make check-deps`, `make format`, `make tidy`, `make refs`
- `C++/scripts/` — `setup-dev.sh`, `check-deps.sh`, `build.sh`, `install-cuda.sh`, `download-refs.sh`, `update-ref-links.sh`
- `C++/.clang-format`, `.clangd`, `.vscode/` — IDE and code-style configuration
- `C++/include/` (empty), `C++/src/` stub `.cpp` files
- `docs/touchscreen.md` — hardware overview, Linux input stack, evdev protocol, DRM/KMS, EGL, DDC/CI, CUDA interop reference

### Definition of Done
- `make check-deps` reports all required packages
- `make` completes without errors on a system with all dependencies installed

---

## Milestone v0.2 — Full Input + Render + CUDA ✅ (Delivered)

**Goal:** Fully functional touch input processing, hardware-accelerated rendering, and CUDA overlay — all 10 touch points tracked and visualized with distinct per-slot identities and rich surface data.

### Delivered

**Input pipeline (`include/` + `src/`):**
- `common.hpp` — shared types: `TouchSlot` (with `touch_major`, `touch_minor`, `pressure`), `TouchEvent`, `KeyEvent`, `TouchCallback`, `KeyCallback`
- `touch_device.hpp` — `TouchDevice`: opens `/dev/input/eventN`, reads ABS axis ranges, exposes `has_abs()` + `normalize_abs()` for all MT axes
- `mt_tracker.hpp/.cpp` — `MTTracker`: full Linux MT Type B slot state machine capturing `ABS_MT_POSITION_X/Y`, `ABS_MT_TOUCH_MAJOR`, `ABS_MT_TOUCH_MINOR`, `ABS_MT_PRESSURE`; fires `TouchEvent` with contact geometry on `SYN_REPORT`
- `input_loop.hpp/.cpp` — `InputLoop`: epoll-based unified loop; multi-device support (add both TD2423D and IFP55G1 simultaneously); dedicated thread model
- `event_bus.hpp` — `SPSCQueue<T,N>`: lock-free single-producer/single-consumer ring buffer; `TouchQueue` (256 slots), `KeyQueue` (64 slots)

**Gesture recognizers (`include/gesture/`, `src/gesture/`):**
- `tap.hpp/.cpp` — `TapDetector`: two-phase single/double tap with `flush_pending()`
- `swipe.hpp/.cpp` — `SwipeDetector`: dominant-axis directional swipe with velocity
- `pinch.hpp/.cpp` — `PinchDetector`: rolling inter-finger distance ratio with 1% noise gate

**Display (`include/display/`, `src/display/`):**
- `drm_device.hpp/.cpp` — `DRMDevice`: DRM/KMS connector discovery, CRTC lookup, dumb framebuffer allocation, legacy mode setting
- `egl_context.hpp/.cpp` — `EGLContext`: GBM surface + EGL setup, vsync-locked page flip via `drmModePageFlip`

**DDC/CI (`include/ddc/`, `src/ddc/`):**
- `ddc_control.hpp/.cpp` — `DDCControl`: brightness, contrast, input source, power via libddcutil; graceful no-op when ddcutil not installed

**Renderer (`include/renderer.hpp`, `src/renderer.cpp`):**
- 10-slot color palette (`SLOT_COLORS[]`) — each slot has a unique, vibrant color
- `TouchIndicator` — rich per-slot state: `major_radius`, `minor_radius`, `pressure`, 16-point trail ring buffer, ripple animation state
- `draw_finger()` — 4-layer composite: comet trail → pressure halo → contact ellipse + centre dot → ripple burst
- `draw_finger_count()` — corner badge showing active finger count using slot colors
- CUDA overlay texture support; `overlay_tex_id()` accessor for registration

**CUDA overlay (`include/cuda_overlay.hpp`, `src/cuda/`):**
- `colormaps.cuh` — `colormap_hot()`, `colormap_viridis()`, `colormap_plasma()`, `colormap_utilization()` — polynomial fits, no LUT
- `cuda_gl_interop.cu` — 5 kernels: `colormap_kernel`, `clear_kernel`, `gaussian_splat_kernel`, `max_reduce_kernel`, `density_to_surface_kernel`, `gpu_bars_kernel`
- `CUDAOverlay` — CUDA device detection via PCI bus ID matching, stream-based async execution, `add_touch_point()`, `render_touch_density()`, `update_gpu_bars()`, `update_from_device/host()`
- Key bindings: F1=touch density, F2=GPU bars, F3=hide, F4=clear density

**Entry point (`src/main.cpp`):**
- Full threading model: input thread + render thread connected by SPSC queues
- Contact geometry → indicator sizing (with `CONTACT_SCALE` and `DEFAULT_MAJOR_R`)
- CUDA overlay integrated before render; overlay mode state machine

### Definition of Done
- `make` builds without errors
- `make cuda` builds with CUDA support on a system with nvcc
- Touch indicators show per-slot colors, correct ellipse sizing, trails, and ripples when a device is connected

---

## Milestone v0.3 — UI Panels and Data Widgets

**Goal:** A real command-deck UI — panels, buttons, status readouts — that an operator can actually use without reading source code.

### Scope

**Panel system:**
- `UIPanel` class: normalized-coordinate rectangle with title bar, content area, optional scrolling
- `UIButton`: touchable region with DOWN highlight, tap callback, label (text rendered via SDF font atlas or simple bitmap font)
- `UILabel`: static or dynamic text field
- `UIProgressBar`: horizontal bar, float [0,1], slot-color tinted

**Built-in panels for the command deck:**
- **Fleet status panel**: list of all registered BMC hosts (from Redfish SDK), health badge, power state badge, last-poll time
- **Node detail panel**: opens on tap of a fleet row; shows sensors, SEL log, firmware version
- **Action panel**: power on/off/reset buttons, boot override selector — calls Redfish API

**Font rendering:**
- Integrate [stb_truetype](https://github.com/nothings/stb) (header-only, no dependencies) for SDF text rendering
- Or: embed a simple bitmap font (8×8 or 16×16 per glyph) for Latin characters — sufficient for status labels

**New files:**
```
include/ui/panel.hpp
include/ui/button.hpp
include/ui/label.hpp
include/ui/font.hpp
src/ui/panel.cpp
src/ui/button.cpp
src/ui/renderer_ui.cpp   (extends Renderer with panel/text drawing)
assets/fonts/            (bitmap font or TTF)
```

### Acceptance Criteria
- Tapping a fleet host row opens a detail panel
- Power buttons send `GracefulRestart` via the Redfish SDK (pykesys-redfish)
- Text labels render correctly at display resolution (no pixelation at typical viewing distance)

---

## Milestone v0.4 — Redfish Integration

**Goal:** The command deck reads live data from the DGX SuperPod via the Redfish management network and displays it in real time on the touch panels and CUDA overlay.

### Scope

**pykesys-redfish SDK bridge:**
- Compile the Python SDK to a C extension (`pykesys_redfish_c`) or call a local HTTP endpoint
- Preferred path: run `redfish_web` Django backend alongside, call `GET /api/fleet/` from C++ using libcurl or a simple HTTP client
- Alternative: reimplement the ~5 Redfish endpoints we need directly in C++ using libcurl + nlohmann/json

**Data feeds:**
- Fleet health: poll `/api/fleet/` every 10s → update fleet status panel
- GPU telemetry: query NVML on the local DGX node every 1s → feed `CUDAOverlay::update_gpu_bars()`
- SEL events: subscribe to Redfish EventService → show notification badges on affected host tiles
- Temperature: pull `Chassis/Thermal` on tap → show in node detail panel

**CUDA overlay modes tied to real data:**
- GPU_BARS mode populated from real NVML utilization values
- HEATMAP mode: render training loss curve from a float array written by the training process via shared memory or a named pipe

**New files:**
```
include/data/fleet_poller.hpp    — polls Redfish API on background thread
include/data/nvml_sampler.hpp    — samples NVML GPU metrics
src/data/fleet_poller.cpp
src/data/nvml_sampler.cpp
```

### Acceptance Criteria
- Fleet status panel shows live health/power from a real DGX BMC (or the Redfish emulator)
- GPU bars overlay reflects real GPU utilization from the local node
- Tapping a host with health=Critical opens a SEL log with real error entries

---

## Milestone v0.5 — Multi-Display + IFP55G1 Bridge

**Goal:** Drive both the TD2423D operator panel (24") and the IFP55G1 bridge display (55") simultaneously, with the bridge display showing a team-visible fleet overview.

### Scope

**Multi-display DRM/KMS:**
- Enumerate all connectors in `DRMDevice::find_all_connectors()`
- Assign each connector its own CRTC + framebuffer
- Render different content to each display using separate `EGLContext` instances (or a single context with multiple surfaces)

**IFP55G1 specifics:**
- 40-point MT tracking: `MTTracker(40)`
- Dual TOUCH port routing: TOUCH1 → HDMI1, TOUCH2 → HDMI2/3 (see touchscreen.md §1.2)
- 4K UHD rendering (3840×2160) — requires higher-resolution assets and a stronger GPU budget

**Bridge display content:**
- Fleet grid: all DGX nodes as colour-coded tiles (health × power), live from Redfish
- CUDA overlay: full-resolution 4K heatmap of ML training metrics

**New files:**
```
include/display/multi_display.hpp   — manages N concurrent displays
src/display/multi_display.cpp
```

### Acceptance Criteria
- Both displays active simultaneously with independent content
- Touch on the TD2423D controls the operator panel
- Touch on the IFP55G1 navigates the team-facing fleet grid
- CUDA heatmap renders correctly at 4K resolution

---

## Dependency Map

```
v0.1 (scaffold)
  └── v0.2 (full input + render + CUDA)
        ├── v0.3 (UI panels)         ← need font rendering before data makes sense visually
        └── v0.4 (Redfish data)      ← can proceed independently of v0.3 (data-only)
              └── v0.5 (multi-display) ← needs both v0.3 UI and v0.4 data to be meaningful
```
