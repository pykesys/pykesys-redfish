// common.hpp — shared types for the CommandDeck input pipeline
//
// This header is the Rosetta Stone of the input system.  Every other
// module speaks these types, so archaeologists should start here.
//
// The design philosophy: raw kernel events (struct input_event) are
// fine-grained and stateful — you have to track slot/tracking-id state
// across many events to understand a single finger touch.  We convert
// that stream into discrete, self-contained TouchEvent / KeyEvent
// structs at the earliest possible moment so that all downstream code
// (gestures, renderer, UI) can work with clean data.
//
// Coordinate convention throughout this codebase:
//   raw  — ADC integers, device-specific range (e.g. 0–32767)
//   norm — float in [0.0, 1.0], independent of device resolution
//   px   — integer pixels, dependent on current display resolution
//
// All times use std::chrono::steady_clock — monotonic, immune to NTP
// jumps, suitable for duration arithmetic.  Wall-clock time is only
// used when we need to stamp UI labels or log messages.

#pragma once
#include <chrono>
#include <functional>

// ── Time alias ────────────────────────────────────────────────────────────────
using TimePoint = std::chrono::steady_clock::time_point;
using Millis    = std::chrono::milliseconds;

// ── Per-slot state: one instance tracks one finger across its lifetime ────────
//
// The Linux MT Type B protocol uses "slots" as persistent finger buckets.
// Slot 0 may contain finger A right now and finger B five seconds later —
// the ABS_MT_TRACKING_ID distinguishes them.  A tracking_id of -1 means
// the slot is empty (no finger).
//
// We store BOTH raw ADC coordinates and normalized [0,1] floats.
// Raw values are kept for debugging; normalized values are used everywhere else.
//
// Contact geometry (TOUCH_MAJOR/MINOR, PRESSURE):
//   These give the *physical footprint* of the touch, not just its centre.
//   A finger laid flat has a large MAJOR axis (25–40mm) and a round ellipse.
//   A fingertip pressing lightly has a small, nearly circular contact.
//   A stylus or pen tip has a tiny, highly elongated contact.
//   Values are normalized to [0,1] using the controller's reported axis range.
//   If the controller doesn't report a given axis, the value stays 0.
struct TouchSlot {
    int   tracking_id     = -1;   // -1 = empty; ≥0 = active finger ID
    int   raw_x           = 0;    // ADC value from kernel
    int   raw_y           = 0;
    float x               = 0.f;  // normalized position [0,1]
    float y               = 0.f;
    // Contact geometry — normalized [0,1], 0 if axis not supported by device.
    float touch_major     = 0.f;  // major axis of contact ellipse
    float touch_minor     = 0.f;  // minor axis (0 if only MAJOR is reported)
    float pressure        = 0.f;  // contact pressure / force estimate
    bool  active() const { return tracking_id >= 0; }
};

// ── Touch events: what the InputLoop delivers to the rest of the world ────────
//
// Three lifecycle events per finger: DOWN when it first touches the glass,
// MOVE every time it slides, UP when it lifts.  All positions are normalized.
//
// Contact geometry is carried through here too so that gesture recognizers
// and the renderer receive the complete picture of each touch contact —
// not just where the finger is, but how large it is and how hard it's pressing.
// This enables:
//   - Rendering ellipses instead of circles (more accurate finger shape)
//   - Palm rejection (palms have very large TOUCH_MAJOR values)
//   - Pressure-sensitive UI feedback (highlight color, stroke width)
struct TouchEvent {
    enum class Type { DOWN, MOVE, UP };

    Type       type;
    int        slot;           // slot index (0-based), stable for finger lifetime
    int        tracking_id;    // unique per-finger per-session
    float      x, y;           // normalized screen position [0,1]
    float      touch_major;    // normalized contact ellipse major axis [0,1]
    float      touch_minor;    // normalized contact ellipse minor axis [0,1]
    float      pressure;       // normalized pressure [0,1] (0 if unsupported)
    TimePoint  time;
};

// ── Keyboard events ───────────────────────────────────────────────────────────
//
// Raw Linux key events: code is the KEY_* constant (KEY_A, KEY_ENTER, etc.),
// value is 1=press, 0=release, 2=autorepeat.
// See: /usr/include/linux/input-event-codes.h
struct KeyEvent {
    int        code;    // KEY_* constant
    int        value;   // 1=down, 0=up, 2=repeat
    TimePoint  time;
};

// ── Callbacks: what callers register to receive events ───────────────────────
using TouchCallback = std::function<void(const TouchEvent&)>;
using KeyCallback   = std::function<void(const KeyEvent&)>;
