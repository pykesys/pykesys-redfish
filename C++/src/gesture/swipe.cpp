// gesture/swipe.cpp — directional swipe recognition
//
// A swipe is detected at finger-UP time by comparing the finger's final
// position to where it started.  We don't look at intermediate MOVE events —
// only the net displacement and elapsed time matter.
//
// Direction is resolved by comparing |dx| vs |dy|: whichever axis has the
// larger absolute value determines the direction.  This correctly handles
// slightly diagonal swipes that the user intended as horizontal or vertical.
//
// The active_count_ field tracks how many fingers are currently down.  The
// SwipeEvent carries this so the caller can treat a one-finger swipe as
// "scroll" and a two-finger swipe as "pan" or "workspace switch".

#include "gesture/swipe.hpp"
#include <chrono>

SwipeDetector::SwipeDetector(Callback cb) : cb_(std::move(cb)) {}

void SwipeDetector::on_touch(const TouchEvent& e) {
    if (e.type == TouchEvent::Type::DOWN) {
        start_[e.slot] = {e.x, e.y, e.time};
        ++active_count_;
        return;
    }

    if (e.type == TouchEvent::Type::MOVE) {
        // Track latest position so we could in principle use it for velocity,
        // though currently we only use the start/end pair.
        last_[e.slot] = {e.x, e.y, e.time};
        return;
    }

    if (e.type == TouchEvent::Type::UP) {
        auto it = start_.find(e.slot);
        if (it == start_.end()) {
            --active_count_;
            return;
        }

        const float dx   = e.x - it->second.x;
        const float dy   = e.y - it->second.y;
        const float dist = std::sqrt(dx * dx + dy * dy);

        using fms = std::chrono::duration<float, std::milli>;
        const float ms = fms(e.time - it->second.t).count();

        if (dist > SWIPE_MIN_DIST && ms < SWIPE_MAX_MS && ms > 0.f) {
            // Resolve dominant direction.
            Direction dir;
            if (std::abs(dx) > std::abs(dy))
                dir = (dx > 0.f) ? Direction::RIGHT : Direction::LEFT;
            else
                dir = (dy > 0.f) ? Direction::DOWN  : Direction::UP;

            // velocity in normalized-screen-units per second.
            const float velocity = dist / (ms / 1000.f);

            cb_(SwipeEvent{dir, velocity, active_count_});
        }

        start_.erase(it);
        last_.erase(e.slot);
        --active_count_;
    }
}
