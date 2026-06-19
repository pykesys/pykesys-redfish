// gesture/pinch.cpp — two-finger pinch-to-zoom
//
// Pinch scale is the ratio of the current inter-finger distance to the
// reference distance.  We update reference_dist_ after each MOVE so the
// callback receives incremental deltas (e.g. 1.02, 1.01, 0.99) rather than
// one large ratio at the end.  This lets the UI update smoothly while the
// user is actively pinching.
//
// We discard changes smaller than 1% (0.01 scale delta) to absorb sensor
// noise — a 24" screen has ~2–3mm of jitter at the touch controller's ADC
// resolution, which translates to fractional percent scale changes per frame.
//
// When either finger lifts (UP event), reference_dist_ is reset to -1.
// If the user immediately places a new finger, the next MOVE will re-establish
// a fresh reference rather than accumulating from the old starting distance.

#include "gesture/pinch.hpp"

PinchDetector::PinchDetector(Callback cb) : cb_(std::move(cb)) {}

void PinchDetector::on_touch(const TouchEvent& e) {
    if (e.type == TouchEvent::Type::DOWN) {
        active_[e.slot] = {e.x, e.y};
        return;
    }

    if (e.type == TouchEvent::Type::MOVE) {
        if (active_.count(e.slot)) {
            active_[e.slot] = {e.x, e.y};
            try_pinch();
        }
        return;
    }

    if (e.type == TouchEvent::Type::UP) {
        active_.erase(e.slot);
        // Reset reference so the next pinch starts fresh.
        reference_dist_ = -1.f;
    }
}

void PinchDetector::try_pinch() {
    // Need exactly two active fingers to compute a meaningful scale.
    if (active_.size() < 2) return;

    auto it      = active_.begin();
    const Point& a = it->second;
    const Point& b = (++it)->second;

    const float dx   = a.x - b.x;
    const float dy   = a.y - b.y;
    const float dist = std::sqrt(dx * dx + dy * dy);

    if (reference_dist_ < 0.f) {
        // First MOVE with two fingers — establish reference, don't fire yet.
        reference_dist_ = dist;
        return;
    }

    if (reference_dist_ < 1e-6f) return;  // avoid division by zero

    const float scale = dist / reference_dist_;

    // Filter out sub-1% changes to suppress sensor noise.
    if (std::abs(scale - 1.f) > 0.01f) {
        reference_dist_ = dist;  // rolling update for smooth incremental output

        cb_(PinchEvent{
            .scale    = scale,
            .center_x = (a.x + b.x) * 0.5f,
            .center_y = (a.y + b.y) * 0.5f,
        });
    }
}
