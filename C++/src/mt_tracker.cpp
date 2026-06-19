// mt_tracker.cpp — Linux MT Type B protocol state machine implementation
//
// If you're reading this without the header, start with mt_tracker.hpp
// for the protocol background.  This file is the engine that converts
// a raw stream of input_events into discrete TouchEvents.
//
// The state machine has four bookkeeping concerns:
//   1. current_slot_ — which slot the next ABS_MT_* event applies to
//   2. slots_[]      — per-slot position and tracking-id state
//   3. pending_*     — events accumulated within one SYN frame
//   4. flush_frame() — fire callbacks when the frame is complete

#include "mt_tracker.hpp"
#include <chrono>
#include <algorithm>

MTTracker::MTTracker(int max_slots)
    : slots_(static_cast<std::size_t>(max_slots))
    , current_slot_(0)
{}

int MTTracker::active_count() const {
    int n = 0;
    for (const auto& s : slots_) if (s.active()) ++n;
    return n;
}

void MTTracker::process(const struct input_event& ev,
                        const TouchDevice&        dev,
                        const TouchCallback&      cb)
{
    // EV_SYN / SYN_REPORT: end of one complete event frame.
    // Fire callbacks for everything accumulated since the last SYN_REPORT.
    if (ev.type == EV_SYN && ev.code == SYN_REPORT) {
        flush_frame(cb);
        return;
    }

    // We only care about absolute axis events.
    // EV_KEY (BTN_TOUCH) is present but redundant with tracking-id changes.
    if (ev.type != EV_ABS) return;

    switch (ev.code) {

    case ABS_MT_SLOT:
        // Switch the "current slot" context.  All subsequent ABS_MT_* events
        // apply to this slot until another ABS_MT_SLOT arrives.
        // Clamp to avoid out-of-bounds if a buggy driver sends a slot index
        // we didn't size for.
        current_slot_ = std::min(ev.value,
                                 static_cast<int>(slots_.size()) - 1);
        break;

    case ABS_MT_TRACKING_ID: {
        auto& slot = slots_[current_slot_];
        if (ev.value >= 0) {
            // Positive tracking-id: a new finger has landed on this slot.
            // We only record DOWN if the slot was previously empty —
            // some controllers re-send the tracking-id during a drag, and
            // we don't want a spurious DOWN in the middle of a swipe.
            if (!slot.active()) {
                slot.tracking_id = ev.value;
                pending_downs_.push_back(current_slot_);
            } else {
                slot.tracking_id = ev.value;  // update ID, no DOWN event
            }
        } else {
            // Tracking-id of -1: finger lifted.  Schedule an UP event.
            if (slot.active())
                pending_ups_.push_back(current_slot_);
            slot.tracking_id = -1;  // mark slot empty
        }
        break;
    }

    case ABS_MT_POSITION_X:
        slots_[current_slot_].raw_x = ev.value;
        slots_[current_slot_].x     = dev.normalize_x(ev.value);
        if (slots_[current_slot_].active())
            pending_moves_.insert(current_slot_);
        break;

    case ABS_MT_POSITION_Y:
        slots_[current_slot_].raw_y = ev.value;
        slots_[current_slot_].y     = dev.normalize_y(ev.value);
        if (slots_[current_slot_].active())
            pending_moves_.insert(current_slot_);
        break;

    // ── Contact geometry — the shape of the touch, not just the centre ────
    //
    // ABS_MT_TOUCH_MAJOR: major axis of the contact ellipse.
    // A resting fingertip is roughly circular with MAJOR ≈ 0.15–0.25 norm.
    // A flat palm has MAJOR > 0.40 — that's the palm-rejection threshold.
    // A stylus or pen nib has MAJOR < 0.05 — nearly a point contact.
    case ABS_MT_TOUCH_MAJOR:
        if (dev.has_abs(ABS_MT_TOUCH_MAJOR))
            slots_[current_slot_].touch_major =
                dev.normalize_abs(ABS_MT_TOUCH_MAJOR, ev.value);
        break;

    // ABS_MT_TOUCH_MINOR: minor axis.
    // Equal to MAJOR for a round contact; much smaller for a stylus or
    // edge-of-finger.  Many controllers only report MAJOR — MINOR stays 0.
    case ABS_MT_TOUCH_MINOR:
        if (dev.has_abs(ABS_MT_TOUCH_MINOR))
            slots_[current_slot_].touch_minor =
                dev.normalize_abs(ABS_MT_TOUCH_MINOR, ev.value);
        break;

    // ABS_MT_PRESSURE: signal strength / force estimate.
    // On PCAP (TD2423D): derived from capacitive area, not true force.
    // May be constant, weakly varying, or absent.  Treat as a visual hint,
    // not a reliable force measurement.
    case ABS_MT_PRESSURE:
        if (dev.has_abs(ABS_MT_PRESSURE))
            slots_[current_slot_].pressure =
                dev.normalize_abs(ABS_MT_PRESSURE, ev.value);
        break;
    default:
        break;
    }
}

void MTTracker::flush_frame(const TouchCallback& cb)
{
    const auto now = std::chrono::steady_clock::now();

    // Fire DOWNs first so gesture recognizers see the finger arrive before
    // any MOVE on the same frame (can happen when the controller sends a
    // new tracking-id and position update in a single SYN frame).
    for (int s : pending_downs_) {
        cb(TouchEvent{
            .type        = TouchEvent::Type::DOWN,
            .slot        = s,
            .tracking_id = slots_[s].tracking_id,
            .x           = slots_[s].x,
            .y           = slots_[s].y,
            .touch_major = slots_[s].touch_major,
            .touch_minor = slots_[s].touch_minor,
            .pressure    = slots_[s].pressure,
            .time        = now,
        });
    }

    for (int s : pending_moves_) {
        if (!slots_[s].active()) continue;
        cb(TouchEvent{
            .type        = TouchEvent::Type::MOVE,
            .slot        = s,
            .tracking_id = slots_[s].tracking_id,
            .x           = slots_[s].x,
            .y           = slots_[s].y,
            .touch_major = slots_[s].touch_major,
            .touch_minor = slots_[s].touch_minor,
            .pressure    = slots_[s].pressure,
            .time        = now,
        });
    }

    // UPs last: gesture recognizers need the final position.
    // Note: slots_[s].tracking_id is already -1 here; the last known
    // position is still valid in x/y.
    for (int s : pending_ups_) {
        cb(TouchEvent{
            .type        = TouchEvent::Type::UP,
            .slot        = s,
            .tracking_id = -1,
            .x           = slots_[s].x,
            .y           = slots_[s].y,
            .time        = now,
        });
    }

    pending_downs_.clear();
    pending_ups_.clear();
    pending_moves_.clear();
}
