// mt_tracker.hpp — Linux MT Type B protocol state machine
//
// The Linux multi-touch Type B protocol is a slot-based incremental
// update protocol.  Understanding it is essential for anyone reading
// this code.  The short version:
//
//   The kernel sends ONLY what changed, not the full state.
//   Before you can understand any individual event, you must maintain
//   the current slot context and per-slot state across many events.
//
// A typical two-finger touch sequence looks like this in the event stream:
//
//   EV_ABS ABS_MT_SLOT         0       ← "I'm about to describe slot 0"
//   EV_ABS ABS_MT_TRACKING_ID  42      ← "a new finger arrived, ID=42"
//   EV_ABS ABS_MT_POSITION_X   15000
//   EV_ABS ABS_MT_POSITION_Y   8000
//   EV_ABS ABS_MT_SLOT         1       ← "now describing slot 1"
//   EV_ABS ABS_MT_TRACKING_ID  43      ← "another new finger, ID=43"
//   EV_ABS ABS_MT_POSITION_X   20000
//   EV_ABS ABS_MT_POSITION_Y   12000
//   EV_SYN SYN_REPORT           0      ← "that's the complete frame"
//
// MTTracker accumulates these deltas into a vector of TouchSlot structs,
// then fires TouchEvent callbacks on SYN_REPORT.
//
// The Type A (legacy) protocol is different and NOT handled here.
// Type A sends a SYN_MT_REPORT between each contact description and
// doesn't use tracking IDs.  If you have an old resistive touchscreen
// that uses Type A, you'll need a different tracker.

#pragma once
#include "common.hpp"
#include "touch_device.hpp"
#include <vector>
#include <set>
#include <linux/input.h>

class MTTracker {
public:
    // max_slots: must match the device's ABS_MT_SLOT maximum.
    // Passing a larger value wastes a little memory; passing a smaller
    // value will silently clamp slot indices and corrupt tracking.
    explicit MTTracker(int max_slots);

    // Feed every struct input_event from the device fd here, in order.
    // On SYN_REPORT, all accumulated changes are fired as TouchEvents
    // via the callback.  Other events update internal state silently.
    void process(const struct input_event& ev,
                 const TouchDevice&        dev,
                 const TouchCallback&      cb);

    // Read-only view of the current per-slot state.
    // Useful for gesture recognizers that need to examine ALL active
    // fingers at once rather than responding event by event.
    const std::vector<TouchSlot>& slots() const { return slots_; }

    // Number of fingers currently touching the screen.
    int active_count() const;

private:
    std::vector<TouchSlot> slots_;
    int                    current_slot_{0};

    // Pending events accumulated within the current SYN frame.
    // We batch them so that DOWN, MOVE, and UP fire in a predictable
    // order (DOWN first, MOVE middle, UP last) even if the kernel
    // sends them interleaved within a single SYN frame.
    std::vector<int> pending_downs_;
    std::vector<int> pending_ups_;
    std::set<int>    pending_moves_;

    void flush_frame(const TouchCallback& cb);
};
