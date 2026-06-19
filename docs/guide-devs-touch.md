# Developer Guide — Touch Interface

This guide is for a developer joining this project who wants to understand the command-deck touch system from the *user-visible effect* backward to the *kernel event* that produces it. Most documentation works the other way (hardware spec → driver → API → app). This one starts with what you see on screen and traces it to its source.

Everything here is purpose-built. There is no desktop compositor, no X11, no Wayland. The application owns the display outright via DRM/KMS and reads raw hardware events via evdev. If you have never worked at this layer before, this guide is designed to make you dangerous quickly.

---

## Table of Contents

- [Part I — What This Is](#part-i--what-this-is)
- [Part II — Effects Catalog](#part-ii--effects-catalog)
  - [Effect 1: Contact Ellipse](#effect-1-contact-ellipse--finger-footprint)
  - [Effect 2: Comet Trail](#effect-2-comet-trail--motion-history)
  - [Effect 3: Pressure Halo](#effect-3-pressure-halo--force-ring)
  - [Effect 4: Ripple Burst](#effect-4-ripple-burst--down-animation)
  - [Effect 5: Centre Dot](#effect-5-centre-dot--precision-reference)
  - [Effect 6: Per-Slot Colors](#effect-6-per-slot-colors--finger-identity)
  - [Effect 7: Active-Finger Badge](#effect-7-active-finger-badge--corner-count)
  - [Effect 8: Touch Density Heatmap (CUDA)](#effect-8-touch-density-heatmap--cuda-)
  - [Effect 9: GPU Utilization Bars (CUDA)](#effect-9-gpu-utilization-bars--cuda-)
- [Part III — The Input Pipeline](#part-iii--the-input-pipeline)
- [Part IV — The Render Pipeline](#part-iv--the-render-pipeline)
- [Part V — CUDA Overlay](#part-v--cuda-overlay)
- [Part VI — How to Extend](#part-vi--how-to-extend)

---

## Part I — What This Is

### The hardware setup

```
TD2423D (24" PCAP touchscreen)         IFP55G1 (55" IR touchscreen, optional)
    │  USB upstream (touch)                 │  USB TOUCH1 / TOUCH2
    │  HDMI/DP (video)                      │  HDMI 2.0 (video)
    └──────────────┬────────────────────────┘
                   │
         DGX H100 SuperPod node
         ┌──────────────────────┐
         │  GPU 0               │  ← drives the display (DRM/KMS)
         │  GPU 1–7             │  ← ML training
         └──────────────────────┘
```

The touch signal and the video signal travel separately and are married in software: the touch device (`/dev/input/event*`) is a USB HID device; the display output is a DRM/KMS connector on the same GPU that does the rendering.

### The two threads

```
InputThread ─── epoll_wait() ────────────────────────► kernel event
                    │
                MTTracker::process()                  ← interpret MT protocol
                    │
                TouchCallback                         ← fires per SYN_REPORT
                    │
           ┌── TapDetector ── on_touch()
           ├── SwipeDetector ── on_touch()
           └── PinchDetector ── on_touch()
                    │
               touch_queue.push()                     ← SPSCQueue<TouchEvent,256>
                    │
RenderThread ── touch_queue.pop() ──────────────────► update TouchIndicator[]
                    │
               CUDAOverlay::add_touch_point()         ← feeds density accumulator
                    │
               Renderer::draw(indicators, now)        ← all visual effects
                    │
               EGLContext::swap_and_flip()            ← DRM page flip at vsync
```

The render thread runs at the display's native refresh rate (60 Hz) because `swap_and_flip()` blocks until the page flip completes. The input thread is unblocked by `epoll_wait()` and processes events as fast as the device delivers them (typically within 1ms of the kernel receiving the USB interrupt).

---

## Part II — Effects Catalog

Each entry shows: what it looks like, which kernel axis drives it, and the exact code path from event to pixel.

---

### Effect 1: Contact Ellipse — Finger Footprint

**What you see:** A colored ellipse at each active finger, sized to match the physical contact area. A flat-pressed fingertip is a wide oval; a precise stylus tap is nearly circular and tiny.

**Why it matters:** The ellipse tells you *how* the finger is touching, not just *where*. A very large major axis (> 0.3 normalized) is a palm — useful for palm rejection or distinguishing accidental contact from intentional taps.

#### Code path

```
Kernel:    ABS_MT_TOUCH_MAJOR  (ADC integer, range 0–N from device)
           ABS_MT_TOUCH_MINOR  (optional; many devices only send MAJOR)
               │
               │  mt_tracker.cpp :: MTTracker::process()
               │    case ABS_MT_TOUCH_MAJOR:
               │      slots_[current_slot_].touch_major =
               │          dev.normalize_abs(ABS_MT_TOUCH_MAJOR, ev.value)
               │    case ABS_MT_TOUCH_MINOR: (same, touch_minor field)
               │
               │  flush_frame() → TouchEvent{.touch_major, .touch_minor}
               │
               │  main.cpp :: touch_queue.pop() → DOWN branch
               │    ind.major_radius = ev->touch_major * CONTACT_SCALE  (0.5)
               │    ind.minor_radius = ev->touch_minor * CONTACT_SCALE
               │                       or major_radius if MINOR absent
               │
               ▼
           renderer.cpp :: draw_finger() → Layer 3
             draw_ellipse(ind.x, ind.y, ind.major_radius, ind.minor_radius, col)
               │
               │  Aspect ratio correction: ry = minor_r * (width/height)
               │  40-segment triangle fan in normalized screen space
               │  Y flip: gl_Position.y = -(norm_y * 2 - 1)
               │
               ▼  GL calls
           glUseProgram(prog_solid_)
           glUniform4f("u_color", r, g, b, a)
           glBufferSubData(vbo_, 0, sizeof(verts), verts)
           glDrawArrays(GL_TRIANGLE_FAN, 0, 42)
```

#### Tuning

| Parameter | Location | Effect |
|-----------|----------|--------|
| `CONTACT_SCALE` | `main.cpp` line 268 | Scale factor: 0.5 = ellipse half the kernel-reported size. Increase for larger visual footprint. |
| `DEFAULT_MAJOR_R` | `main.cpp` line 262 | Fallback radius (normalized) when device doesn't report TOUCH_MAJOR. 0.018 ≈ 35px on 1920px display. |
| `segments` arg | `draw_ellipse()` call | 40 for smooth circles; 12 for small dots (trail, centre). Reduce for performance. |

---

### Effect 2: Comet Trail — Motion History

**What you see:** A fading smear of smaller blobs trailing behind each moving finger, giving the impression of speed and direction. The trail is 16 positions deep; older positions are more transparent.

**Why it matters:** Trails make swipes visually legible — the operator can see at a glance that a fast diagonal swipe just happened. They also make it obvious when a finger is stationary (no trail) vs moving.

#### Code path

```
Kernel:    ABS_MT_POSITION_X/Y  (every MOVE event)
               │
               │  MTTracker: accumulates x,y in slots_[] on every MOVE
               │  flush_frame() fires TouchEvent::Type::MOVE
               │
               │  main.cpp :: MOVE branch
               │    ind.push_trail()    ← appends (x,y) to ring buffer
               │      trail_pts[trail_head] = {x, y}
               │      trail_head = (trail_head + 1) % TRAIL_LEN
               │      trail_count = min(trail_count + 1, TRAIL_LEN)
               │
               ▼
           renderer.cpp :: draw_trail(ind)
             for i in [0, trail_count-1]:
               idx = (trail_head - 1 - i + TRAIL_LEN) % TRAIL_LEN  // newest first
               alpha = 0.45 * (1 - i/trail_count)                  // fades to 0
               trail_color = (R,G,B, alpha*255)
               draw_ellipse(trail_pts[idx].x, trail_pts[idx].y,
                            major_radius * 0.35, ...)
```

The ring buffer traversal reads from newest to oldest: `trail_head - 1` is the most recent entry, `trail_head - trail_count` is the oldest.

#### Tuning

| Parameter | Location | Effect |
|-----------|----------|--------|
| `TRAIL_LEN` | `renderer.hpp` line 73 | Number of positions stored per finger. 16 = about 4 frames of trail at 60 Hz with fast swipes. |
| `alpha = 0.45 * (...)` | `renderer.cpp` draw_trail | Maximum trail opacity. Reduce for subtler trails. |
| `major_radius * 0.35` | `renderer.cpp` draw_trail | Trail blob radius relative to contact ellipse. |

---

### Effect 3: Pressure Halo — Force Ring

**What you see:** An outer ring surrounding the contact ellipse that expands when the operator presses harder. The ring uses the same slot color at reduced opacity. If the device doesn't report pressure (or pressure is constant), the halo is invisible.

**Why it matters:** On PCAP panels like the TD2423D, `ABS_MT_PRESSURE` is derived from capacitive signal strength, which correlates loosely with contact area rather than true force. The halo is a visual bonus when available, not a required interaction cue.

#### Code path

```
Kernel:    ABS_MT_PRESSURE  (0–N ADC range; may be absent or constant)
               │
               │  mt_tracker.cpp: slots_[slot].pressure =
               │      dev.normalize_abs(ABS_MT_PRESSURE, ev.value)
               │  Carried in TouchEvent.pressure
               │
               │  main.cpp: ind.pressure = ev->pressure
               │
               ▼
           renderer.cpp :: draw_finger()
             if (ind.pressure > 0.01f):           // skip if absent/zero
               halo_r = major_radius * (1 + pressure * 0.6)
               halo_color = (slot_color & 0xFFFFFF00) | 0x44  // alpha=0x44
               draw_ring(x, y,
                         major_radius * 1.05,     // inner edge
                         halo_r,                  // outer edge
                         halo_color,
                         0.5 + pressure * 0.3)    // alpha scales with pressure
```

`draw_ring()` generates a `GL_TRIANGLE_STRIP` alternating between inner and outer circle vertices at each angular step.

---

### Effect 4: Ripple Burst — DOWN Animation

**What you see:** When a finger first touches the screen, an expanding ring radiates outward from the contact point and fades over 350ms. The ring expands to 3× the contact radius before disappearing.

**Why it matters:** Immediate feedback that a DOWN event was registered. On a touchscreen with no tactile click, this tells the operator "yes, I saw that."

#### Code path

```
Kernel:    ABS_MT_TRACKING_ID (≥0 = new contact)
           SYN_REPORT         (END of frame containing the DOWN)
               │
               │  MTTracker: pending_downs_ → flush_frame → TouchEvent::DOWN
               │
               │  main.cpp :: DOWN branch
               │    ind.start_ripple(ev->time)
               │      ripple_start = now
               │      ripple_active = true
               │
               ▼  Every render frame while active:
           renderer.cpp :: draw_finger()
             rp = ind.ripple_progress(now)
               = elapsed_ms / RIPPLE_DURATION_MS  (350ms)
               = -1.0 if expired
             if (rp >= 0):
               outer = major_radius * (1 + rp * 3.0)  // 1x→4x expansion
               inner = outer * 0.85
               alpha = (1 - rp) * 0.8              // fades to zero
               draw_ring(x, y, inner, outer, slot_color, alpha)
```

The ripple is driven entirely by elapsed time — no state update needed in the render loop. `ripple_progress()` computes the fraction from the stored `ripple_start` timestamp.

#### Tuning

| Parameter | Location | Effect |
|-----------|----------|--------|
| `RIPPLE_DURATION_MS` | `renderer.hpp` line 82 | How long the animation lasts. 350ms is standard. |
| `rp * 3.0` expansion | `renderer.cpp` draw_finger | How far the ring travels. 3.0 = expands to 4× contact radius. |
| `alpha = (1-rp) * 0.8` | same | Peak opacity. |

---

### Effect 5: Centre Dot — Precision Reference

**What you see:** A small bright white dot at the exact centre of each finger's contact ellipse.

**Why it matters:** On a large PCAP display, the ellipse itself can be 30–40px across. The centre dot gives a single pixel-precise reference for hit-testing. It also gives visual feedback that the slot is active even if the contact ellipse is too small to see clearly.

#### Code path

```
renderer.cpp :: draw_finger() → between ellipse and ripple
  dot_r = ind.major_radius * 0.2
  draw_ellipse(ind.x, ind.y, dot_r, dot_r,
               0xFFFFFFCC,   // white, alpha=CC (80%)
               12)           // 12 segments: very small, low polygon count
```

---

### Effect 6: Per-Slot Colors — Finger Identity

**What you see:** Each of the 10 finger slots has a permanently assigned color. Slot 0 is always coral red; slot 4 is always sky blue; etc. When you lift and replace a finger, the new contact uses the same slot and therefore the same color.

**Why this design:** The Linux MT Type B protocol assigns tracking IDs to fingers, but those IDs increment monotonically and are not reused. The *slot* index (0–9) is stable — the same slot is used for each successive contact at roughly the same screen region. Using the slot index for color assignment gives consistent visual identity without chasing ephemeral tracking IDs.

#### The palette

From `include/renderer.hpp`, the `SLOT_COLORS` array:

| Slot | Color name | Hex (RGBA) |
|------|-----------|------------|
| 0 | Coral red | `0xFF3344FF` |
| 1 | Amber orange | `0xFF9900FF` |
| 2 | Lime green | `0x55FF33FF` |
| 3 | Cyan | `0x00EEFFFF` |
| 4 | Sky blue | `0x3388FFFF` |
| 5 | Violet | `0xBB44FFFF` |
| 6 | Hot pink | `0xFF44AAFF` |
| 7 | Gold | `0xFFDD00FF` |
| 8 | Teal | `0x00DDAAFF` |
| 9 | Tangerine | `0xFF8833FF` |

For devices with >10 slots (IFP55G1: 40), colors repeat modulo 10: `SLOT_COLORS[slot % 10]`.

#### Code path

```
include/renderer.hpp :: TouchIndicator::color()
  return SLOT_COLORS[slot % SLOT_COLORS.size()]

renderer.cpp :: draw_finger()
  const uint32_t col = ind.color()
  // col is passed to draw_ellipse, draw_ring, draw_trail, draw_ripple
```

---

### Effect 7: Active-Finger Badge — Corner Count

**What you see:** A row of small colored squares in the top-right corner of the display. One square per active finger, using each finger's slot color.

**Why it matters:** Diagnostic feedback from a distance. An operator across the room can see at a glance that three fingers are registered without leaning over to check the ellipses.

#### Code path

```
renderer.cpp :: Renderer::draw()
  int active_count = 0
  for (ind : indicators):
    if (ind.active): active_count++, draw_finger(ind, now)
  draw_finger_count(active_count)

renderer.cpp :: draw_finger_count(count)
  BADGE_SIZE = 0.018   // normalized width/height per square
  BADGE_PAD  = 0.006   // gap
  BADGE_TOP  = 0.012   // top margin
  BADGE_RIGHT= 0.012   // right margin
  for i in [0, count):
    x = 1.0 - BADGE_RIGHT - BADGE_SIZE - i*(BADGE_SIZE+BADGE_PAD)
    draw_rect({x, BADGE_TOP, BADGE_SIZE, BADGE_SIZE}, SLOT_COLORS[i])
```

Squares are drawn right-to-left so the first active finger (slot 0) is always the rightmost badge.

---

### Effect 8: Touch Density Heatmap (CUDA)

**What you see (F1 mode):** A full-screen heatmap that accumulates over time, showing where on the screen the operator has been touching. Areas of high contact density appear bright (viridis colormap); untouched areas are fully transparent. Faint halos bloom outward from frequently-touched points.

**Why it matters:** Shows which UI regions are used and which are ignored. After a day of operation, the density map is a usage analytics artifact — you can see exactly which buttons are being used.

#### Code path

```
main.cpp :: DOWN/MOVE branch
  float sigma = 0.015 + ind.major_radius * 0.5    // larger for bigger contacts
  cuda_overlay->add_touch_point(ev->x, ev->y, sigma)

cuda_gl_interop.cu :: CUDAOverlay::add_touch_point()
  gaussian_splat_kernel<<<grid, block, stream>>>(
      d_density_,           // float[W*H] accumulator on GPU
      width_, height_,
      norm_x, norm_y, sigma, weight=1.0)

  gaussian_splat_kernel device code:
    dist2 = (px-cx)^2 + (py-cy)^2
    if (dist2 > 9*sigma^2) return        // beyond 3σ cutoff
    atomicAdd(&density[y*W+x],
              weight * exp(-dist2 / (2*sigma^2)))

main.cpp :: render loop (before renderer.draw)
  cuda_overlay->render_touch_density()

cuda_gl_interop.cu :: CUDAOverlay::render_touch_density()
  max_reduce_kernel → finds max(d_density_)       // parallel reduction
  density_to_surface_kernel:
    val = density[y*W+x] / max_density
    pixel = colormap_viridis(val)
    pixel.w = val < 0.01 ? 0 : val*2*220          // transparent where zero
    surf2Dwrite(pixel, surf, x*4, y)               // writes directly to GL texture

renderer.cpp :: draw_overlay()
  glUseProgram(prog_texture_)
  glBindTexture(GL_TEXTURE_2D, overlay_tex_)
  glUniform1f("u_alpha", 0.6)                       // 60% blend
  glDrawArrays(GL_TRIANGLES, 0, 6)                  // full-screen quad
```

The key primitive: `surf2Dwrite` writes to the same physical GPU memory that OpenGL reads as a texture. No CPU roundtrip. The `cudaGraphicsMapResources` / `cudaGraphicsUnmapResources` calls hand texture ownership between the two APIs.

---

### Effect 9: GPU Utilization Bars (CUDA)

**What you see (F2 mode):** Eight vertical bars spanning the display, each representing one H100 GPU's utilization percentage. Color codes: green (<50%), yellow (50–80%), orange (80–95%), red (>95%). Bars update every render frame.

**Why it matters:** The DGX H100 SXM5 has 8 GPUs all training simultaneously. This overlay lets the command-deck operator monitor all 8 without a separate terminal.

#### Code path

```
main.cpp :: render loop CUDA section
  // Animate demo data (replace with real NVML or Redfish telemetry)
  gpu_utils[g] = 60 + 35*sin(frame*0.02 + g*0.7)
  cuda_overlay->update_gpu_bars(gpu_utils)

cuda_gl_interop.cu :: CUDAOverlay::update_gpu_bars()
  cudaMemcpyAsync(d_gpu_utils_, h_utils.data(), count*4, H2D, stream)

  gpu_bars_kernel<<<grid, block, stream>>>(surf, W, H, d_gpu_utils_, n_gpus):
    bar_w = W / n_gpus
    gpu_idx = x / bar_w
    fill = utils[gpu_idx] / 100
    fill_top = (1-fill) * H                  // 100% fills the full bar height
    pixel = (y >= fill_top) ?
              colormap_utilization(utils[gpu_idx])   // inside bar
            : make_uchar4(15, 15, 25, 180)           // dark background above bar
    surf2Dwrite(pixel, surf, x*4, y)
```

To replace the demo animation with real data:
```cpp
// In the render loop, before update_gpu_bars():
// Option A: NVML on the local node
nvmlDeviceGetUtilizationRates(device[g], &util);
gpu_utils[g] = util.gpu;

// Option B: from pykesys-redfish Redfish SDK poll
// (poll /api/fleet/ in a background thread, read results here)
```

---

## Part III — The Input Pipeline

### Step 1: The kernel delivers raw events

The touchscreen controller sends USB HID reports. The `hid-multitouch` kernel module converts them to `struct input_event` packets and queues them in the character device at `/dev/input/event*`.

Each packet is 24 bytes:
```c
struct input_event {
    struct timeval time;   // 8 bytes: timestamp
    __u16 type;            // 2 bytes: EV_ABS, EV_SYN, EV_KEY
    __u16 code;            // 2 bytes: ABS_MT_SLOT, ABS_MT_POSITION_X, ...
    __s32 value;           // 4 bytes: the axis value
};
```

### Step 2: MTTracker assembles frames

The MT Type B protocol is incremental — you need to maintain state across events to understand any one event. `MTTracker::process()` does this bookkeeping:

```
Event arrives → switch(ev.code):
  ABS_MT_SLOT         → set current_slot_ = ev.value
  ABS_MT_TRACKING_ID  → ev.value ≥ 0: finger DOWN on this slot
                         ev.value = -1: finger UP
  ABS_MT_POSITION_X   → update slots_[current_slot_].x
  ABS_MT_POSITION_Y   → update slots_[current_slot_].y
  ABS_MT_TOUCH_MAJOR  → update slots_[current_slot_].touch_major
  ABS_MT_TOUCH_MINOR  → update slots_[current_slot_].touch_minor
  ABS_MT_PRESSURE     → update slots_[current_slot_].pressure
  EV_SYN/SYN_REPORT   → flush_frame(): emit TouchEvents, clear pending lists
```

A critical invariant: **ABS_MT_SLOT changes are sticky**. If the device sends:
```
SLOT 2
POSITION_X 15000
POSITION_Y 8000
```
...then both X and Y apply to slot 2, even though slot 2 appeared in a previous event. `current_slot_` holds context across events until the next `ABS_MT_SLOT`.

### Step 3: The SPSC queue crosses thread boundaries

`TouchCallback` is called by the input thread. The render thread must never be called from the input thread (it owns the GL context). `SPSCQueue<TouchEvent, 256>` bridges them:

- `push()`: called by input thread — stores event, advances `write_` with `memory_order_release`
- `pop()`: called by render thread — reads event, advances `read_` with `memory_order_release`

No mutex, no condition variable, no CPU CAS. The ring-buffer invariant is maintained purely by the ordering of two atomic store/load pairs. This is safe because exactly one thread writes and one thread reads — the SPSC constraint.

---

## Part IV — The Render Pipeline

### Coordinate systems

There are three coordinate systems in play. Confusing them is the most common source of visual bugs:

| System | Origin | X | Y | Used by |
|--------|--------|---|---|---------|
| **Normalized screen** | top-left | right→ | down↓ | Touch events, `TouchIndicator.x/y`, all `draw_*` inputs |
| **GL clip space** | centre | right→ | up↑ | `gl_Position` in vertex shader |
| **Pixel** | top-left | right→ | down↓ | `glViewport`, hit testing |

The vertex shader converts normalized→clip space:
```glsl
gl_Position = vec4(norm_x * 2.0 - 1.0,
                   -(norm_y * 2.0 - 1.0),   // Y flip
                   0.0, 1.0);
```

**If you add a new draw function**, pass normalized [0,1] coordinates. The shader handles the rest.

### The single VAO/VBO

All geometry shares one VAO and one VBO. Per-draw, vertices are uploaded via `glBufferSubData`. This works because the draw calls are sequential on the render thread — there's no parallel rendering.

The VBO is pre-allocated as `GL_DYNAMIC_DRAW` for 512 vertices. If you add a draw function that needs more vertices, increase this value in `Renderer::init_buffers()`.

### The draw order (back to front)

Within `Renderer::draw()`:
1. `glClear` — dark background
2. `draw_overlay()` — CUDA texture (if enabled and visible)
3. For each active finger: `draw_finger(ind, now)` which internally draws:
   - Trail (oldest → newest fading blobs)
   - Pressure halo ring (if pressure > 0.01)
   - Contact ellipse
   - Centre dot
   - Ripple ring (if animation still running)
4. `draw_finger_count()` — top-right badges

Alpha blending is `GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA`. Draw order matters: things drawn first appear behind things drawn later.

---

## Part V — CUDA Overlay

### How CUDA and OpenGL share the texture

```
GL creates a texture:
  glGenTextures → overlay_tex_ (uint32_t texture ID)

CUDAOverlay registers it:
  cudaGraphicsGLRegisterImage(&cuda_resource_, overlay_tex_, GL_TEXTURE_2D, ...)
  // cuda_resource_ is now a handle to the same physical GPU memory

Before each CUDA kernel:
  cudaGraphicsMapResources(&cuda_resource_, stream)
  // GL cannot read the texture while it is mapped to CUDA

  cudaGraphicsSubResourceGetMappedArray(&arr, cuda_resource_, 0, 0)
  cudaCreateSurfaceObject(&surf, &arr_desc)
  // surf is a CUDA surface object: kernels call surf2Dwrite(surf, x*4, y)

After each CUDA kernel:
  cudaDestroySurfaceObject(surf)
  cudaGraphicsUnmapResources(&cuda_resource_, stream)
  cudaStreamSynchronize(stream)
  // GL can now read the texture
```

**The ordering constraint:** `CUDAOverlay::render_touch_density()` (or `update_gpu_bars()`) must be called *before* `Renderer::draw()`. In `main.cpp`, the CUDA update happens first in the render loop, then `renderer.draw(indicators, now)`.

### Adding a new CUDA visualization

1. Add a case to `CUDAOverlay::Mode` in `include/cuda_overlay.hpp`
2. Write a kernel in `src/cuda/cuda_gl_interop.cu`
3. Add a case to `update_from_device()` in the same file
4. Add a key binding and mode state in `main.cpp`

Skeleton for a new kernel:
```cuda
__global__ void my_kernel(cudaSurfaceObject_t surf,
                           const float* d_data,
                           int width, int height)
{
    const int x = blockIdx.x * blockDim.x + threadIdx.x;
    const int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= width || y >= height) return;

    // Your data → color mapping here
    float val = d_data[y * width + x];
    uchar4 pixel = colormap_viridis(val);  // from colormaps.cuh

    surf2Dwrite(pixel, surf, x * (int)sizeof(uchar4), y);
}
```

Launch it the same way as the others:
```cpp
colormap_kernel<<<grid2d(width_, height_), block2d(), 0, str>>>(
    surf, d_data, width_, height_);
```

### Connecting to Redfish telemetry

To feed real GPU utilization into `update_gpu_bars()`:

```cpp
// Option A: NVML (local node)
#include <nvml.h>
nvmlInit();
nvmlDevice_t devices[8];
for (int g = 0; g < 8; g++) nvmlDeviceGetHandleByIndex(g, &devices[g]);

// In render loop:
for (int g = 0; g < 8; g++) {
    nvmlUtilization_st util;
    nvmlDeviceGetUtilizationRates(devices[g], &util);
    gpu_utils[g] = static_cast<float>(util.gpu);
}
cuda_overlay->update_gpu_bars(gpu_utils);

// Option B: Redfish SDK (remote DGX nodes via pykesys-redfish)
// Poll GET /api/fleet/ from a background thread;
// store results in a mutex-protected std::vector<float>;
// read them on the render thread for update_gpu_bars().
```

---

## Part VI — How to Extend

### Adding a new visual effect

1. **Add fields to `TouchIndicator`** in `include/renderer.hpp` if the effect needs per-slot state
2. **Update the touch event drain** in `main.cpp` to populate those fields
3. **Add a draw method** in `include/renderer.hpp` and implement in `src/renderer.cpp`:
   - Accept normalized [0,1] coordinates
   - Call `draw_ellipse()`, `draw_ring()`, or `draw_rect()` as building blocks
   - Or write raw triangle geometry and call `glBufferSubData` + `glDrawArrays` directly
4. **Call it from `draw_finger()`** in `src/renderer.cpp` at the appropriate layer

Example — adding a pulse effect (brightness oscillates with a sine wave):

```cpp
// In renderer.hpp :: TouchIndicator
float pulse_phase{0.f};   // add this field

// In main.cpp :: MOVE branch
ind.pulse_phase += 0.15f;  // advances each frame

// In renderer.cpp :: draw_finger(), after centre dot
float pulse_alpha = 0.3f + 0.2f * std::sin(ind.pulse_phase);
uint32_t pulse_col = (ind.color() & 0xFFFFFF00) |
                     static_cast<uint32_t>(pulse_alpha * 255);
draw_ellipse(ind.x, ind.y, ind.major_radius * 1.3f, ind.minor_radius * 1.3f,
             pulse_col, 24);
```

### Adding a new gesture

1. Create `include/gesture/mygeo.hpp` and `src/gesture/mygeo.cpp` following the pattern of `tap.hpp/.cpp`
2. Add `#include` and instantiation in `main.cpp`
3. Register with `on_touch(e)` in the `touch_cb` lambda

Minimum interface:
```cpp
class MyGestureDetector {
public:
    struct MyEvent { /* your data */ };
    using Callback = std::function<void(const MyEvent&)>;
    explicit MyGestureDetector(Callback cb);
    void on_touch(const TouchEvent& e);
};
```

### Supporting a second display (IFP55G1)

1. Call `input_loop.add_touch("/dev/input/by-id/...")` with the IFP55G1's device path
2. Create a second `MTTracker(40)` (40 slots for IFP55G1 vs 10 for TD2423D)
3. Create a second `EGLContext` for the second DRM connector
4. Render different content to each context (e.g., fleet overview on the 55" bridge display)

The `InputLoop` already supports multiple touch devices — they share the same epoll fd and dispatch via per-device tags.

---

*See [docs/touchscreen.md](touchscreen.md) for hardware specifications, kernel protocol details, calibration, and DDC/CI reference.*
*See [docs/project-plan-cpp.md](project-plan-cpp.md) for the milestone roadmap.*
*See [docs/architecture.md](architecture.md) for the overall system architecture including the Python SDK and Django web layers.*
