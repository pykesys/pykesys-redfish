// renderer.hpp — OpenGL ES 3 rendering layer for the command deck UI
//
// The renderer owns all GL state.  Archaeologists: look at TouchIndicator
// first — that struct drives the majority of the visible per-finger output.

#pragma once
#include "display/egl_context.hpp"
#include "common.hpp"
#include <vector>
#include <array>
#include <cstdint>
#include <chrono>

// ── Per-slot color palette ────────────────────────────────────────────────────
//
// Each of the 10 (or 40) touch slots has a fixed, distinct color so an
// operator can identify their fingers at a glance.  Colors are chosen to be:
//   • High contrast against the dark UI background (0x0A, 0x0A, 0x14)
//   • Distinct from each other under typical data-center fluorescent lighting
//   • Saturation ≥ 80% so they are visible from a meter away
//
// Format: 0xRRGGBBAA  (R in high byte, A in low byte)
// If a device has more than 10 slots (IFP55G1: 40), colors repeat modulo 10.
inline constexpr std::array<uint32_t, 10> SLOT_COLORS = {{
    0xFF3344FF,   // slot 0 — coral red
    0xFF9900FF,   // slot 1 — amber orange
    0x55FF33FF,   // slot 2 — lime green
    0x00EEFFFF,   // slot 3 — cyan
    0x3388FFFF,   // slot 4 — sky blue
    0xBB44FFFF,   // slot 5 — violet
    0xFF44AAFF,   // slot 6 — hot pink
    0xFFDD00FF,   // slot 7 — gold
    0x00DDAAFF,   // slot 8 — teal
    0xFF8833FF,   // slot 9 — tangerine
}};

// ── Normalized rectangle ──────────────────────────────────────────────────────
struct Rect {
    float x, y, w, h;
    bool contains(float px, float py) const {
        return px >= x && px <= x + w && py >= y && py <= y + h;
    }
};

// ── Per-slot touch surface state ──────────────────────────────────────────────
//
// This struct holds everything the renderer needs to draw one finger's full
// visual representation: position, contact ellipse, pressure, comet trail,
// and ripple animation state.
//
// Trail ring buffer:
//   The last TRAIL_LEN positions are stored in a ring buffer (trail_pts[]).
//   trail_head is the index where the NEXT position will be written.
//   trail_count is how many valid positions are stored.
//   Traversal: start at (trail_head + TRAIL_LEN - 1) % TRAIL_LEN (newest),
//              go backwards TRAIL_COUNT steps.
//   Alpha fades from 1.0 (newest) to 0.0 (oldest) giving a comet-tail effect.
//
// Ripple animation:
//   When a finger first touches (DOWN), ripple_start is set to the current
//   time.  The renderer draws an expanding/fading ring for RIPPLE_DURATION_MS.
//   After the duration expires, no ring is drawn.
struct TouchIndicator {
    bool      active       = false;
    int       slot         = 0;
    float     x            = 0.f;   // current normalized position
    float     y            = 0.f;
    float     major_radius = 0.018f; // contact ellipse major (normalized screen units)
    float     minor_radius = 0.018f; // contact ellipse minor (≤ major)
    float     pressure     = 0.f;    // 0–1 normalized; drives halo brightness

    // Comet trail
    static constexpr int TRAIL_LEN = 16;
    struct TrailPt { float x, y; };
    TrailPt trail_pts[TRAIL_LEN]{};
    int trail_head  = 0;
    int trail_count = 0;

    // Ripple animation state
    TimePoint ripple_start{};
    bool      ripple_active = false;
    static constexpr int RIPPLE_DURATION_MS = 350;

    // ── Helpers ───────────────────────────────────────────────────────────

    // Resolve this slot's display color from the global palette.
    uint32_t color() const {
        return SLOT_COLORS[static_cast<std::size_t>(slot) % SLOT_COLORS.size()];
    }

    // Append the current position to the trail ring buffer.
    void push_trail() {
        trail_pts[trail_head] = {x, y};
        trail_head = (trail_head + 1) % TRAIL_LEN;
        if (trail_count < TRAIL_LEN) ++trail_count;
    }

    // Wipe the trail (called on DOWN to start fresh, and on UP to clear).
    void clear_trail() { trail_head = 0; trail_count = 0; }

    // Start a ripple burst at the current position.
    void start_ripple(TimePoint now) {
        ripple_start  = now;
        ripple_active = true;
    }

    // Fraction through the ripple animation [0.0, 1.0]; -1 if not active.
    float ripple_progress(TimePoint now) const {
        if (!ripple_active) return -1.f;
        using fms = std::chrono::duration<float, std::milli>;
        const float elapsed = fms(now - ripple_start).count();
        if (elapsed >= static_cast<float>(RIPPLE_DURATION_MS)) return -1.f;
        return elapsed / static_cast<float>(RIPPLE_DURATION_MS);
    }
};

// ── Renderer ──────────────────────────────────────────────────────────────────
class Renderer {
public:
    Renderer(EGLContext& ctx, uint32_t width, uint32_t height);
    ~Renderer();

    Renderer(const Renderer&)            = delete;
    Renderer& operator=(const Renderer&) = delete;

    // Draw one complete frame.
    // indicators: all 10 (or 40) slot states — active and inactive.
    // now: current time, used for ripple animation progress.
    void draw(const std::vector<TouchIndicator>& indicators, TimePoint now);

    // CUDA ML overlay texture update (device pointer).
    void update_ml_overlay(float* d_data);
    void set_overlay_visible(bool v) { overlay_visible_ = v; }

    uint32_t width()  const { return width_; }
    uint32_t height() const { return height_; }

    // Expose the GL texture ID so CUDAOverlay can register it.
    // Call after construction.  The texture is created in init_overlay_texture().
    uint32_t overlay_tex_id() const { return overlay_tex_; }

private:
    EGLContext& ctx_;
    uint32_t    width_, height_;
    bool        overlay_visible_{false};

    uint32_t vao_{0}, vbo_{0};
    uint32_t prog_solid_{0};
    uint32_t prog_texture_{0};
    uint32_t overlay_tex_{0};
    void*    cuda_resource_{nullptr};

    void init_shaders();
    void init_buffers();
    void init_overlay_texture();

    // Drawing primitives
    void draw_rect(const Rect& r, uint32_t color);

    // Ellipse (generalizes circle when major_r == minor_r).
    // aspect_ratio: width/height of the display, needed to avoid screen-shape
    // distortion when radius is specified in normalized units.
    void draw_ellipse(float cx, float cy,
                      float major_r, float minor_r,
                      uint32_t color, int segments = 40);

    // Fading ring used for ripple bursts and pressure halos.
    // inner_r < outer_r; alpha fades based on the ring's "age" fraction.
    void draw_ring(float cx, float cy,
                   float inner_r, float outer_r,
                   uint32_t color, float alpha,
                   int segments = 40);

    // Comet trail: draws trail_count line segments with fading alpha.
    void draw_trail(const TouchIndicator& ind);

    // Full per-finger composite: trail → halo → ellipse → ripple.
    void draw_finger(const TouchIndicator& ind, TimePoint now);

    // Active-finger count badge in the corner.
    void draw_finger_count(int count);

    void draw_overlay();
};

