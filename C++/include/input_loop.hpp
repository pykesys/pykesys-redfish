// input_loop.hpp — unified epoll event loop for all input devices
//
// A naïve approach to reading from multiple input devices would be to
// spin in a loop calling read() on each fd in turn.  That burns a full
// CPU core doing nothing 99.9% of the time and adds latency proportional
// to the number of devices.
//
// epoll is the correct Linux primitive for this.  It sleeps the thread
// in the kernel until ANY watched fd has data, then wakes it with a list
// of exactly which fds are ready.  Cost is O(1) regardless of how many
// fds are registered — you could watch 10,000 devices as cheaply as 2.
//
// This class manages the epoll instance and provides a blocking run()
// loop that dispatches events to the appropriate callbacks.  It can watch:
//   - One or more touchscreen devices (MTTracker per device)
//   - One keyboard device
//   - One libinput context (for gesture events, if preferred over raw)
//
// Threading model: run() is blocking — call it from a dedicated input
// thread.  The callbacks fire on that same thread.  If you use the SPSC
// event bus (event_bus.hpp), push events in the callbacks and consume them
// on the render thread.  Never call OpenGL from the input thread.

#pragma once
#include "common.hpp"
#include "touch_device.hpp"
#include "mt_tracker.hpp"
#include <string>
#include <memory>
#include <vector>
#include <atomic>

struct InputSource {
    std::unique_ptr<TouchDevice> device;
    std::unique_ptr<MTTracker>   tracker;
};

class InputLoop {
public:
    // Add a touchscreen by device path (e.g. "/dev/input/event4").
    // Can be called multiple times before run() to watch several screens
    // simultaneously — useful if you have both a TD2423D and an IFP55G1.
    void add_touch(const std::string& path);

    // Add the keyboard device path.
    // Only one keyboard is supported; call this once.
    void add_keyboard(const std::string& path);

    // Block until stop() is called, dispatching touch and key events.
    // touch_cb and key_cb are called from this thread on every event.
    void run(const TouchCallback& touch_cb, const KeyCallback& key_cb);

    // Signal run() to exit on the next epoll_wait() timeout (within 100ms).
    // Safe to call from any thread.
    void stop() { running_.store(false, std::memory_order_relaxed); }

    ~InputLoop();

private:
    int epfd_{-1};

    // Touch sources — each screen gets its own device + tracker pair.
    std::vector<InputSource> touch_sources_;

    // Keyboard — plain libevdev read, no tracker needed.
    struct libevdev* kbd_dev_{nullptr};
    int              kbd_fd_{-1};

    std::atomic<bool> running_{false};

    void init_epoll();
    void add_fd(int fd, uint64_t tag);
    void drain_touch(InputSource& src, const TouchCallback& cb);
    void drain_keyboard(const KeyCallback& cb);
};
