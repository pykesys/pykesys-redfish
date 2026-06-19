// touch_device.hpp — opens a /dev/input/eventN node and interrogates it
//
// On Linux, every input peripheral (touchscreen, keyboard, mouse, joystick)
// appears as a character device under /dev/input/.  Reading from it gives
// a stream of struct input_event packets.
//
// Surface data axes — not all controllers report all of these.
// Call has_abs() before using normalize_abs() for optional axes.
//
//   ABS_MT_POSITION_X/Y   — finger position        (always present)
//   ABS_MT_TOUCH_MAJOR    — contact ellipse major   (TD2423D: present; IFP55G1: present)
//   ABS_MT_TOUCH_MINOR    — contact ellipse minor   (may be absent; some report only MAJOR)
//   ABS_MT_PRESSURE       — contact force 0–255     (PCAP panels: often a constant or derived from area)
//   ABS_MT_ORIENTATION    — ellipse rotation deg    (rare; some stylus-capable panels)
//   ABS_MT_DISTANCE       — hover distance mm       (rare; stylus hover)
//
// TD2423D (PCAP): POSITION_X/Y + TOUCH_MAJOR confirmed.
//   PRESSURE may be present but often constant on PCAP (not a true force sensor).
// IFP55G1 (IR):   POSITION_X/Y + TOUCH_MAJOR.
//   IR panels derive contact size from beam occlusion width; no true pressure.

#pragma once
#include <libevdev/libevdev.h>
#include <linux/input.h>
#include <string>
#include <stdexcept>
#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <unistd.h>

class TouchDevice {
public:
    explicit TouchDevice(const std::string& path) {
        // O_NONBLOCK is essential: without it, read() blocks until the next
        // event arrives.  With it, libevdev_next_event() returns -EAGAIN
        // when the queue is empty, which is what we want in an epoll loop.
        fd_ = open(path.c_str(), O_RDONLY | O_NONBLOCK);
        if (fd_ < 0)
            throw std::runtime_error("Cannot open " + path + ": " + strerror(errno));

        int rc = libevdev_new_from_fd(fd_, &dev_);
        if (rc < 0)
            throw std::runtime_error("libevdev_new_from_fd failed: " + std::string(strerror(-rc)));

        // Sanity check: confirm this device reports ABS_MT_POSITION_X.
        // A keyboard will open fine but has no ABS axes; we'd get garbage.
        if (!libevdev_has_event_code(dev_, EV_ABS, ABS_MT_POSITION_X))
            throw std::runtime_error(path + " is not a multi-touch device (no ABS_MT_POSITION_X)");

        // The kernel reports touch positions as raw ADC integers.
        // Their range (min/max) varies by controller — common values are
        // 0–32767, 0–4095, or the actual pixel dimensions.
        // We store min/max here so normalize_x/y can produce [0,1] floats.
        const auto* ax = libevdev_get_abs_info(dev_, ABS_MT_POSITION_X);
        const auto* ay = libevdev_get_abs_info(dev_, ABS_MT_POSITION_Y);
        x_min_ = ax->minimum;  x_max_ = ax->maximum;
        y_min_ = ay->minimum;  y_max_ = ay->maximum;

        // max_slots_ tells us how many simultaneous fingers this controller
        // can track.  TD2423D = 10, IFP55G1 = 40.
        max_slots_ = libevdev_get_abs_maximum(dev_, ABS_MT_SLOT) + 1;
    }

    ~TouchDevice() {
        if (dev_) libevdev_free(dev_);
        if (fd_ >= 0) close(fd_);
    }

    // Non-copyable — the fd and libevdev handle are owned resources.
    TouchDevice(const TouchDevice&)            = delete;
    TouchDevice& operator=(const TouchDevice&) = delete;

    int         fd()        const { return fd_; }
    libevdev*   dev()       const { return dev_; }
    int         max_slots() const { return max_slots_; }

    // Check whether the device reports a given absolute axis.
    // Always call this before normalize_abs() for optional axes like
    // ABS_MT_TOUCH_MAJOR or ABS_MT_PRESSURE — not all controllers send them.
    bool has_abs(int abs_code) const {
        return libevdev_has_event_code(dev_, EV_ABS, abs_code);
    }

    // Generic normalizer for any ABS axis: maps raw ADC value to [0.0, 1.0].
    // Returns 0.0 if the axis has zero range (max == min) or doesn't exist.
    float normalize_abs(int abs_code, int raw) const {
        const auto* info = libevdev_get_abs_info(dev_, abs_code);
        if (!info || info->maximum == info->minimum) return 0.f;
        return static_cast<float>(raw - info->minimum)
             / static_cast<float>(info->maximum - info->minimum);
    }

    // Convenience wrappers for the most-used axes.
    float normalize_x(int raw) const { return normalize_abs(ABS_MT_POSITION_X, raw); }
    float normalize_y(int raw) const { return normalize_abs(ABS_MT_POSITION_Y, raw); }

    // Convert normalized coords to screen pixels given a viewport size.
    int to_px_x(float norm, int screen_w) const { return static_cast<int>(norm * screen_w); }
    int to_px_y(float norm, int screen_h) const { return static_cast<int>(norm * screen_h); }

private:
    int       fd_{-1};
    libevdev* dev_{nullptr};
    int       x_min_{0}, x_max_{1};
    int       y_min_{0}, y_max_{1};
    int       max_slots_{10};
};
