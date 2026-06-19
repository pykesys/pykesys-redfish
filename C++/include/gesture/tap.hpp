// gesture/tap.hpp — single and double tap detector
//
// A tap is: finger DOWN followed by finger UP without moving more than
// TAP_MAX_MOVE (3% of screen width) within TAP_MAX_DURATION (150ms).
//
// A double-tap is two such taps within DOUBLE_TAP_WINDOW (300ms) at
// roughly the same location.  We don't check location for the second tap
// because users naturally drift a few mm between taps.
//
// The tricky part: we can't fire a single-tap callback immediately on UP,
// because we don't yet know if a second tap is coming.  Instead we set a
// pending flag and fire on the next call to flush_pending() if the window
// has elapsed.  In practice, flush_pending() should be called once per
// render frame (~16ms), giving plenty of resolution.
//
// This detector operates on the normalized coordinate space [0,1] so the
// same thresholds work on any screen size.

#pragma once
#include "../common.hpp"
#include <functional>
#include <unordered_map>
#include <utility>
#include <cmath>

class TapDetector {
public:
    struct TapEvent {
        float x, y;     // normalized position of the tap
        int   count;    // 1 = single tap, 2 = double tap
    };
    using Callback = std::function<void(const TapEvent&)>;

    explicit TapDetector(Callback cb);

    void on_touch(const TouchEvent& e);

    // Call once per frame to emit pending single-taps whose double-tap
    // window has expired.
    void flush_pending(TimePoint now);

private:
    static constexpr Millis  TAP_MAX_DURATION  {150};
    static constexpr Millis  DOUBLE_TAP_WINDOW {300};
    static constexpr float   TAP_MAX_MOVE      {0.03f}; // 3% of screen

    static float dist(std::pair<float,float> a, std::pair<float,float> b) {
        float dx = a.first - b.first, dy = a.second - b.second;
        return std::sqrt(dx*dx + dy*dy);
    }

    Callback cb_;
    std::unordered_map<int, TimePoint>               down_time_;
    std::unordered_map<int, std::pair<float,float>>  down_pos_;

    bool                      pending_tap_{false};
    TimePoint                 last_tap_time_;
    std::pair<float,float>    last_tap_pos_{};
};
