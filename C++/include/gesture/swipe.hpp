// gesture/swipe.hpp — directional swipe detector
//
// A swipe is: a finger (or fingers) moving in one dominant direction,
// fast enough (SWIPE_MIN_DIST covered in SWIPE_MAX_MS), without changing
// direction significantly.
//
// "Dominant direction" means |dx| > |dy| for horizontal swipes and vice
// versa.  We don't try to detect diagonal swipes because they are rarely
// intentional on a touchscreen command interface.
//
// The finger_count in SwipeEvent tells you how many fingers were down
// when the swipe completed.  Two-finger swipes are commonly used for
// scroll or pan; three-finger for workspace switching.
//
// Implementation note: we record the DOWN position per slot, then on UP
// we measure displacement and elapsed time.  We don't need intermediate
// MOVE events — only the start and end matter for swipe classification.

#pragma once
#include "../common.hpp"
#include <functional>
#include <unordered_map>
#include <cmath>

class SwipeDetector {
public:
    enum class Direction { LEFT, RIGHT, UP, DOWN };

    struct SwipeEvent {
        Direction dir;
        float     velocity;       // normalized screen units per second
        int       finger_count;   // how many fingers were active
    };
    using Callback = std::function<void(const SwipeEvent&)>;

    explicit SwipeDetector(Callback cb);
    void on_touch(const TouchEvent& e);

private:
    static constexpr float SWIPE_MIN_DIST {0.15f};   // 15% of screen
    static constexpr float SWIPE_MAX_MS   {500.f};   // must complete in 500ms

    struct PosTime { float x, y; TimePoint t; };

    Callback cb_;
    std::unordered_map<int, PosTime> start_;
    std::unordered_map<int, PosTime> last_;
    int active_count_{0};
};
