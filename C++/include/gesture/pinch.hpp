// gesture/pinch.hpp — two-finger pinch-to-zoom detector
//
// Pinch is computed as the ratio of the current inter-finger distance to
// the reference distance established at pinch start.  A scale > 1.0 means
// the fingers are moving apart (zoom in); < 1.0 means approaching (zoom out).
//
// The center point is the midpoint between the two fingers — this is the
// natural zoom pivot for most UI operations.
//
// After each MOVE event that changes the distance by more than 1% (to filter
// sensor noise), we update reference_dist_ so the next event gets a delta
// relative to the CURRENT position, not the original pinch start.  This
// gives smooth continuous zoom rather than an accumulating offset.
//
// Only the two fingers present at pinch start are tracked.  If a third
// finger is added mid-pinch, the extra slot is ignored.  If either of the
// original two lifts, reference_dist_ is reset so the next valid pair
// starts fresh.
//
// Note: libinput provides built-in pinch recognition (GESTURE_PINCH_*)
// if you use the libinput path.  This manual implementation is provided
// for the raw evdev path where libinput is not in use.

#pragma once
#include "../common.hpp"
#include <functional>
#include <unordered_map>
#include <cmath>

class PinchDetector {
public:
    struct PinchEvent {
        float scale;              // > 1.0 = zoom in, < 1.0 = zoom out
        float center_x;           // pivot point (normalized)
        float center_y;
    };
    using Callback = std::function<void(const PinchEvent&)>;

    explicit PinchDetector(Callback cb);
    void on_touch(const TouchEvent& e);

private:
    struct Point { float x, y; };

    Callback cb_;
    std::unordered_map<int, Point> active_;
    float reference_dist_{-1.f};  // -1 means "not yet established"

    void try_pinch();
};
