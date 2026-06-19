// gesture/tap.cpp — single and double tap recognition
//
// A tap is a brief press-and-release that doesn't travel far.
// The challenge is distinguishing single from double tap without
// waiting forever.  We use a two-phase approach:
//
//   Phase 1 (on UP): if it looks like a tap, set pending_tap_ = true
//                    and remember position + time.
//   Phase 2 (on flush_pending): if the double-tap window has expired
//                    without a second tap arriving, fire SINGLE.
//                    If a second tap arrives within the window, fire DOUBLE
//                    immediately and clear pending.
//
// This gives users up to DOUBLE_TAP_WINDOW (300ms) to produce a double tap.
// Single-tap latency is at most DOUBLE_TAP_WINDOW — acceptable for most UIs.
// If you need instant single-tap response, reduce the window or eliminate
// double-tap support.

#include "gesture/tap.hpp"

TapDetector::TapDetector(Callback cb) : cb_(std::move(cb)) {}

void TapDetector::on_touch(const TouchEvent& e) {
    if (e.type == TouchEvent::Type::DOWN) {
        // Record where and when the finger landed.
        down_time_[e.slot] = e.time;
        down_pos_[e.slot]  = {e.x, e.y};
        return;
    }

    if (e.type != TouchEvent::Type::UP) return;

    auto time_it = down_time_.find(e.slot);
    if (time_it == down_time_.end()) return;  // no matching DOWN, ignore

    const auto duration = e.time - time_it->second;
    const auto& pos     = down_pos_[e.slot];

    // Classify as a tap only if:
    //   (a) the press was short (not a long-press / hold)
    //   (b) the finger didn't travel (not a swipe)
    const bool short_press = duration <= TAP_MAX_DURATION;
    const bool small_move  = dist(pos, {e.x, e.y}) < TAP_MAX_MOVE;

    if (short_press && small_move) {
        if (pending_tap_) {
            // A second tap arrived within the double-tap window — fire DOUBLE.
            cb_(TapEvent{pos.first, pos.second, 2});
            pending_tap_ = false;
        } else {
            // First tap — wait for a possible second.
            pending_tap_    = true;
            last_tap_pos_   = pos;
            last_tap_time_  = e.time;
        }
    }

    // Clean up tracking state for this slot.
    down_time_.erase(time_it);
    down_pos_.erase(e.slot);
}

void TapDetector::flush_pending(TimePoint now) {
    if (!pending_tap_) return;

    // If DOUBLE_TAP_WINDOW has elapsed without a second tap, emit SINGLE.
    if ((now - last_tap_time_) >= DOUBLE_TAP_WINDOW) {
        cb_(TapEvent{last_tap_pos_.first, last_tap_pos_.second, 1});
        pending_tap_ = false;
    }
    // Otherwise, keep waiting — the window hasn't expired yet.
}
