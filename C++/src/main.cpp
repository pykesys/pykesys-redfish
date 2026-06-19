// main.cpp — CommandDeck application entry point
//
// This file assembles the full system from its parts.  Think of it as the
// wiring diagram: it creates all the objects, connects them together, and
// starts the two threads that keep everything running.
//
// Threading model (two threads, one SPSC queue per event type):
//
//   ┌──────────────────────────────────────────────────────────┐
//   │  InputThread                                             │
//   │  epoll_wait → MTTracker → TouchCallback → touch_queue   │
//   │                        → TapDetector                    │
//   │                        → SwipeDetector                  │
//   │                        → PinchDetector                  │
//   │  KeyCallback → key_queue                                 │
//   └────────────────────────┬─────────────────────────────────┘
//                            │  SPSC queues (lock-free)
//   ┌────────────────────────▼─────────────────────────────────┐
//   │  RenderThread (main thread)                              │
//   │  drain queues → update UI state                          │
//   │  CUDAOverlay::render_touch_density() / update_gpu_bars() │
//   │  Renderer::draw()                                        │
//   │  EGLContext::swap_and_flip() → DRM page flip → display   │
//   └──────────────────────────────────────────────────────────┘
//
// CUDA overlay modes cycle on F-keys:
//   F1 → touch density (accumulated heatmap of where you've touched)
//   F2 → GPU utilization bars (8 H100s from Redfish telemetry)
//   F3 → hide overlay
//
// Device paths: customise these for your hardware setup.
// Run `ls -la /dev/input/by-id/` to find the stable symlinks for each device.
// The emulator section below shows how to run against the Redfish emulator
// on a development machine — replace with real paths on the DGX.

#include "input_loop.hpp"
#include "event_bus.hpp"
#include "gesture/tap.hpp"
#include "gesture/swipe.hpp"
#include "gesture/pinch.hpp"
#include "display/drm_device.hpp"
#include "display/egl_context.hpp"
#include "ddc/ddc_control.hpp"
#include "renderer.hpp"
#include <thread>
#include <atomic>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include <linux/input-event-codes.h>

#ifdef HAVE_CUDA
#include "cuda_overlay.hpp"
#endif

// ── Configuration ─────────────────────────────────────────────────────────────
// Adjust these paths for your target system.

// TD2423D touch device — find with: ls /dev/input/by-id/ | grep -i viewsonic
static const char* TOUCH_DEVICE  = "/dev/input/by-id/usb-ViewSonic_TD2423D-event-if00";

// Keyboard — find with: ls /dev/input/by-id/ | grep -i kbd
static const char* KBD_DEVICE    = "/dev/input/by-id/usb-USB_Keyboard-event-kbd";

// DRM device — usually card0 on DGX systems with a single GPU.
static const char* DRM_DEVICE    = "/dev/dri/card0";

// ── Global shutdown signal ────────────────────────────────────────────────────
// SIGINT (Ctrl+C) and SIGTERM both set this flag.
// Both threads check it on each iteration to exit cleanly.
static std::atomic<bool> g_shutdown{false};

static void signal_handler(int /*sig*/) {
    g_shutdown.store(true, std::memory_order_relaxed);
}

// ── Main ──────────────────────────────────────────────────────────────────────
int main(int /*argc*/, char** /*argv*/) {
    std::signal(SIGINT,  signal_handler);
    std::signal(SIGTERM, signal_handler);

    // ── Event queues: InputThread → RenderThread ──────────────────────────
    TouchQueue touch_queue;
    KeyQueue   key_queue;

    // ── Gesture recognizers (run on the input thread) ──────────────────────
    // They receive every TouchEvent and fire their own callbacks.
    // Here we just print — in a real UI, these would trigger state changes
    // pushed through a separate UI event queue.
    TapDetector tap([](const TapDetector::TapEvent& e) {
        printf("[TAP x%d] at (%.3f, %.3f)\n", e.count, e.x, e.y);
    });
    SwipeDetector swipe([](const SwipeDetector::SwipeEvent& e) {
        const char* dirs[] = {"LEFT","RIGHT","UP","DOWN"};
        printf("[SWIPE %s] %d finger(s), v=%.2f\n",
               dirs[static_cast<int>(e.dir)], e.finger_count, e.velocity);
    });
    PinchDetector pinch([](const PinchDetector::PinchEvent& e) {
        printf("[PINCH] scale=%.3f center=(%.3f, %.3f)\n",
               e.scale, e.center_x, e.center_y);
    });

    // ── Input loop ────────────────────────────────────────────────────────
    // The TouchCallback runs on the input thread: push events into the
    // queue AND feed the gesture recognizers.
    InputLoop input_loop;

    auto touch_cb = [&](const TouchEvent& e) {
        touch_queue.push(e);
        tap.on_touch(e);
        swipe.on_touch(e);
        pinch.on_touch(e);
    };
    auto key_cb = [&](const KeyEvent& e) {
        key_queue.push(e);
        // Escape key exits the application.
        if (e.code == KEY_ESC && e.value == 1)
            g_shutdown.store(true, std::memory_order_relaxed);
    };

    // Try to open the devices.  If they don't exist (development machine
    // without a TD2423D), we log a warning and continue — the render loop
    // will still run, just without touch input.
    try {
        input_loop.add_touch(TOUCH_DEVICE);
        printf("[InputLoop] Touch device: %s\n", TOUCH_DEVICE);
    } catch (const std::exception& ex) {
        fprintf(stderr, "[InputLoop] WARNING: %s\n", ex.what());
        fprintf(stderr, "            Touch input disabled.  "
                        "Check TOUCH_DEVICE path in main.cpp.\n");
    }
    try {
        input_loop.add_keyboard(KBD_DEVICE);
        printf("[InputLoop] Keyboard: %s\n", KBD_DEVICE);
    } catch (const std::exception& ex) {
        fprintf(stderr, "[InputLoop] WARNING: %s\n", ex.what());
    }

    // Launch the input thread.
    std::thread input_thread([&] {
        try {
            input_loop.run(touch_cb, key_cb);
        } catch (const std::exception& ex) {
            fprintf(stderr, "[InputThread] Fatal: %s\n", ex.what());
            g_shutdown.store(true, std::memory_order_relaxed);
        }
    });

    // ── Display setup ─────────────────────────────────────────────────────
    // DRM/KMS: find the connected display and set up the framebuffer.
    DRMDevice drm(DRM_DEVICE);

    auto* conn = drm.find_connector();
    if (!conn) {
        fprintf(stderr, "[DRM] No display connected to %s\n", DRM_DEVICE);
        input_loop.stop();
        input_thread.join();
        return EXIT_FAILURE;
    }

    drmModeModeInfo& mode = conn->modes[0];  // modes[0] = preferred mode
    const uint32_t W = mode.hdisplay;
    const uint32_t H = mode.vdisplay;
    printf("[DRM] Display: %ux%u @ %uHz\n", W, H, mode.vrefresh);

    const uint32_t crtc_id = drm.find_crtc_for_connector(conn);

    // EGL + GBM: hardware-accelerated rendering surface.
    EGLContext egl_ctx(drm.fd(), W, H);
    egl_ctx.make_current();

    // Activate the display mode using the EGL surface's first rendered frame.
    // We must set the mode before the first page flip.
    // drmModeSetCrtc expects a valid framebuffer, but we haven't rendered
    // anything yet — render one blank frame first.
    Renderer renderer(egl_ctx, W, H);
    const auto startup_time = std::chrono::steady_clock::now();
    renderer.draw({}, startup_time);   // blank frame to prime the swap chain
    egl_ctx.swap_and_flip(crtc_id, conn->connector_id, &mode);
    // Now set the CRTC to show the display.
    drm.set_mode(crtc_id, conn->connector_id,
                 0,  // fb_id 0 — EGLContext manages its own fb ids
                 &mode);

    drmModeFreeConnector(conn);

    // ── Optional: DDC/CI brightness control ───────────────────────────────
    // This is best-effort — failure is not fatal.
    try {
        DDCControl ddc;
        printf("[DDC] Connected: %s  brightness=%d\n",
               ddc.model_name().c_str(), ddc.get_brightness());
        ddc.set_brightness(75);  // dim slightly for comfortable viewing
    } catch (const std::exception& ex) {
        fprintf(stderr, "[DDC] INFO: %s (DDC/CI disabled)\n", ex.what());
    }

    // ── CUDA overlay (optional — compiled in only when ENABLE_CUDA=ON) ────
    //
    // The overlay is a full-screen RGBA8 texture that CUDA kernels write
    // into directly, blended on top of the UI by the renderer.
    //
    // Overlay modes:
    //   TOUCH_DENSITY — accumulates gaussian splats at each touch point.
    //                   Shows where the operator has been touching over time.
    //                   Useful for identifying UI hot-spots and unused regions.
    //
    //   GPU_BARS      — 8-bar chart of H100 GPU utilization (0–100%).
    //                   Populated from Redfish telemetry pulled from the DGX
    //                   management controller (see pykesys-redfish SDK).
    //
    // Key bindings (handled in the key event drain below):
    //   F1 → touch density mode
    //   F2 → GPU bars mode
    //   F3 → hide overlay

#ifdef HAVE_CUDA
    // The CUDAOverlay constructor registers the overlay texture with CUDA.
    // It must be called AFTER the renderer (which creates overlay_tex_) and
    // AFTER EGL is current on this thread.  The display GPU is auto-detected.
    std::unique_ptr<CUDAOverlay> cuda_overlay;
    try {
        cuda_overlay = std::make_unique<CUDAOverlay>(
            renderer.overlay_tex_id(), static_cast<int>(W), static_cast<int>(H));
        renderer.set_overlay_visible(true);
        printf("[CUDA] Overlay ready on %s\n", cuda_overlay->device_name().c_str());
        printf("[CUDA] F1=touch density  F2=GPU bars  F3=hide\n");
    } catch (const std::exception& ex) {
        fprintf(stderr, "[CUDA] WARNING: overlay unavailable: %s\n", ex.what());
    }

    // Track which overlay mode is active.
    enum class OverlayMode { TOUCH_DENSITY, GPU_BARS, HIDDEN };
    OverlayMode overlay_mode = OverlayMode::TOUCH_DENSITY;

    // Simulated GPU utilization data — in production this comes from the
    // Redfish SDK polling the DGX BMC via pykesys-redfish.
    // Replace with real telemetry from your Redfish fleet manager.
    std::vector<float> gpu_utils(8, 0.f);
    int gpu_util_frame = 0;  // frame counter for demo animation
#endif

    // ── Render loop ───────────────────────────────────────────────────────
    // Runs on the main thread at the display's refresh rate (vsync-locked
    // by egl_ctx.swap_and_flip() which blocks until page flip completes).
    printf("[Render] Starting render loop at %ux%u\n", W, H);

    // Allocate one TouchIndicator per slot.
    // TD2423D has 10 slots (slots 0–9); IFP55G1 has 40 (slots 0–39).
    // We allocate MAX_SLOTS and index directly by slot number so there
    // is never any indirection — indicators[s] is always slot s.
    constexpr int MAX_SLOTS = 40;
    std::vector<TouchIndicator> indicators(MAX_SLOTS);
    for (int s = 0; s < MAX_SLOTS; ++s) indicators[s].slot = s;

    // Minimum contact radius when the device doesn't report TOUCH_MAJOR.
    // 1.8% of screen width ≈ 34px on a 1920px-wide display — comfortable
    // to see from a meter away.
    constexpr float DEFAULT_MAJOR_R = 0.018f;

    // Scale factor: ABS_MT_TOUCH_MAJOR is in the same ADC units as position.
    // A fingertip contact is roughly 15–20mm; the TD2423D active area is
    // 521mm wide with a 0–32767 ADC range.  So 1 ADC unit ≈ 521/32767 mm.
    // Normalized TOUCH_MAJOR for a 15mm contact ≈ 15/521 ≈ 0.029.
    // We scale by 0.5 so the rendered ellipse matches the physical contact
    // rather than fully occluding the finger.
    constexpr float CONTACT_SCALE = 0.5f;

    auto now = std::chrono::steady_clock::now();

    while (!g_shutdown.load(std::memory_order_relaxed)) {
        now = std::chrono::steady_clock::now();

        // Drain touch events.  All events since the last frame are
        // processed here before we render — so the frame always reflects
        // the most current input state, not last frame's.
        while (auto ev = touch_queue.pop()) {
            const int s = ev->slot;
            if (s < 0 || s >= MAX_SLOTS) continue;

            auto& ind = indicators[s];
            ind.slot = s;

            if (ev->type == TouchEvent::Type::DOWN) {
                // New finger: reset trail, start ripple burst.
                ind.active = true;
                ind.x = ev->x;
                ind.y = ev->y;
                ind.clear_trail();
                ind.push_trail();
                ind.start_ripple(ev->time);

                // Contact ellipse from TOUCH_MAJOR/MINOR, or default.
                ind.major_radius = ev->touch_major > 0.01f
                    ? ev->touch_major * CONTACT_SCALE
                    : DEFAULT_MAJOR_R;
                ind.minor_radius = ev->touch_minor > 0.01f
                    ? ev->touch_minor * CONTACT_SCALE
                    : ind.major_radius;  // circular if MINOR not reported

                ind.pressure = ev->pressure;

#ifdef HAVE_CUDA
                // Feed DOWN into the CUDA touch density accumulator.
                // sigma scales with contact size so a big palm press creates
                // a broader gaussian than a precise fingertip tap.
                if (cuda_overlay) {
                    const float sigma = 0.015f + ind.major_radius * 0.5f;
                    cuda_overlay->add_touch_point(ev->x, ev->y, sigma);
                }
#endif

            } else if (ev->type == TouchEvent::Type::MOVE) {
                // Finger sliding: update position and append to trail.
                ind.x = ev->x;
                ind.y = ev->y;
                ind.push_trail();

                // Update contact geometry as it changes during the stroke.
                // A finger pressing harder flattens out — MAJOR grows.
                if (ev->touch_major > 0.01f) {
                    ind.major_radius = ev->touch_major * CONTACT_SCALE;
                    ind.minor_radius = ev->touch_minor > 0.01f
                        ? ev->touch_minor * CONTACT_SCALE
                        : ind.major_radius;
                }
                ind.pressure = ev->pressure;

#ifdef HAVE_CUDA
                // Continue density accumulation during the drag.
                // Smaller sigma than DOWN so dragging draws a tight path
                // rather than a fat smear.
                if (cuda_overlay) {
                    const float sigma = 0.010f + ind.major_radius * 0.3f;
                    cuda_overlay->add_touch_point(ev->x, ev->y, sigma);
                }
#endif

            } else if (ev->type == TouchEvent::Type::UP) {
                // Finger lifted: mark inactive but don't clear trail yet.
                // The trail fades out over the next few frames naturally
                // because active=false stops new trail points being added.
                ind.active = false;
                ind.pressure = 0.f;
                ind.clear_trail();  // clean reset for next touch on this slot
            }
        }

        // Drain key events.
        while (auto ev = key_queue.pop()) {
            if (ev->value != 1) continue;  // only process key-down
#ifdef HAVE_CUDA
            if (cuda_overlay) {
                if (ev->code == KEY_F1) {
                    overlay_mode = OverlayMode::TOUCH_DENSITY;
                    renderer.set_overlay_visible(true);
                    printf("[CUDA] Overlay: touch density\n");
                } else if (ev->code == KEY_F2) {
                    overlay_mode = OverlayMode::GPU_BARS;
                    renderer.set_overlay_visible(true);
                    printf("[CUDA] Overlay: GPU bars\n");
                } else if (ev->code == KEY_F3) {
                    overlay_mode = OverlayMode::HIDDEN;
                    renderer.set_overlay_visible(false);
                    printf("[CUDA] Overlay: hidden\n");
                } else if (ev->code == KEY_F4) {
                    cuda_overlay->clear_density();
                    printf("[CUDA] Touch density cleared\n");
                }
            }
#endif
        }

        // Flush pending single-tap timers.
        tap.flush_pending(now);

        // ── CUDA overlay update ────────────────────────────────────────────
        // Update the overlay BEFORE renderer.draw() — the GL texture must not
        // be in use by GL when CUDA maps it (cudaGraphicsMapResources).
#ifdef HAVE_CUDA
        if (cuda_overlay && overlay_mode != OverlayMode::HIDDEN) {
            if (overlay_mode == OverlayMode::TOUCH_DENSITY) {
                // The density accumulator was already updated in the touch
                // drain loop above (add_touch_point calls).  Just render it.
                cuda_overlay->render_touch_density();

            } else if (overlay_mode == OverlayMode::GPU_BARS) {
                // ── Demo: animate GPU utilization bars ────────────────────
                // In production, replace this with real data from the Redfish
                // fleet manager (pykesys-redfish FleetManager.collect_inventory()
                // or a direct NVML call on the local DGX).
                //
                // The DGX H100 SXM5 has 8 H100 GPUs.  A typical training run
                // saturates all 8 to 90–100%; the animation below shows what
                // burst/idle patterns look like for debugging the visualization.
                ++gpu_util_frame;
                for (int g = 0; g < 8; ++g) {
                    // Sine wave with per-GPU phase offset, bias toward high util.
                    const float phase = static_cast<float>(g) * 0.7f;
                    const float t     = gpu_util_frame * 0.02f + phase;
                    gpu_utils[static_cast<std::size_t>(g)] =
                        60.f + 35.f * std::sin(t) + 5.f * std::sin(t * 3.f);
                }
                cuda_overlay->update_gpu_bars(gpu_utils);
            }
        }
#endif

        // Draw the frame and present it.
        renderer.draw(indicators, now);
        egl_ctx.swap_and_flip(crtc_id, conn->connector_id, &mode);
    }

    // ── Shutdown ──────────────────────────────────────────────────────────
    printf("[Main] Shutting down...\n");
    input_loop.stop();
    input_thread.join();

    printf("[Main] Done.\n");
    return EXIT_SUCCESS;
}
