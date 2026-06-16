# Touchscreen Programming on Linux — ViewSonic TD2423D C++ Tutorial

A complete guide to building a C++ command-deck application for the ViewSonic TD2423D 24" projected-capacitive touchscreen display on Linux, covering the full input stack, display output, DDC/CI control, CUDA/OpenGL interop, and multi-touch gesture recognition.

---


[↑ Back to Top](#table-of-contents)

## Table of Contents

- [1. Hardware Overview — ViewSonic TD2423D](#1-hardware-overview--viewsonic-td2423d)
- [2. Linux Input Stack Architecture](#2-linux-input-stack-architecture)
- [3. Device Discovery and Setup](#3-device-discovery-and-setup)
- [4. Raw evdev Programming in C++](#4-raw-evdev-programming-in-c)
  - [4.1 Opening the device](#41-opening-the-device)
  - [4.2 Reading multi-touch events](#42-reading-multi-touch-events)
  - [4.3 Type B (slot-based) protocol implementation](#43-type-b-slot-based-protocol-implementation)
  - [4.4 Coordinate normalization](#44-coordinate-normalization)
- [5. libinput in C++](#5-libinput-in-c)
  - [5.1 Context setup](#51-context-setup)
  - [5.2 Touch event handling](#52-touch-event-handling)
  - [5.3 Gesture events](#53-gesture-events)
  - [5.4 Calibration matrix](#54-calibration-matrix)
- [6. Keyboard Input](#6-keyboard-input)
- [7. Unified Input Loop with epoll](#7-unified-input-loop-with-epoll)
- [8. Multi-Touch Gesture Recognition](#8-multi-touch-gesture-recognition)
  - [8.1 Tap detection](#81-tap-detection)
  - [8.2 Swipe detection](#82-swipe-detection)
  - [8.3 Pinch-to-zoom](#83-pinch-to-zoom)
- [9. Display Output — DRM/KMS](#9-display-output--drmkms)
  - [9.1 Opening the DRM device](#91-opening-the-drm-device)
  - [9.2 Mode setting](#92-mode-setting)
  - [9.3 Framebuffer rendering loop](#93-framebuffer-rendering-loop)
- [10. OpenGL / EGL on DRM/KMS](#10-opengl--egl-on-drmkms)
  - [10.1 EGL setup with GBM](#101-egl-setup-with-gbm)
  - [10.2 Rendering to screen](#102-rendering-to-screen)
- [11. SDL2 as a Higher-Level Alternative](#11-sdl2-as-a-higher-level-alternative)
- [12. DDC/CI Display Control](#12-ddcci-display-control)
  - [12.1 Using ddcutil C library](#121-using-ddcutil-c-library)
  - [12.2 Raw i2c-dev access](#122-raw-i2c-dev-access)
- [13. CUDA / OpenGL Interop](#13-cuda--opengl-interop)
  - [13.1 CUDA → OpenGL texture pipeline](#131-cuda--opengl-texture-pipeline)
  - [13.2 Vulkan / CUDA interop](#132-vulkan--cuda-interop)
- [14. Application Architecture — Command Deck](#14-application-architecture--command-deck)
- [15. udev Rules and Permissions](#15-udev-rules-and-permissions)
- [16. Calibration and Coordinate Mapping](#16-calibration-and-coordinate-mapping)
- [17. CMake Build System](#17-cmake-build-system)
- [18. Troubleshooting](#18-troubleshooting)
- [Appendix A — Acronym Glossary](#appendix-a--acronym-glossary)
- [Appendix B — Software, Drivers & Reference Links](#appendix-b--software-drivers--reference-links)

---


[↑ Back to Top](#table-of-contents)

## 1. Hardware Overview — ViewSonic TD2423D

The TD2423D is a 24-inch FHD industrial-grade touchscreen monitor designed for kiosk and control-panel applications.

### Key specifications

| Property | Value |
|----------|-------|
| Panel | 24" IPS |
| Resolution | 1920 × 1080 (FHD) |
| Touch technology | 10-point projected capacitive (PCAP) |
| Touch interface | USB 2.0 (upstream) |
| Video inputs | HDMI 1.4, DisplayPort 1.2, VGA |
| USB VID:PID (touch) | `0x0543:0x9881` (ViewSonic) |
| Linux kernel driver | `hid-multitouch` (in-tree, no install needed) |
| Touch area | ~527 × 296 mm |
| Response time | <25 ms touch latency |
| OS support | Linux kernel 3.2+ (HID-MT class driver) |

### How it appears on Linux

When connected via USB the touch controller enumerates as a USB HID device. The `hid-multitouch` kernel module handles it automatically. You will see:

```
Bus 003 Device 004: ID 0543:9881 ViewSonic Corp.
```

It creates two `/dev/input/event*` nodes:
- One for the pointer/touch surface (ABS axes, BTN_TOUCH)
- One for function keys on the bezel (if any)

The video signal arrives separately over HDMI/DP and appears as a standard DRM/KMS connector — the display and touch are logically separate subsystems that you marry in software.

---


[↑ Back to Top](#table-of-contents)

## 2. Linux Input Stack Architecture

```
TouchSensor (hardware)
    │  USB HID report
    ▼
usbhid  ──►  hid-multitouch         kernel drivers
                    │  struct input_dev
                    ▼
            Linux Input Subsystem
            (drivers/input/input.c)
                    │
          ┌─────────┴──────────┐
          ▼                    ▼
   /dev/input/eventX     evdev kernel interface
          │
     ┌────┴────────────────────────┐
     │                             │
     ▼                             ▼
  libevdev (thin wrapper)     libinput (policy layer)
     │                             │
     ▼                             ▼
Your C++ app (raw)        Your C++ app (high-level)
                                   │
                    X11 / Wayland / DRM compositor
```

### evdev multi-touch protocols

The kernel exposes two MT protocols:

**Type A** (legacy): No tracking, sends raw contact packets per `SYN_MT_REPORT`. Each sync frame lists all current contacts. Older controllers use this.

**Type B** (slot-based, modern): Uses per-slot state. Each slot tracks one finger. A `ABS_MT_TRACKING_ID >= 0` means a new contact; `-1` means finger lifted. The TD2423D uses **Type B**.

Key event codes for Type B:

| Code | Description |
|------|-------------|
| `EV_ABS / ABS_MT_SLOT` | Switch to slot N (0–9 for 10-touch) |
| `EV_ABS / ABS_MT_TRACKING_ID` | Contact ID (≥0 = down, -1 = lifted) |
| `EV_ABS / ABS_MT_POSITION_X` | X coordinate (raw ADC units) |
| `EV_ABS / ABS_MT_POSITION_Y` | Y coordinate (raw ADC units) |
| `EV_ABS / ABS_MT_TOUCH_MAJOR` | Contact ellipse major axis |
| `EV_ABS / ABS_MT_PRESSURE` | Pressure (if supported) |
| `EV_SYN / SYN_REPORT` | End of event frame — process accumulated state |

---


[↑ Back to Top](#table-of-contents)

## 3. Device Discovery and Setup

### Find the touch device

```bash
# List all input devices with capabilities
cat /proc/bus/input/devices

# Or use evtest (installs with evtest package)
sudo evtest

# Find by USB ID
ls -la /dev/input/by-id/ | grep -i viewsonic

# Check what driver is bound
udevadm info --name=/dev/input/event4 --attribute-walk | grep -i hid
```

### Verify multi-touch capabilities

```bash
# Show ABS axes and their ranges
evemu-describe /dev/input/event4
# or
cat /sys/class/input/event4/device/capabilities/abs
```

You should see `ABS_MT_SLOT`, `ABS_MT_TRACKING_ID`, `ABS_MT_POSITION_X/Y` listed.

### Permissions

By default `/dev/input/event*` requires root or membership in the `input` group:

```bash
sudo usermod -aG input $USER
# Re-login for it to take effect

# Verify
ls -la /dev/input/event4
# crw-rw---- 1 root input 13, 68 ...
```

---


[↑ Back to Top](#table-of-contents)

## 4. Raw evdev Programming in C++

This approach gives the lowest latency and full control over event processing.

### Dependencies

```bash
# Ubuntu/Debian
sudo apt-get install libevdev-dev linux-headers-generic

# Fedora/RHEL
sudo dnf install libevdev-devel kernel-headers
```

### 4.1 Opening the device

```cpp
// touch_device.hpp
#pragma once
#include <libevdev/libevdev.h>
#include <string>
#include <stdexcept>

class TouchDevice {
public:
    explicit TouchDevice(const std::string& path) {
        fd_ = open(path.c_str(), O_RDONLY | O_NONBLOCK);
        if (fd_ < 0)
            throw std::runtime_error("Cannot open " + path + ": " + strerror(errno));

        int rc = libevdev_new_from_fd(fd_, &dev_);
        if (rc < 0)
            throw std::runtime_error("libevdev_new_from_fd failed: " + std::string(strerror(-rc)));

        // Verify this is a multi-touch device
        if (!libevdev_has_event_code(dev_, EV_ABS, ABS_MT_POSITION_X))
            throw std::runtime_error(path + " is not a multi-touch device");

        // Read axis ranges for normalization
        const struct input_absinfo* abs_x = libevdev_get_abs_info(dev_, ABS_MT_POSITION_X);
        const struct input_absinfo* abs_y = libevdev_get_abs_info(dev_, ABS_MT_POSITION_Y);
        x_min_ = abs_x->minimum; x_max_ = abs_x->maximum;
        y_min_ = abs_y->minimum; y_max_ = abs_y->maximum;

        max_slots_ = libevdev_get_abs_maximum(dev_, ABS_MT_SLOT) + 1;
    }

    ~TouchDevice() {
        libevdev_free(dev_);
        close(fd_);
    }

    int fd() const { return fd_; }
    libevdev* dev() const { return dev_; }
    int x_min() const { return x_min_; }
    int x_max() const { return x_max_; }
    int y_min() const { return y_min_; }
    int y_max() const { return y_max_; }
    int max_slots() const { return max_slots_; }

    // Normalize raw coordinates to [0.0, 1.0]
    float normalize_x(int raw) const {
        return (float)(raw - x_min_) / (float)(x_max_ - x_min_);
    }
    float normalize_y(int raw) const {
        return (float)(raw - y_min_) / (float)(y_max_ - y_min_);
    }

private:
    int fd_{-1};
    libevdev* dev_{nullptr};
    int x_min_{0}, x_max_{1}, y_min_{0}, y_max_{1};
    int max_slots_{10};
};
```

### 4.2 Reading multi-touch events

```cpp
// event_reader.hpp
#pragma once
#include <libevdev/libevdev.h>
#include <linux/input.h>
#include <vector>
#include <functional>
#include <chrono>

struct TouchSlot {
    int tracking_id{-1};  // -1 = inactive
    int raw_x{0};
    int raw_y{0};
    float x{0.0f};        // normalized [0,1]
    float y{0.0f};
    bool active() const { return tracking_id >= 0; }
};

struct TouchEvent {
    enum class Type { DOWN, MOVE, UP };
    Type type;
    int slot;
    int tracking_id;
    float x, y;          // normalized screen coords
    std::chrono::steady_clock::time_point time;
};

using TouchCallback = std::function<void(const TouchEvent&)>;
```

### 4.3 Type B (slot-based) protocol implementation

```cpp
// mt_tracker.cpp
#include "mt_tracker.hpp"

class MTTracker {
public:
    explicit MTTracker(int max_slots) : slots_(max_slots), current_slot_(0) {}

    // Call for each input_event; returns true when a complete frame is ready.
    // Fires callbacks synchronously on SYN_REPORT.
    void process(const struct input_event& ev, const TouchDevice& dev,
                 const TouchCallback& cb) {
        if (ev.type == EV_SYN && ev.code == SYN_REPORT) {
            // End of frame — fire any pending UP/DOWN/MOVE events
            flush_frame(cb);
            return;
        }

        if (ev.type != EV_ABS) return;

        switch (ev.code) {
        case ABS_MT_SLOT:
            current_slot_ = ev.value;
            if (current_slot_ >= (int)slots_.size())
                current_slot_ = 0;  // safety clamp
            break;

        case ABS_MT_TRACKING_ID: {
            auto& slot = slots_[current_slot_];
            if (ev.value >= 0) {
                // Finger down — new contact
                bool was_active = slot.active();
                slot.tracking_id = ev.value;
                if (!was_active)
                    pending_downs_.push_back(current_slot_);
            } else {
                // Finger up
                if (slot.active())
                    pending_ups_.push_back(current_slot_);
                slot.tracking_id = -1;
            }
            break;
        }

        case ABS_MT_POSITION_X:
            slots_[current_slot_].raw_x = ev.value;
            slots_[current_slot_].x = dev.normalize_x(ev.value);
            if (slots_[current_slot_].active())
                pending_moves_.insert(current_slot_);
            break;

        case ABS_MT_POSITION_Y:
            slots_[current_slot_].raw_y = ev.value;
            slots_[current_slot_].y = dev.normalize_y(ev.value);
            if (slots_[current_slot_].active())
                pending_moves_.insert(current_slot_);
            break;
        }
    }

    const std::vector<TouchSlot>& slots() const { return slots_; }

private:
    std::vector<TouchSlot> slots_;
    int current_slot_{0};
    std::vector<int> pending_downs_;
    std::vector<int> pending_ups_;
    std::set<int> pending_moves_;

    void flush_frame(const TouchCallback& cb) {
        auto now = std::chrono::steady_clock::now();

        // Process downs first
        for (int s : pending_downs_) {
            TouchEvent e;
            e.type = TouchEvent::Type::DOWN;
            e.slot = s;
            e.tracking_id = slots_[s].tracking_id;
            e.x = slots_[s].x;
            e.y = slots_[s].y;
            e.time = now;
            cb(e);
        }

        // Then moves (exclude slots that just went down or up)
        for (int s : pending_moves_) {
            if (slots_[s].active()) {
                TouchEvent e;
                e.type = TouchEvent::Type::MOVE;
                e.slot = s;
                e.tracking_id = slots_[s].tracking_id;
                e.x = slots_[s].x;
                e.y = slots_[s].y;
                e.time = now;
                cb(e);
            }
        }

        // Ups last
        for (int s : pending_ups_) {
            TouchEvent e;
            e.type = TouchEvent::Type::UP;
            e.slot = s;
            e.tracking_id = -1;  // already cleared
            e.x = slots_[s].x;
            e.y = slots_[s].y;
            e.time = now;
            cb(e);
        }

        pending_downs_.clear();
        pending_ups_.clear();
        pending_moves_.clear();
    }
};
```

### 4.4 Coordinate normalization

The TD2423D touch sensor returns raw ADC values in the range reported by the kernel (`ABS_MT_POSITION_X` min/max). To convert to pixel coordinates:

```cpp
// Convert normalized [0,1] coords to screen pixels
int to_pixel_x(float norm_x, int screen_w) {
    return static_cast<int>(norm_x * screen_w);
}
int to_pixel_y(float norm_y, int screen_h) {
    return static_cast<int>(norm_y * screen_h);
}

// Convert normalized coords to physical millimeters
// TD2423D active area: 527 mm × 296 mm
float to_mm_x(float norm_x) { return norm_x * 527.0f; }
float to_mm_y(float norm_y) { return norm_y * 296.0f; }
```

---


[↑ Back to Top](#table-of-contents)

## 5. libinput in C++

libinput sits above evdev and provides policy features: palm rejection, finger tracking, gesture recognition, and a unified event model. It is the recommended path for most applications.

### Dependencies

```bash
sudo apt-get install libinput-dev libudev-dev
```

### 5.1 Context setup

```cpp
// libinput_context.hpp
#pragma once
#include <libinput.h>
#include <libudev.h>
#include <stdexcept>
#include <functional>

// libinput uses a log handler + interface struct
static void li_log_handler(libinput*, libinput_log_priority priority,
                            const char* fmt, va_list args) {
    if (priority >= LIBINPUT_LOG_PRIORITY_ERROR) {
        vfprintf(stderr, fmt, args);
    }
}

// For opening/closing input devices without X11/Wayland compositor
struct LibinputInterface {
    static int open_restricted(const char* path, int flags, void* /*user_data*/) {
        int fd = open(path, flags);
        return fd < 0 ? -errno : fd;
    }
    static void close_restricted(int fd, void* /*user_data*/) {
        close(fd);
    }
    static const libinput_interface iface;
};
const libinput_interface LibinputInterface::iface = {
    .open_restricted  = LibinputInterface::open_restricted,
    .close_restricted = LibinputInterface::close_restricted,
};

class LibinputContext {
public:
    LibinputContext() {
        udev_ = udev_new();
        if (!udev_) throw std::runtime_error("udev_new failed");

        // Use udev seat discovery (picks up all input devices)
        li_ = libinput_udev_create_context(&LibinputInterface::iface, nullptr, udev_);
        if (!li_) throw std::runtime_error("libinput_udev_create_context failed");

        libinput_log_set_handler(li_, li_log_handler);
        libinput_log_set_priority(li_, LIBINPUT_LOG_PRIORITY_ERROR);

        if (libinput_udev_assign_seat(li_, "seat0") != 0)
            throw std::runtime_error("libinput_udev_assign_seat failed");
    }

    // Or create for a specific device path (no udev needed)
    explicit LibinputContext(const char* path) {
        udev_ = nullptr;
        li_ = libinput_path_create_context(&LibinputInterface::iface, nullptr);
        if (!li_) throw std::runtime_error("libinput_path_create_context failed");
        device_ = libinput_path_add_device(li_, path);
        if (!device_) throw std::runtime_error(std::string("Cannot add ") + path);
        libinput_device_ref(device_);
    }

    ~LibinputContext() {
        if (device_) libinput_device_unref(device_);
        if (li_)    libinput_unref(li_);
        if (udev_)  udev_unref(udev_);
    }

    int fd() const { return libinput_get_fd(li_); }
    libinput* ctx() const { return li_; }

private:
    udev* udev_{nullptr};
    libinput* li_{nullptr};
    libinput_device* device_{nullptr};
};
```

### 5.2 Touch event handling

```cpp
// libinput_handler.cpp
#include <libinput.h>
#include <cstdio>

void process_libinput_events(libinput* li) {
    libinput_dispatch(li);

    libinput_event* event;
    while ((event = libinput_get_event(li)) != nullptr) {
        libinput_event_type type = libinput_event_get_type(event);

        switch (type) {

        case LIBINPUT_EVENT_TOUCH_DOWN: {
            auto* te = libinput_event_get_touch_event(event);
            int slot   = libinput_event_touch_get_slot(te);
            int seq    = libinput_event_touch_get_seat_slot(te);
            double x   = libinput_event_touch_get_x_transformed(te, 1920);
            double y   = libinput_event_touch_get_y_transformed(te, 1080);
            printf("TOUCH DOWN slot=%d seq=%d  (%.1f, %.1f)\n", slot, seq, x, y);
            break;
        }

        case LIBINPUT_EVENT_TOUCH_MOTION: {
            auto* te = libinput_event_get_touch_event(event);
            int slot = libinput_event_touch_get_slot(te);
            double x = libinput_event_touch_get_x_transformed(te, 1920);
            double y = libinput_event_touch_get_y_transformed(te, 1080);
            printf("TOUCH MOVE slot=%d  (%.1f, %.1f)\n", slot, x, y);
            break;
        }

        case LIBINPUT_EVENT_TOUCH_UP: {
            auto* te = libinput_event_get_touch_event(event);
            int slot = libinput_event_touch_get_slot(te);
            printf("TOUCH UP   slot=%d\n", slot);
            break;
        }

        case LIBINPUT_EVENT_TOUCH_FRAME:
            // All contacts for this time-step have been reported
            break;

        case LIBINPUT_EVENT_GESTURE_SWIPE_BEGIN:
        case LIBINPUT_EVENT_GESTURE_SWIPE_UPDATE:
        case LIBINPUT_EVENT_GESTURE_SWIPE_END: {
            auto* ge = libinput_event_get_gesture_event(event);
            int nfingers = libinput_event_gesture_get_finger_count(ge);
            double dx = libinput_event_gesture_get_dx(ge);
            double dy = libinput_event_gesture_get_dy(ge);
            printf("SWIPE %d fingers  Δ(%.2f, %.2f)\n", nfingers, dx, dy);
            break;
        }

        case LIBINPUT_EVENT_GESTURE_PINCH_BEGIN:
        case LIBINPUT_EVENT_GESTURE_PINCH_UPDATE:
        case LIBINPUT_EVENT_GESTURE_PINCH_END: {
            auto* ge = libinput_event_get_gesture_event(event);
            double scale = libinput_event_gesture_get_scale(ge);
            double angle = libinput_event_gesture_get_angle_delta(ge);
            printf("PINCH scale=%.3f angle=%.2f°\n", scale, angle);
            break;
        }

        default:
            break;
        }
        libinput_event_destroy(event);
    }
}
```

### 5.3 Gesture events

libinput provides built-in gesture recognition on top of multi-touch data. Available gesture types:

| Event type | Trigger | Key data |
|-----------|---------|----------|
| `GESTURE_SWIPE_*` | 2–4 fingers moving same direction | `get_dx/dy`, finger count |
| `GESTURE_PINCH_*` | 2 fingers moving toward/away | `get_scale`, `get_angle_delta` |
| `GESTURE_HOLD_*` | 1+ fingers stationary | finger count, duration |

Note: libinput gesture recognition only fires for 2+ fingers. Single-finger taps and drags come through as `TOUCH_DOWN/MOTION/UP` events.

### 5.4 Calibration matrix

libinput accepts a 6-element affine calibration matrix via a udev property:

```
LIBINPUT_CALIBRATION_MATRIX = a b c d e f
```

The transformation is:
```
[ x' ]   [ a  b  c ] [ x ]
[ y' ] = [ d  e  f ] [ y ]
[ 1  ]   [ 0  0  1 ] [ 1 ]
```

For a 90° clockwise rotation: `0 -1 1  1 0 0`
For a simple offset correction: `1 0 0.02  0 1 -0.01` (shift 2% right, 1% up)

Apply via udev rule (see Section 15) or at runtime:

```cpp
float matrix[6] = {1, 0, 0,  0, 1, 0};  // identity
libinput_device_config_calibration_set_matrix(device, matrix);
```

---


[↑ Back to Top](#table-of-contents)

## 6. Keyboard Input

The keyboard appears as a separate `/dev/input/event*` device. Use the same evdev mechanism:

```cpp
// keyboard_reader.cpp
#include <libevdev/libevdev.h>
#include <linux/input.h>

struct KeyEvent {
    int keycode;   // KEY_A, KEY_ESC, etc.
    int value;     // 1=press, 0=release, 2=repeat
    std::chrono::steady_clock::time_point time;
};

using KeyCallback = std::function<void(const KeyEvent&)>;

void read_keyboard_events(int fd, libevdev* dev, const KeyCallback& cb) {
    struct input_event ev;
    int rc;
    while ((rc = libevdev_next_event(dev, LIBEVDEV_READ_FLAG_NORMAL, &ev)) == 0) {
        if (ev.type == EV_KEY) {
            cb(KeyEvent{
                .keycode = ev.code,
                .value   = ev.value,
                .time    = std::chrono::steady_clock::now()
            });
        }
    }
    if (rc != -EAGAIN)
        fprintf(stderr, "keyboard read error: %s\n", strerror(-rc));
}
```

Find the keyboard device:

```bash
# Look for EV_KEY capability without EV_ABS (no touch axes)
grep -l EV /sys/class/input/event*/device/capabilities/ev | while read f; do
    dir=$(dirname $f)
    echo "$dir: ev=$(cat $f) keys=$(cat $dir/capabilities/key 2>/dev/null)"
done
```

---


[↑ Back to Top](#table-of-contents)

## 7. Unified Input Loop with epoll

Combine touch and keyboard into a single event loop with zero busy-waiting:

```cpp
// input_loop.cpp
#include <sys/epoll.h>
#include <unistd.h>
#include <libevdev/libevdev.h>
#include "touch_device.hpp"
#include "mt_tracker.hpp"

class InputLoop {
public:
    InputLoop(const std::string& touch_path, const std::string& kbd_path) {
        epfd_ = epoll_create1(0);
        if (epfd_ < 0) throw std::runtime_error("epoll_create1 failed");

        // Open touch device
        touch_fd_ = open(touch_path.c_str(), O_RDONLY | O_NONBLOCK);
        libevdev_new_from_fd(touch_fd_, &touch_dev_);
        add_fd(touch_fd_, FD_TOUCH);

        // Open keyboard
        kbd_fd_ = open(kbd_path.c_str(), O_RDONLY | O_NONBLOCK);
        libevdev_new_from_fd(kbd_fd_, &kbd_dev_);
        add_fd(kbd_fd_, FD_KBD);

        // Optional: add libinput fd for gesture events
        // add_fd(li_ctx_.fd(), FD_LIBINPUT);
    }

    ~InputLoop() {
        libevdev_free(touch_dev_);
        libevdev_free(kbd_dev_);
        close(touch_fd_);
        close(kbd_fd_);
        close(epfd_);
    }

    void run(const TouchCallback& on_touch, const KeyCallback& on_key) {
        running_ = true;
        constexpr int MAX_EVENTS = 16;
        struct epoll_event events[MAX_EVENTS];

        while (running_) {
            int n = epoll_wait(epfd_, events, MAX_EVENTS, -1 /*block forever*/);
            for (int i = 0; i < n; ++i) {
                uintptr_t tag = events[i].data.u64;

                if (tag == FD_TOUCH) {
                    drain_touch(on_touch);
                } else if (tag == FD_KBD) {
                    drain_keyboard(on_key);
                }
            }
        }
    }

    void stop() { running_ = false; }

private:
    static constexpr uintptr_t FD_TOUCH    = 1;
    static constexpr uintptr_t FD_KBD      = 2;
    static constexpr uintptr_t FD_LIBINPUT = 3;

    int epfd_{-1};
    int touch_fd_{-1}, kbd_fd_{-1};
    libevdev* touch_dev_{nullptr};
    libevdev* kbd_dev_{nullptr};
    bool running_{false};
    MTTracker tracker_{10};

    void add_fd(int fd, uintptr_t tag) {
        struct epoll_event ev{};
        ev.events = EPOLLIN;
        ev.data.u64 = tag;
        if (epoll_ctl(epfd_, EPOLL_CTL_ADD, fd, &ev) < 0)
            throw std::runtime_error("epoll_ctl failed");
    }

    void drain_touch(const TouchCallback& cb) {
        struct input_event ev;
        int rc;
        while ((rc = libevdev_next_event(touch_dev_,
                    LIBEVDEV_READ_FLAG_NORMAL, &ev)) == 0) {
            tracker_.process(ev, /* dev */ cb);
        }
    }

    void drain_keyboard(const KeyCallback& cb) {
        struct input_event ev;
        int rc;
        while ((rc = libevdev_next_event(kbd_dev_,
                    LIBEVDEV_READ_FLAG_NORMAL, &ev)) == 0) {
            if (ev.type == EV_KEY) {
                cb(KeyEvent{.keycode = ev.code, .value = ev.value,
                            .time = std::chrono::steady_clock::now()});
            }
        }
    }
};
```

---


[↑ Back to Top](#table-of-contents)

## 8. Multi-Touch Gesture Recognition

When using raw evdev (not libinput), implement gesture recognizers manually.

### 8.1 Tap detection

```cpp
// gesture/tap.hpp
#include <chrono>
#include <unordered_map>

class TapDetector {
public:
    struct TapEvent {
        float x, y;
        int tap_count;  // 1=single, 2=double
    };
    using Callback = std::function<void(const TapEvent&)>;

    explicit TapDetector(Callback cb) : cb_(std::move(cb)) {}

    void on_touch(const TouchEvent& e) {
        if (e.type == TouchEvent::Type::DOWN) {
            down_time_[e.slot] = e.time;
            down_pos_[e.slot]  = {e.x, e.y};
        } else if (e.type == TouchEvent::Type::UP) {
            auto it = down_time_.find(e.slot);
            if (it == down_time_.end()) return;

            auto duration = e.time - it->second;
            auto& pos = down_pos_[e.slot];

            // Must be short press and minimal movement
            if (duration <= TAP_MAX_DURATION && distance(pos, {e.x, e.y}) < TAP_MAX_MOVE) {
                auto now = e.time;
                if (pending_tap_ && (now - last_tap_time_) < DOUBLE_TAP_WINDOW) {
                    cb_(TapEvent{pos.first, pos.second, 2});
                    pending_tap_ = false;
                } else {
                    pending_tap_ = true;
                    last_tap_pos_ = pos;
                    last_tap_time_ = now;
                    // Schedule single-tap callback after DOUBLE_TAP_WINDOW
                    // (in a real app, use a timer; simplified here)
                }
            }
            down_time_.erase(it);
        }
    }

    void flush_pending(std::chrono::steady_clock::time_point now) {
        if (pending_tap_ && (now - last_tap_time_) >= DOUBLE_TAP_WINDOW) {
            cb_(TapEvent{last_tap_pos_.first, last_tap_pos_.second, 1});
            pending_tap_ = false;
        }
    }

private:
    using TimePoint = std::chrono::steady_clock::time_point;
    using Duration  = std::chrono::milliseconds;

    static constexpr Duration TAP_MAX_DURATION  = Duration{150};
    static constexpr Duration DOUBLE_TAP_WINDOW = Duration{300};
    static constexpr float    TAP_MAX_MOVE      = 0.03f;  // 3% of screen

    Callback cb_;
    std::unordered_map<int, TimePoint> down_time_;
    std::unordered_map<int, std::pair<float,float>> down_pos_;
    bool pending_tap_{false};
    TimePoint last_tap_time_;
    std::pair<float,float> last_tap_pos_;

    float distance(std::pair<float,float> a, std::pair<float,float> b) {
        float dx = a.first - b.first;
        float dy = a.second - b.second;
        return std::sqrt(dx*dx + dy*dy);
    }
};
```

### 8.2 Swipe detection

```cpp
// gesture/swipe.hpp
#include <array>

class SwipeDetector {
public:
    enum class Direction { LEFT, RIGHT, UP, DOWN };
    struct SwipeEvent {
        Direction dir;
        float velocity;  // normalized units/sec
        int finger_count;
    };
    using Callback = std::function<void(const SwipeEvent&)>;

    explicit SwipeDetector(Callback cb) : cb_(std::move(cb)) {}

    void on_touch(const TouchEvent& e) {
        if (e.type == TouchEvent::Type::DOWN) {
            start_[e.slot] = {e.x, e.y, e.time};
            active_count_++;
        } else if (e.type == TouchEvent::Type::MOVE) {
            last_[e.slot] = {e.x, e.y, e.time};
        } else if (e.type == TouchEvent::Type::UP) {
            auto sit = start_.find(e.slot);
            if (sit == start_.end()) { active_count_--; return; }

            auto& s = sit->second;
            float dx = e.x - s.x;
            float dy = e.y - s.y;
            float dist = std::sqrt(dx*dx + dy*dy);

            using fms = std::chrono::duration<float, std::milli>;
            float ms = fms(e.time - s.time).count();

            if (dist > SWIPE_MIN_DIST && ms < SWIPE_MAX_MS) {
                Direction dir;
                if (std::abs(dx) > std::abs(dy))
                    dir = dx > 0 ? Direction::RIGHT : Direction::LEFT;
                else
                    dir = dy > 0 ? Direction::DOWN : Direction::UP;

                cb_(SwipeEvent{dir, dist / (ms / 1000.0f), active_count_});
            }
            start_.erase(sit);
            active_count_--;
        }
    }

private:
    struct PosTime { float x, y; std::chrono::steady_clock::time_point t; };

    static constexpr float SWIPE_MIN_DIST = 0.15f;  // 15% of screen
    static constexpr float SWIPE_MAX_MS   = 500.0f;

    Callback cb_;
    std::unordered_map<int, PosTime> start_, last_;
    int active_count_{0};
};
```

### 8.3 Pinch-to-zoom

```cpp
// gesture/pinch.hpp
class PinchDetector {
public:
    struct PinchEvent {
        float scale;    // >1 zoom in, <1 zoom out
        float center_x, center_y;
    };
    using Callback = std::function<void(const PinchEvent&)>;

    explicit PinchDetector(Callback cb) : cb_(std::move(cb)) {}

    void on_touch(const TouchEvent& e) {
        if (e.type == TouchEvent::Type::DOWN) {
            active_[e.slot] = {e.x, e.y};
        } else if (e.type == TouchEvent::Type::MOVE) {
            if (active_.count(e.slot)) {
                active_[e.slot] = {e.x, e.y};
                try_pinch();
            }
        } else if (e.type == TouchEvent::Type::UP) {
            active_.erase(e.slot);
            reference_dist_ = -1.0f;  // reset on any lift
        }
    }

private:
    struct Point { float x, y; };
    Callback cb_;
    std::unordered_map<int, Point> active_;
    float reference_dist_{-1.0f};

    void try_pinch() {
        if (active_.size() < 2) return;

        // Use the first two active touches
        auto it = active_.begin();
        const Point& a = it->second; ++it;
        const Point& b = it->second;

        float dx   = a.x - b.x;
        float dy   = a.y - b.y;
        float dist = std::sqrt(dx*dx + dy*dy);

        if (reference_dist_ < 0) {
            reference_dist_ = dist;
            return;
        }

        float scale = dist / reference_dist_;
        reference_dist_ = dist;

        if (std::abs(scale - 1.0f) > 0.01f) {  // minimum 1% change
            cb_(PinchEvent{
                scale,
                (a.x + b.x) * 0.5f,
                (a.y + b.y) * 0.5f
            });
        }
    }
};
```

---


[↑ Back to Top](#table-of-contents)

## 9. Display Output — DRM/KMS

For a standalone C++ application without a compositor (X11/Wayland), use DRM/KMS directly. This is the right approach for a dedicated command deck that owns the display.

### Dependencies

```bash
sudo apt-get install libdrm-dev libgbm-dev
```

### 9.1 Opening the DRM device

```cpp
// drm_device.cpp
#include <xf86drm.h>
#include <xf86drmMode.h>
#include <fcntl.h>

class DRMDevice {
public:
    explicit DRMDevice(const char* path = "/dev/dri/card0") {
        fd_ = open(path, O_RDWR | O_CLOEXEC);
        if (fd_ < 0) throw std::runtime_error("Cannot open DRM device");

        // Request universal planes and atomic modesetting
        drmSetClientCap(fd_, DRM_CLIENT_CAP_UNIVERSAL_PLANES, 1);
        drmSetClientCap(fd_, DRM_CLIENT_CAP_ATOMIC, 1);

        // Get current display resources
        res_ = drmModeGetResources(fd_);
        if (!res_) throw std::runtime_error("drmModeGetResources failed");
    }

    ~DRMDevice() {
        if (res_) drmModeFreeResources(res_);
        if (fd_ >= 0) close(fd_);
    }

    int fd() const { return fd_; }
    drmModeResPtr res() const { return res_; }

    // Find a connected connector (display)
    drmModeConnectorPtr find_connector() const {
        for (int i = 0; i < res_->count_connectors; ++i) {
            auto* conn = drmModeGetConnector(fd_, res_->connectors[i]);
            if (conn && conn->connection == DRM_MODE_CONNECTED && conn->count_modes > 0)
                return conn;
            drmModeFreeConnector(conn);
        }
        return nullptr;
    }

private:
    int fd_{-1};
    drmModeResPtr res_{nullptr};
};
```

### 9.2 Mode setting

```cpp
// drm_modesetter.cpp
#include <xf86drm.h>
#include <xf86drmMode.h>
#include <sys/mman.h>
#include <cstring>

struct DRMFramebuffer {
    uint32_t fb_id;
    uint8_t* map;
    uint32_t width, height, stride, size;
    int fd;
};

DRMFramebuffer create_dumb_framebuffer(int drm_fd, uint32_t w, uint32_t h) {
    // Create a dumb buffer (CPU-mappable)
    struct drm_mode_create_dumb create{};
    create.width  = w;
    create.height = h;
    create.bpp    = 32;
    drmIoctl(drm_fd, DRM_IOCTL_MODE_CREATE_DUMB, &create);

    // Add framebuffer
    uint32_t fb_id = 0;
    drmModeAddFB(drm_fd, w, h, 24, 32, create.pitch,
                 create.handle, &fb_id);

    // Map buffer to CPU memory
    struct drm_mode_map_dumb map_dumb{};
    map_dumb.handle = create.handle;
    drmIoctl(drm_fd, DRM_IOCTL_MODE_MAP_DUMB, &map_dumb);

    void* mapped = mmap(nullptr, create.size, PROT_READ | PROT_WRITE,
                        MAP_SHARED, drm_fd, map_dumb.offset);

    memset(mapped, 0, create.size);  // clear to black

    return DRMFramebuffer{
        fb_id,
        static_cast<uint8_t*>(mapped),
        w, h, (uint32_t)create.pitch,
        (uint32_t)create.size,
        drm_fd
    };
}

// Set display mode (legacy modesetting — simple and widely supported)
void set_mode(int drm_fd, uint32_t crtc_id, uint32_t connector_id,
              uint32_t fb_id, drmModeModeInfoPtr mode) {
    drmModeSetCrtc(drm_fd, crtc_id, fb_id, 0, 0,
                   &connector_id, 1, mode);
}

// Draw a pixel (BGRA/XRGB format)
inline void draw_pixel(DRMFramebuffer& fb, int x, int y,
                        uint8_t r, uint8_t g, uint8_t b) {
    if (x < 0 || y < 0 || x >= (int)fb.width || y >= (int)fb.height) return;
    uint32_t* row = reinterpret_cast<uint32_t*>(fb.map + y * fb.stride);
    row[x] = (0xFF << 24) | (r << 16) | (g << 8) | b;
}
```

### 9.3 Framebuffer rendering loop

```cpp
// Minimal DRM rendering loop (no GL)
int main() {
    DRMDevice drm;
    auto* conn = drm.find_connector();
    if (!conn) { fprintf(stderr, "No display connected\n"); return 1; }

    drmModeModeInfo& mode = conn->modes[0];  // use first (preferred) mode
    uint32_t w = mode.hdisplay;  // 1920
    uint32_t h = mode.vdisplay;  // 1080

    // Find matching encoder → CRTC
    auto* enc  = drmModeGetEncoder(drm.fd(), conn->encoder_id);
    uint32_t crtc_id = enc->crtc_id;
    drmModeFreeEncoder(enc);

    auto fb = create_dumb_framebuffer(drm.fd(), w, h);
    set_mode(drm.fd(), crtc_id, conn->connector_id, fb.fb_id, &mode);

    // Render loop
    while (true) {
        // Clear
        memset(fb.map, 0x11, fb.size);  // dark grey background

        // Draw touch indicators, UI, etc.
        draw_pixel(fb, 100, 100, 255, 0, 0);  // red dot

        // Page flip (double-buffered with two FBs is better)
        drmModeSetCrtc(drm.fd(), crtc_id, fb.fb_id, 0, 0,
                       &conn->connector_id, 1, &mode);
    }
}
```

---


[↑ Back to Top](#table-of-contents)

## 10. OpenGL / EGL on DRM/KMS

For a proper command-deck UI with hardware-accelerated rendering, use OpenGL via EGL and GBM. This is the professional path and enables CUDA interop.

### 10.1 EGL setup with GBM

```cpp
// egl_context.cpp
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES3/gl3.h>
#include <gbm.h>
#include <xf86drm.h>
#include <xf86drmMode.h>

class EGLContext {
public:
    EGLContext(int drm_fd, uint32_t w, uint32_t h)
        : drm_fd_(drm_fd), width_(w), height_(h) {
        setup_gbm();
        setup_egl();
    }

    ~EGLContext() {
        eglDestroyContext(display_, context_);
        eglDestroySurface(display_, surface_);
        eglTerminate(display_);
        gbm_surface_destroy(gbm_surface_);
        gbm_device_destroy(gbm_device_);
    }

    void make_current() {
        eglMakeCurrent(display_, surface_, surface_, context_);
    }

    void swap_buffers(uint32_t crtc_id, uint32_t connector_id, drmModeModeInfo* mode) {
        eglSwapBuffers(display_, surface_);

        // Lock front buffer and page flip
        auto* bo = gbm_surface_lock_front_buffer(gbm_surface_);
        uint32_t fb_id = bo_to_fb(bo);

        drmModePageFlip(drm_fd_, crtc_id, fb_id, DRM_MODE_PAGE_FLIP_EVENT, nullptr);

        // Wait for flip completion
        fd_set fds; FD_ZERO(&fds); FD_SET(drm_fd_, &fds);
        select(drm_fd_ + 1, &fds, nullptr, nullptr, nullptr);

        drmEventContext evctx{};
        evctx.version = 2;
        evctx.page_flip_handler = [](int, unsigned, unsigned, unsigned, void*){};
        drmHandleEvent(drm_fd_, &evctx);

        if (prev_bo_) {
            drmModeRmFB(drm_fd_, prev_fb_id_);
            gbm_surface_release_buffer(gbm_surface_, prev_bo_);
        }
        prev_bo_    = bo;
        prev_fb_id_ = fb_id;
    }

private:
    int drm_fd_;
    uint32_t width_, height_;
    gbm_device*  gbm_device_{nullptr};
    gbm_surface* gbm_surface_{nullptr};
    EGLDisplay display_{EGL_NO_DISPLAY};
    EGLSurface surface_{EGL_NO_SURFACE};
    ::EGLContext context_{EGL_NO_CONTEXT};
    gbm_bo* prev_bo_{nullptr};
    uint32_t prev_fb_id_{0};

    void setup_gbm() {
        gbm_device_ = gbm_create_device(drm_fd_);
        gbm_surface_ = gbm_surface_create(gbm_device_, width_, height_,
                                           GBM_FORMAT_XRGB8888,
                                           GBM_BO_USE_SCANOUT | GBM_BO_USE_RENDERING);
    }

    void setup_egl() {
        // Get EGL display from GBM device
        PFNEGLGETPLATFORMDISPLAYEXTPROC eglGetPlatformDisplayEXT =
            (PFNEGLGETPLATFORMDISPLAYEXTPROC)eglGetProcAddress("eglGetPlatformDisplayEXT");
        display_ = eglGetPlatformDisplayEXT(EGL_PLATFORM_GBM_KHR, gbm_device_, nullptr);
        eglInitialize(display_, nullptr, nullptr);

        EGLint attribs[] = {
            EGL_RED_SIZE,   8,
            EGL_GREEN_SIZE, 8,
            EGL_BLUE_SIZE,  8,
            EGL_ALPHA_SIZE, 8,
            EGL_DEPTH_SIZE, 24,
            EGL_RENDERABLE_TYPE, EGL_OPENGL_ES3_BIT,
            EGL_SURFACE_TYPE, EGL_WINDOW_BIT,
            EGL_NONE
        };
        EGLConfig config;
        EGLint n;
        eglChooseConfig(display_, attribs, &config, 1, &n);

        EGLint ctx_attribs[] = { EGL_CONTEXT_CLIENT_VERSION, 3, EGL_NONE };
        eglBindAPI(EGL_OPENGL_ES_API);
        context_ = eglCreateContext(display_, config, EGL_NO_CONTEXT, ctx_attribs);
        surface_ = eglCreateWindowSurface(display_, config,
                                           (EGLNativeWindowType)gbm_surface_, nullptr);
        eglMakeCurrent(display_, surface_, surface_, context_);
    }

    uint32_t bo_to_fb(gbm_bo* bo) {
        uint32_t handles[4] = { gbm_bo_get_handle(bo).u32 };
        uint32_t strides[4] = { gbm_bo_get_stride(bo) };
        uint32_t offsets[4] = { 0 };
        uint32_t fb_id = 0;
        drmModeAddFB2(drm_fd_, width_, height_, DRM_FORMAT_XRGB8888,
                      handles, strides, offsets, &fb_id, 0);
        return fb_id;
    }
};
```

### 10.2 Rendering to screen

```cpp
// A minimal GL ES 3 render pass
void render_frame(float touch_x, float touch_y) {
    glClearColor(0.05f, 0.05f, 0.1f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);

    // Draw UI elements using your shader programs
    // draw_panel(0, 0, 1920, 540, 0x1a1a2e);
    // draw_button(touch_x, touch_y, "Power Off");
}
```

---


[↑ Back to Top](#table-of-contents)

## 11. SDL2 as a Higher-Level Alternative

If you do not need bare-metal DRM/KMS control, SDL2 wraps the entire display + input stack and works on DRM/KMS natively (without X11/Wayland) when compiled with `SDL_VIDEO_DRIVER=kmsdrm`.

```cpp
// sdl2_app.cpp
#include <SDL2/SDL.h>

class SDL2App {
public:
    SDL2App(int w = 1920, int h = 1080) {
        // Force KMS/DRM video driver (no X11/Wayland needed)
        SDL_SetHint(SDL_HINT_VIDEODRIVER, "kmsdrm");
        // Enable multi-touch
        SDL_SetHint(SDL_HINT_TOUCH_MOUSE_EVENTS, "1");

        SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS);
        window_ = SDL_CreateWindow("Command Deck",
            SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED, w, h,
            SDL_WINDOW_OPENGL | SDL_WINDOW_FULLSCREEN);
        renderer_ = SDL_CreateRenderer(window_, -1,
            SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC);
    }

    ~SDL2App() {
        SDL_DestroyRenderer(renderer_);
        SDL_DestroyWindow(window_);
        SDL_Quit();
    }

    void run() {
        bool running = true;
        SDL_Event e;
        while (running) {
            while (SDL_PollEvent(&e)) {
                if (e.type == SDL_QUIT) { running = false; break; }

                // Multi-touch finger events
                if (e.type == SDL_FINGERDOWN) {
                    printf("Touch DOWN at (%.3f, %.3f) id=%lld\n",
                           e.tfinger.x, e.tfinger.y,
                           (long long)e.tfinger.fingerId);
                } else if (e.type == SDL_FINGERMOTION) {
                    printf("Touch MOVE at (%.3f, %.3f) dx=%.4f dy=%.4f\n",
                           e.tfinger.x, e.tfinger.y,
                           e.tfinger.dx, e.tfinger.dy);
                } else if (e.type == SDL_FINGERUP) {
                    printf("Touch UP  at (%.3f, %.3f)\n",
                           e.tfinger.x, e.tfinger.y);
                } else if (e.type == SDL_MULTIGESTURE) {
                    printf("Pinch: numFingers=%d dTheta=%.4f dDist=%.4f\n",
                           e.mgesture.numFingers,
                           e.mgesture.dTheta, e.mgesture.dDist);
                }

                // Keyboard
                if (e.type == SDL_KEYDOWN) {
                    if (e.key.keysym.sym == SDLK_ESCAPE) running = false;
                }
            }

            // Render
            SDL_SetRenderDrawColor(renderer_, 0x11, 0x11, 0x22, 0xFF);
            SDL_RenderClear(renderer_);
            // Draw UI...
            SDL_RenderPresent(renderer_);
        }
    }

private:
    SDL_Window*   window_{nullptr};
    SDL_Renderer* renderer_{nullptr};
};
```

SDL2 touch coordinates are normalized [0,1] in `e.tfinger.x/y`. Multiply by screen dimensions to get pixels.

---


[↑ Back to Top](#table-of-contents)

## 12. DDC/CI Display Control

DDC/CI (Display Data Channel Command Interface) lets you programmatically control monitor settings: brightness, contrast, input source, power mode. The TD2423D supports DDC/CI over its video input cable.

### VCP code reference for TD2423D

| VCP Code | Feature |
|----------|---------|
| `0x10` | Brightness (0–100) |
| `0x12` | Contrast (0–100) |
| `0x60` | Input source (15=DisplayPort, 17=HDMI, 1=VGA) |
| `0xD6` | Power mode (1=on, 4=off) |
| `0x14` | Color preset |
| `0x62` | Audio speaker volume |

### 12.1 Using ddcutil C library

```bash
sudo apt-get install libddcutil-dev
```

```cpp
// ddc_control.cpp
#include <ddcutil_c_api.h>
#include <ddcutil_types.h>
#include <stdexcept>
#include <cstdio>

class DDCControl {
public:
    DDCControl() {
        DDCA_Status rc = ddca_init(nullptr, DDCA_SYSLOG_NOT_USED, DDCA_INIT_OPTIONS_NONE);
        if (rc != DDCRC_OK)
            throw std::runtime_error("ddca_init failed");

        // Detect all monitors
        DDCA_Display_Info_List* dlist = nullptr;
        ddca_get_display_info_list2(false, &dlist);
        if (!dlist || dlist->ct == 0) {
            throw std::runtime_error("No DDC-capable displays found");
        }

        // Open the first display (or search by model name)
        DDCA_Display_Ref dref = dlist->info[0].dref;
        rc = ddca_open_display2(dref, false, &dh_);
        ddca_free_display_info_list(dlist);
        if (rc != DDCRC_OK)
            throw std::runtime_error("ddca_open_display2 failed");
    }

    ~DDCControl() {
        if (dh_) ddca_close_display(dh_);
    }

    // Get a VCP value (current and maximum)
    std::pair<uint16_t, uint16_t> get_vcp(uint8_t vcp_code) {
        DDCA_Non_Table_Vcp_Value val{};
        DDCA_Status rc = ddca_get_non_table_vcp_value(dh_, vcp_code, &val);
        if (rc != DDCRC_OK) return {0, 0};
        return {val.cur_val, val.max_val};
    }

    // Set a VCP value
    void set_vcp(uint8_t vcp_code, uint16_t value) {
        DDCA_Status rc = ddca_set_non_table_vcp_value(dh_, vcp_code, 0, value);
        if (rc != DDCRC_OK)
            fprintf(stderr, "set_vcp 0x%02x=%d failed: %s\n",
                    vcp_code, value, ddca_rc_name(rc));
    }

    void set_brightness(int pct) {  // 0–100
        set_vcp(0x10, static_cast<uint16_t>(pct));
    }
    void set_contrast(int pct) {
        set_vcp(0x12, static_cast<uint16_t>(pct));
    }
    void set_input(uint16_t source) {  // 15=DP, 17=HDMI, 1=VGA
        set_vcp(0x60, source);
    }
    void power_off() { set_vcp(0xD6, 4); }
    void power_on()  { set_vcp(0xD6, 1); }

    int get_brightness() { return get_vcp(0x10).first; }
    int get_contrast()   { return get_vcp(0x12).first; }

private:
    DDCA_Display_Handle dh_{nullptr};
};

// Usage
int main() {
    DDCControl ddc;
    printf("Current brightness: %d\n", ddc.get_brightness());
    ddc.set_brightness(75);
    ddc.set_input(17);  // switch to HDMI
}
```

### 12.2 Raw i2c-dev access

If libddcutil is unavailable, access DDC/CI directly via `/dev/i2c-*`:

```cpp
// raw_ddc.cpp — DDC/CI over i2c-dev
#include <linux/i2c-dev.h>
#include <sys/ioctl.h>
#include <fcntl.h>
#include <unistd.h>
#include <cstdint>

constexpr uint8_t DDC_ADDR = 0x37;  // DDC/CI monitor address

// Find the i2c bus for a DRM connector:
// ls /sys/class/drm/card0-HDMI-A-1/i2c-*/
// → /sys/class/drm/card0-HDMI-A-1/i2c-3/

int open_ddc_bus(const char* i2c_path) {
    int fd = open(i2c_path, O_RDWR);
    if (fd < 0) return -1;
    if (ioctl(fd, I2C_SLAVE, DDC_ADDR) < 0) { close(fd); return -1; }
    return fd;
}

// Build and send a Get VCP Feature Request
bool get_vcp_value(int fd, uint8_t vcp_code, uint16_t& cur, uint16_t& max) {
    // DDC/CI Get VCP Feature Request packet
    uint8_t cmd[] = { 0x6E, 0x51, 0x02, 0x01, vcp_code, 0x00 };
    // Compute checksum (XOR of bytes 1..n-1 XOR 0x6F)
    uint8_t cs = 0;
    for (int i = 1; i < 5; i++) cs ^= cmd[i];
    cmd[5] = cs ^ 0x6F;

    if (write(fd, cmd, sizeof(cmd)) < 0) return false;
    usleep(50000);  // 50ms per DDC/CI spec

    uint8_t reply[12]{};
    if (read(fd, reply, sizeof(reply)) < 0) return false;

    // Parse reply: cur = bytes[8..9], max = bytes[6..7]
    max = ((uint16_t)reply[6] << 8) | reply[7];
    cur = ((uint16_t)reply[8] << 8) | reply[9];
    return true;
}

bool set_vcp_value(int fd, uint8_t vcp_code, uint16_t value) {
    uint8_t cmd[] = {
        0x6E, 0x51, 0x07, 0x03,  // header
        vcp_code,
        (uint8_t)(value >> 8),
        (uint8_t)(value & 0xFF),
        0x00  // checksum placeholder
    };
    uint8_t cs = 0;
    for (int i = 1; i < 7; i++) cs ^= cmd[i];
    cmd[7] = cs ^ 0x6E;

    return write(fd, cmd, sizeof(cmd)) == (ssize_t)sizeof(cmd);
}
```

---


[↑ Back to Top](#table-of-contents)

## 13. CUDA / OpenGL Interop

For the ML training context — visualizing inference results, sensor data, or training metrics — CUDA can write directly into OpenGL textures or Vulkan images, which are then composited into the command-deck UI with zero CPU copies.

### 13.1 CUDA → OpenGL texture pipeline

```cpp
// cuda_gl_interop.cu
#include <cuda_gl_interop.h>
#include <GL/gl.h>
#include <stdexcept>

class CUDAGLTexture {
public:
    CUDAGLTexture(int width, int height)
        : width_(width), height_(height) {
        // Create OpenGL texture
        glGenTextures(1, &tex_id_);
        glBindTexture(GL_TEXTURE_2D, tex_id_);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, width, height, 0,
                     GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
        glBindTexture(GL_TEXTURE_2D, 0);

        // Register texture with CUDA
        cudaError_t err = cudaGraphicsGLRegisterImage(
            &cuda_resource_, tex_id_, GL_TEXTURE_2D,
            cudaGraphicsRegisterFlagsSurfaceLoadStore);
        if (err != cudaSuccess)
            throw std::runtime_error("cudaGraphicsGLRegisterImage failed");
    }

    ~CUDAGLTexture() {
        cudaGraphicsUnregisterResource(cuda_resource_);
        glDeleteTextures(1, &tex_id_);
    }

    // Map the texture into CUDA address space for writing
    cudaSurfaceObject_t map_for_cuda() {
        cudaGraphicsMapResources(1, &cuda_resource_, 0);
        cudaArray_t arr;
        cudaGraphicsSubResourceGetMappedArray(&arr, cuda_resource_, 0, 0);

        cudaResourceDesc desc{};
        desc.resType         = cudaResourceTypeArray;
        desc.res.array.array = arr;
        cudaSurfaceObject_t surf = 0;
        cudaCreateSurfaceObject(&surf, &desc);
        return surf;
    }

    void unmap_from_cuda(cudaSurfaceObject_t surf) {
        cudaDestroySurfaceObject(surf);
        cudaGraphicsUnmapResources(1, &cuda_resource_, 0);
    }

    GLuint tex_id() const { return tex_id_; }

private:
    GLuint tex_id_{0};
    cudaGraphicsResource_t cuda_resource_{nullptr};
    int width_, height_;
};

// CUDA kernel: write ML heatmap into texture
__global__ void write_heatmap(cudaSurfaceObject_t surf, float* data,
                               int width, int height) {
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= width || y >= height) return;

    float val = data[y * width + x];  // normalized [0,1] ML output
    // Map to red-yellow-green colormap
    uchar4 color;
    color.x = (unsigned char)(255 * min(1.0f, 2.0f * val));      // R
    color.y = (unsigned char)(255 * min(1.0f, 2.0f * (1-val)));  // G
    color.z = 0;
    color.w = 255;  // A

    surf2Dwrite(color, surf, x * sizeof(uchar4), y);
}

// Usage in render loop
void update_ml_overlay(CUDAGLTexture& tex, float* d_ml_data, int w, int h) {
    // Map for CUDA
    auto surf = tex.map_for_cuda();

    // Launch kernel
    dim3 block(16, 16);
    dim3 grid((w + 15) / 16, (h + 15) / 16);
    write_heatmap<<<grid, block>>>(surf, d_ml_data, w, h);
    cudaDeviceSynchronize();

    // Unmap — GL can now use the texture
    tex.unmap_from_cuda(surf);
}
```

### 13.2 Vulkan / CUDA interop

For a more modern pipeline (zero-copy, timeline semaphores):

```cpp
// vulkan_cuda_interop.cpp — key steps
// 1. Create Vulkan image with VK_EXTERNAL_MEMORY_HANDLE_TYPE_OPAQUE_FD_BIT
// 2. Export the image's memory fd with vkGetMemoryFdKHR
// 3. Import into CUDA: cudaImportExternalMemory(fd)
// 4. Create a CUDA mipmapped array from external memory
// 5. Use a Vulkan timeline semaphore exported to CUDA for synchronization
//    - vkExportSemaphore → CUDA: cudaImportExternalSemaphore
//    - Signal from CUDA: cudaSignalExternalSemaphoresAsync
//    - Wait in Vulkan: vkWaitSemaphores

// See NVIDIA sample: cuda-samples/Samples/5_Domain_Specific/vulkanCUDA
```

---


[↑ Back to Top](#table-of-contents)

## 14. Application Architecture — Command Deck

A production command-deck combining all components:

```
┌─────────────────────────────────────────────────────────────────┐
│                     CommandDeck Application                      │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │ InputThread  │    │ RenderThread │    │   CUDAThread     │  │
│  │              │    │              │    │                  │  │
│  │ epoll loop   │    │ GL ES 3.x    │    │ ML inference     │  │
│  │ touch events │───►│ EGL/GBM/KMS │    │ writes to GL tex │  │
│  │ key events   │    │ UI panels    │◄───│ via interop      │  │
│  │ gestures     │    │ overlays     │    │                  │  │
│  └──────┬───────┘    └──────┬───────┘    └──────────────────┘  │
│         │                   │                                    │
│  ┌──────▼───────────────────▼───────────────────────────────┐  │
│  │                    Event Bus (lock-free SPSC queue)        │  │
│  │  TouchEvent / KeyEvent / GestureEvent / MLUpdateEvent     │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    DDCControl Thread                        │  │
│  │  Monitors ambient light sensor → adjusts brightness        │  │
│  │  Handles power management / screen sleep                   │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Event bus (lock-free SPSC queue)

```cpp
// event_bus.hpp
#include <atomic>
#include <array>
#include <optional>

template<typename T, size_t N>
class SPSCQueue {
    static_assert((N & (N-1)) == 0, "N must be power of 2");
public:
    bool push(const T& item) {
        size_t w = write_.load(std::memory_order_relaxed);
        size_t next = (w + 1) & (N - 1);
        if (next == read_.load(std::memory_order_acquire)) return false;  // full
        buf_[w] = item;
        write_.store(next, std::memory_order_release);
        return true;
    }
    std::optional<T> pop() {
        size_t r = read_.load(std::memory_order_relaxed);
        if (r == write_.load(std::memory_order_acquire)) return std::nullopt;
        T item = buf_[r];
        read_.store((r + 1) & (N-1), std::memory_order_release);
        return item;
    }
private:
    std::array<T, N> buf_{};
    std::atomic<size_t> read_{0}, write_{0};
};
```

---


[↑ Back to Top](#table-of-contents)

## 15. udev Rules and Permissions

Create `/etc/udev/rules.d/99-touchscreen.rules`:

```udev
# ViewSonic TD2423D touch controller — grant group input access
SUBSYSTEM=="input", ATTRS{idVendor}=="0543", ATTRS{idProduct}=="9881", \
    GROUP="input", MODE="0660", TAG+="uaccess"

# Apply libinput calibration matrix for TD2423D
# Adjust values after running 'sudo libinput measure touchpad-size'
SUBSYSTEM=="input", ATTRS{idVendor}=="0543", ATTRS{idProduct}=="9881", \
    ENV{LIBINPUT_CALIBRATION_MATRIX}="1 0 0  0 1 0"

# Link stable name
SUBSYSTEM=="input", ATTRS{idVendor}=="0543", ATTRS{idProduct}=="9881", \
    SYMLINK+="input/touchscreen0"
```

Reload:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

---


[↑ Back to Top](#table-of-contents)

## 16. Calibration and Coordinate Mapping

### Detect if calibration is needed

```bash
# Check reported touch range vs display resolution
evemu-describe /dev/input/touchscreen0 | grep ABS_MT_POSITION
# ABS_MT_POSITION_X  min=0 max=32767  (for many controllers)
# ABS_MT_POSITION_Y  min=0 max=32767

# Map raw to screen: if max ≠ 32767, the driver already scales
libinput measure touchpad-size
```

### Calibration matrix math

The `LIBINPUT_CALIBRATION_MATRIX` maps from normalized hardware coordinates `(hx, hy)` (range [0,1]) to normalized screen coordinates `(sx, sy)`:

```
[ sx ]   [ a  b  c ] [ hx ]
[ sy ] = [ d  e  f ] [ hy ]
[ 1  ]   [ 0  0  1 ] [ 1  ]
```

Common transformations:

| Case | Matrix |
|------|--------|
| Identity (no transform) | `1 0 0  0 1 0` |
| 90° clockwise rotation | `0 1 0  -1 0 1` |
| 90° counter-clockwise | `0 -1 1  1 0 0` |
| 180° rotation (upside down) | `-1 0 1  0 -1 1` |
| Mirror horizontally | `-1 0 1  0 1 0` |
| Offset right by 2%, up by 1% | `1 0 0.02  0 1 -0.01` |

### Runtime calibration in C++ with libinput

```cpp
// Apply calibration to a libinput device
void apply_calibration(libinput_device* dev, float a, float b, float c,
                                              float d, float e, float f) {
    if (libinput_device_config_calibration_has_matrix(dev)) {
        float matrix[6] = {a, b, c, d, e, f};
        libinput_device_config_calibration_set_matrix(dev, matrix);
    }
}
```

### 4-point calibration procedure

```cpp
// Collect 4 calibration taps at known screen positions, then solve:
// Standard cross-ratio method using least-squares
struct CalibPoint { float hx, hy; float sx, sy; };

// Given 4 (hardware, screen) point pairs, compute the affine matrix
std::array<float,6> compute_calibration_matrix(
    const std::array<CalibPoint, 4>& pts) {
    // Solve: A * src = dst using pseudo-inverse
    // src = [hx, hy, 1]^T   dst = [sx, sy]^T
    // This is a standard overdetermined 2D affine regression
    // — see any numerical methods library (Eigen is ideal here)
    // Simplified 3-point exact solution:
    // Use Eigen::MatrixXf A(8, 6); and solve via A.jacobiSvd()
    // ... (Eigen implementation omitted for brevity)
    return {1,0,0, 0,1,0};  // identity fallback
}
```

---


[↑ Back to Top](#table-of-contents)

## 17. CMake Build System

```cmake
# CMakeLists.txt
cmake_minimum_required(VERSION 3.20)
project(CommandDeck LANGUAGES CXX CUDA)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CUDA_STANDARD 17)

# Find required packages
find_package(PkgConfig REQUIRED)
pkg_check_modules(LIBEVDEV    REQUIRED libevdev)
pkg_check_modules(LIBINPUT    REQUIRED libinput)
pkg_check_modules(LIBUDEV     REQUIRED libudev)
pkg_check_modules(LIBDRM      REQUIRED libdrm)
pkg_check_modules(GBM         REQUIRED gbm)
pkg_check_modules(EGL         REQUIRED egl)
pkg_check_modules(GLESV2      REQUIRED glesv2)
pkg_check_modules(DDCUTIL     QUIET    ddcutil)

find_package(SDL2 QUIET)
find_package(CUDAToolkit QUIET)

# Core application
add_executable(command_deck
    src/main.cpp
    src/input_loop.cpp
    src/mt_tracker.cpp
    src/gesture_tap.cpp
    src/gesture_swipe.cpp
    src/gesture_pinch.cpp
    src/drm_device.cpp
    src/egl_context.cpp
    src/ddc_control.cpp
    src/renderer.cpp
)

target_include_directories(command_deck PRIVATE
    ${LIBEVDEV_INCLUDE_DIRS}
    ${LIBINPUT_INCLUDE_DIRS}
    ${LIBUDEV_INCLUDE_DIRS}
    ${LIBDRM_INCLUDE_DIRS}
    ${GBM_INCLUDE_DIRS}
    ${EGL_INCLUDE_DIRS}
    include/
)

target_link_libraries(command_deck
    ${LIBEVDEV_LIBRARIES}
    ${LIBINPUT_LIBRARIES}
    ${LIBUDEV_LIBRARIES}
    ${LIBDRM_LIBRARIES}
    ${GBM_LIBRARIES}
    ${EGL_LIBRARIES}
    ${GLESV2_LIBRARIES}
    pthread
)

# DDC/CI support (optional)
if(DDCUTIL_FOUND)
    target_compile_definitions(command_deck PRIVATE HAVE_DDCUTIL)
    target_include_directories(command_deck PRIVATE ${DDCUTIL_INCLUDE_DIRS})
    target_link_libraries(command_deck ${DDCUTIL_LIBRARIES})
endif()

# CUDA overlay support (optional)
if(CUDAToolkit_FOUND)
    target_sources(command_deck PRIVATE src/cuda_gl_interop.cu)
    target_compile_definitions(command_deck PRIVATE HAVE_CUDA)
    target_link_libraries(command_deck CUDA::cudart CUDA::cuda_driver)
endif()

# SDL2 alternative backend
if(SDL2_FOUND)
    add_executable(command_deck_sdl2
        src/main_sdl2.cpp
        src/gesture_tap.cpp
        src/gesture_swipe.cpp
    )
    target_link_libraries(command_deck_sdl2 SDL2::SDL2 pthread)
endif()

# Build flags
target_compile_options(command_deck PRIVATE
    -O2 -Wall -Wextra
    -march=native      # optimize for the host CPU (DGX nodes)
)
```

Build:

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)
```

---


[↑ Back to Top](#table-of-contents)

## 18. Troubleshooting

### Touch not detected

```bash
# Verify USB device present
lsusb | grep -i viewsonic

# Check kernel driver bound
dmesg | grep -i "hid-multitouch\|0543:9881"

# Verify event node exists
ls -la /dev/input/by-id/ | grep -i viewsonic

# Test raw events
sudo evtest /dev/input/event4
```

### Touch works but coordinates are wrong

```bash
# Check reported axis ranges
evemu-describe /dev/input/event4 | grep MT_POSITION

# Check if libinput is rotating/transforming
sudo libinput debug-events --device /dev/input/event4

# Reset calibration
sudo udevadm trigger   # re-applies udev LIBINPUT_CALIBRATION_MATRIX rule
```

### DRM device not found or permission denied

```bash
# Check DRM devices
ls -la /dev/dri/
# crw-rw---- 1 root video 226, 0 ... card0
# crw-rw-rw- 1 root video 226, 128 ... renderD128

sudo usermod -aG video $USER
# Re-login

# Confirm CRTC/connector available
modetest -M /dev/dri/card0
```

### CUDA interop fails

```bash
# Must have NVIDIA GL extension (not Mesa for CUDA interop)
glxinfo | grep "OpenGL vendor"
# → "NVIDIA Corporation"  (not "Mesa" or "nouveau")

# Check cuda device and GL device are same GPU
nvidia-smi
# CUDA_VISIBLE_DEVICES=0 matches the GPU connected to the display
```

### DDC/CI not responding

```bash
# Enable DDC/CI in monitor OSD first (Menu → Setup → DDC/CI → On)

# Find the i2c bus for the display
sudo ddcutil detect

# Test manually
sudo ddcutil getvcp 10   # brightness

# If permission denied on /dev/i2c-*:
sudo modprobe i2c-dev
sudo chmod a+rw /dev/i2c-*
# Or add udev rule:
# SUBSYSTEM=="i2c-dev", GROUP="video", MODE="0660"
```

### High CPU usage in input loop

```bash
# Verify epoll is being used (not busy-polling)
# If using libevdev_next_event, ensure flag is LIBEVDEV_READ_FLAG_NORMAL
# and the fd is added to epoll. The loop should block in epoll_wait.

# Check with strace
strace -e trace=epoll_wait,read -p $(pidof command_deck) 2>&1 | head -20
# Should show: epoll_wait(fd, ..., -1) → blocks until event arrives
```

---

*References: Linux kernel input documentation (`Documentation/input/`), libevdev API docs, libinput documentation (freedesktop.org), Mesa EGL docs, DRM/KMS kernel docs, NVIDIA CUDA Programming Guide (OpenGL and Vulkan interoperability), ddcutil project documentation.*

---


[↑ Back to Top](#table-of-contents)

## Appendix A — Acronym Glossary

All acronyms and initialisms used in this document, in alphabetical order.

| Acronym | Full Form | Context |
|---------|-----------|---------|
| **ABS** | Absolute | Linux input subsystem event type (`EV_ABS`); absolute-position axes such as `ABS_MT_POSITION_X` |
| **ADC** | Analog-to-Digital Converter | The touch sensor hardware that converts physical pressure/capacitance into digital coordinates |
| **API** | Application Programming Interface | The programmatic interface exposed by a library (libinput API, EGL API, etc.) |
| **BGRA** | Blue-Green-Red-Alpha | A 32-bit pixel memory layout with bytes ordered B, G, R, A |
| **bpp** | Bits Per Pixel | Color depth of a framebuffer; 32 bpp = 4 bytes per pixel (XRGB8888) |
| **BTN** | Button | Linux input subsystem event code prefix for button/key state (`BTN_TOUCH`, `BTN_LEFT`) |
| **CI** | Command Interface | The command half of DDC/CI; the protocol layer that sends control messages to the monitor |
| **CPU** | Central Processing Unit | The host processor; distinguished from GPU in the CUDA interop sections |
| **CRTC** | Cathode-Ray-Tube Controller | Legacy name for the DRM display-pipeline object that drives a physical scan-out; still used in modern DRM/KMS APIs |
| **CUDA** | Compute Unified Device Architecture | NVIDIA's parallel computing platform and programming model for GPU-accelerated workloads |
| **DDC** | Display Data Channel | A VESA standard communication channel between a host and a monitor, carried on the I2C bus embedded in the video cable |
| **DDC/CI** | Display Data Channel / Command Interface | Extension of DDC that allows the host to send control commands to the monitor (brightness, contrast, input source, power) |
| **DP** | DisplayPort | A digital display interface standard; one of the video inputs on the TD2423D |
| **DRI** | Direct Rendering Infrastructure | The Linux kernel and userspace subsystem providing direct GPU access to userspace applications without going through the X server |
| **DRM** | Direct Rendering Manager | The Linux kernel subsystem that manages GPU resources and display output; entry point is `/dev/dri/card*` |
| **EGL** | Embedded Graphics Library | The Khronos native platform interface that creates rendering surfaces and connects OpenGL ES or Vulkan to the underlying windowing system (or DRM/GBM in a compositor-less setup) |
| **epoll** | Event Poll | A Linux kernel I/O event notification facility; scalable replacement for `select()`/`poll()` used in the unified input loop |
| **ES** | Embedded Systems | Qualifier in "OpenGL ES" (OpenGL for Embedded Systems), the subset of OpenGL used on mobile, embedded, and DRM/KMS targets |
| **EV** | Event | Prefix for Linux input subsystem event type constants (`EV_ABS`, `EV_KEY`, `EV_SYN`, `EV_REL`) |
| **evdev** | Event Device | The Linux kernel input event interface; raw events are read from `/dev/input/event*` nodes |
| **FD** | File Descriptor | An integer handle returned by `open()` referencing an open kernel resource (device node, socket, etc.) |
| **FHD** | Full High Definition | Display resolution of 1920 × 1080 pixels; the native resolution of the TD2423D |
| **GBM** | Generic Buffer Manager | A Mesa library that allocates DRM-compatible GPU buffers for use as EGL native window surfaces |
| **GL** | Graphics Library | Short form of OpenGL (Open Graphics Library), the cross-platform 2D/3D rendering API |
| **GLES** | OpenGL for Embedded Systems | The embedded-profile subset of OpenGL; version 3 (GLES 3.x) is used in the EGL/KMS rendering path |
| **GPU** | Graphics Processing Unit | The dedicated graphics and compute processor; in an NVIDIA DGX context it also runs CUDA workloads |
| **HDMI** | High-Definition Multimedia Interface | A digital audio/video interface standard; one of the video inputs on the TD2423D |
| **HID** | Human Interface Device | A USB device class for keyboards, mice, and touchscreens; the TD2423D touch controller is a USB HID device handled by the `hid-multitouch` kernel driver |
| **HID-MT** | Human Interface Device — Multi-Touch | The Linux kernel driver class (`hid-multitouch.ko`) that processes multi-touch HID reports and emits evdev MT events |
| **I2C** | Inter-Integrated Circuit | A two-wire serial communication bus; DDC/CI commands travel over the I2C bus embedded in the HDMI/DP cable, accessible on Linux via `/dev/i2c-*` |
| **IPS** | In-Plane Switching | An LCD panel technology providing wide viewing angles and accurate color reproduction; the panel type used in the TD2423D |
| **ioctl** | Input/Output Control | A POSIX system call for device-specific operations not covered by `read()`/`write()`; used for DRM mode-setting and I2C slave address selection |
| **KMS** | Kernel Mode Setting | The Linux kernel mechanism that moves display mode configuration (resolution, refresh rate, framebuffer mapping) from userspace into the kernel; used together with DRM |
| **ML** | Machine Learning | The AI/statistical modeling workloads running on NVIDIA DGX nodes; the command-deck overlays ML inference results using CUDA/GL interop |
| **ms** | Milliseconds | Unit of time used for touch latency, tap duration thresholds, and DDC/CI command delays |
| **MT** | Multi-Touch | The ability to track multiple simultaneous contact points; the TD2423D supports 10-point MT |
| **nvidia-smi** | NVIDIA System Management Interface | The NVIDIA command-line utility for monitoring and managing GPU state; used to verify the correct GPU is handling the display |
| **OS** | Operating System | The host operating system; this tutorial targets Linux |
| **OSD** | On-Screen Display | The interactive configuration menu built into the monitor itself; DDC/CI must be enabled in the OSD before it can be used programmatically |
| **PCAP** | Projected Capacitive | A touch sensor technology that uses a grid of capacitive electrodes behind the display glass to detect finger position; enables multi-touch and does not require stylus pressure |
| **PID** | Product ID | The 16-bit USB product identifier within a vendor's namespace; the TD2423D touch controller is `0x9881` |
| **RGBA** | Red-Green-Blue-Alpha | A 32-bit pixel format with bytes ordered R, G, B, A; used for OpenGL textures in the CUDA interop path |
| **RHEL** | Red Hat Enterprise Linux | A commercial Linux distribution; referenced alongside Fedora for `dnf`-based package installation |
| **SDL** | Simple DirectMedia Layer | A cross-platform multimedia library providing abstracted access to display, input, and audio; SDL2 is the second major version |
| **SDL2** | Simple DirectMedia Layer version 2 | The current release of SDL; supports DRM/KMS natively via its `kmsdrm` video driver without requiring X11 or Wayland |
| **SPSC** | Single-Producer Single-Consumer | A lock-free queue design where exactly one thread writes and one thread reads; used in the command-deck event bus for zero-contention inter-thread communication |
| **SVD** | Singular Value Decomposition | A matrix factorization technique used in the least-squares calibration matrix computation (via `Eigen::jacobiSvd()`) |
| **SYN** | Synchronization | The Linux input subsystem event type (`EV_SYN`) that signals the end of an event frame; `SYN_REPORT` separates complete MT contact snapshots |
| **TD2423D** | Touch Display 2423D | ViewSonic model designation: **T**ouch **D**isplay, 24-inch panel, 23 = sub-series, D = design revision |
| **UI** | User Interface | The visual and interactive layer of the command-deck application (panels, buttons, overlays) |
| **USB** | Universal Serial Bus | The serial bus standard used for the TD2423D touch interface (USB 2.0 upstream connector) |
| **udev** | Userspace Device | The Linux device manager daemon responsible for managing `/dev` nodes, applying udev rules, and populating `by-id` symlinks when devices are plugged in |
| **VCP** | Virtual Control Panel | The DDC/CI feature code namespace; each 8-bit VCP code addresses one monitor control (e.g., `0x10` = brightness, `0x60` = input source) |
| **VGA** | Video Graphics Array | An analog video interface standard; one of the legacy video inputs on the TD2423D |
| **VID** | Vendor ID | The 16-bit USB vendor identifier; ViewSonic's USB VID is `0x0543` |
| **VSync** | Vertical Synchronization | The display signal that marks the end of a video frame; DRM page-flip events and `SDL_RENDERER_PRESENTVSYNC` synchronize rendering to VSync to avoid tearing |
| **XRGB** | Extended Red-Green-Blue | A 32-bit DRM pixel format (`DRM_FORMAT_XRGB8888`) where the high byte is unused padding (X) and the remaining three bytes are R, G, B |
| **XOR** | eXclusive OR | A bitwise operation used in the DDC/CI packet checksum calculation |

---


[↑ Back to Top](#table-of-contents)

## Appendix B — Software, Drivers & Reference Links

All libraries, kernel drivers, tools, and reference documentation required or referenced by this tutorial. Organized by function.

---

### B.1 Display Hardware

| Resource | Description | Link |
|----------|-------------|------|
| ViewSonic TD2423D product page | Spec sheet, datasheet PDF, firmware downloads, OSD manual | https://www.viewsonic.com/global/products/lcd/TD2423D.php |
| ViewSonic support / drivers | Driver downloads and release notes for the TD2423D | https://www.viewsonic.com/global/service/repair.php |
| VESA DDC/CI standard (MCCS) | Monitor Control Command Set specification defining VCP codes | https://www.vesa.org/vesa-standards/ |

---

### B.2 Linux Kernel — Input Subsystem & Drivers

The `hid-multitouch` driver is in-tree — no download needed. Listed here for source reference.

| Resource | Description | Link |
|----------|-------------|------|
| Linux kernel input documentation | Canonical reference for evdev, multi-touch protocol (Type A/B), event codes | https://www.kernel.org/doc/html/latest/input/ |
| Multi-touch protocol specification | Detailed description of `ABS_MT_*` event codes, slot protocol, Type A vs B | https://www.kernel.org/doc/html/latest/input/multi-touch-protocol.html |
| `hid-multitouch` driver source | The in-kernel driver that handles USB HID multi-touch devices including the TD2423D | https://github.com/torvalds/linux/blob/master/drivers/hid/hid-multitouch.c |
| `evdev` driver source | The kernel-side evdev interface that exposes `/dev/input/event*` | https://github.com/torvalds/linux/blob/master/drivers/input/evdev.c |
| Linux input event codes reference | Full listing of `EV_*`, `ABS_*`, `KEY_*`, `SYN_*` constants | https://www.kernel.org/doc/html/latest/input/event-codes.html |
| `i2c-dev` module | Userspace I2C access for raw DDC/CI; `modprobe i2c-dev` | https://www.kernel.org/doc/html/latest/i2c/dev-interface.html |
| DRM/KMS kernel documentation | Connector, CRTC, plane, atomic modesetting internals | https://www.kernel.org/doc/html/latest/gpu/drm-kms.html |

**Package installation:**
```bash
# Headers for evdev ioctls and input_event struct
sudo apt-get install linux-headers-$(uname -r)
# Enable I2C userspace access
sudo modprobe i2c-dev
```

---

### B.3 Input Libraries

#### libevdev

Thin, officially recommended C wrapper around the raw evdev kernel interface.

| Resource | Link |
|----------|------|
| Project homepage | https://www.freedesktop.org/wiki/Software/libevdev/ |
| Source repository (GitLab) | https://gitlab.freedesktop.org/libevdev/libevdev |
| API documentation | https://www.freedesktop.org/software/libevdev/doc/latest/ |

```bash
sudo apt-get install libevdev-dev        # Ubuntu/Debian
sudo dnf install libevdev-devel          # Fedora/RHEL
```

#### libinput

Higher-level input handling library with palm rejection, calibration, and built-in gesture recognition. The recommended path for most applications.

| Resource | Link |
|----------|------|
| Documentation (latest) | https://wayland.freedesktop.org/libinput/doc/latest/ |
| Touch event API | https://wayland.freedesktop.org/libinput/doc/latest/api/group__touch.html |
| Gesture event API | https://wayland.freedesktop.org/libinput/doc/latest/api/group__gestures.html |
| Context creation API | https://wayland.freedesktop.org/libinput/doc/latest/api/group__context.html |
| Calibration matrix | https://wayland.freedesktop.org/libinput/doc/latest/api/group__config.html |
| udev device configuration | https://wayland.freedesktop.org/libinput/doc/latest/device-configuration-via-udev.html |
| Palm detection | https://wayland.freedesktop.org/libinput/doc/latest/palm-detection.html |
| Source repository (GitLab) | https://gitlab.freedesktop.org/libinput/libinput |

```bash
sudo apt-get install libinput-dev libudev-dev    # Ubuntu/Debian
sudo dnf install libinput-devel libudev-devel     # Fedora/RHEL
```

#### libudev

The udev client library; required by libinput for seat-based device discovery.

| Resource | Link |
|----------|------|
| systemd/udev project | https://systemd.io/ |
| libudev API reference | https://www.freedesktop.org/software/systemd/man/latest/libudev.html |

```bash
sudo apt-get install libudev-dev
```

---

### B.4 Display Output — DRM/KMS & Graphics

#### libdrm

Userspace bindings for the Linux Direct Rendering Manager kernel subsystem.

| Resource | Link |
|----------|------|
| Mesa DRM repository | https://gitlab.freedesktop.org/mesa/drm |
| DRM howto (David Herrmann) | https://github.com/dvdhrm/docs/tree/master/drm-howto |
| DRM/KMS kernel docs | https://www.kernel.org/doc/html/latest/gpu/drm-kms.html |
| `xf86drm.h` / `xf86drmMode.h` headers | Included with `libdrm-dev` |

```bash
sudo apt-get install libdrm-dev          # Ubuntu/Debian
sudo dnf install libdrm-devel            # Fedora/RHEL
```

#### GBM (Generic Buffer Manager)

Allocates DRM-compatible GPU buffers for use as EGL native window surfaces. Ships with Mesa.

| Resource | Link |
|----------|------|
| Mesa project (GBM is part of Mesa) | https://mesa3d.org/ |
| Mesa source repository | https://gitlab.freedesktop.org/mesa/mesa |
| `kmscube` — minimal EGL/KMS/GBM example | https://gitlab.freedesktop.org/mesa/kmscube |

```bash
sudo apt-get install libgbm-dev          # Ubuntu/Debian
sudo dnf install mesa-libgbm-devel       # Fedora/RHEL
```

#### EGL

The Khronos native platform interface connecting OpenGL ES to DRM/GBM. Ships with Mesa or the NVIDIA driver stack.

| Resource | Link |
|----------|------|
| EGL specification (Khronos) | https://registry.khronos.org/EGL/ |
| EGL reference pages | https://registry.khronos.org/EGL/sdk/docs/man/ |
| Mesa EGL documentation | https://docs.mesa3d.org/egl.html |
| Khronos EGL registry | https://registry.khronos.org/EGL/api/EGL/ |

```bash
sudo apt-get install libegl-dev libgles2-mesa-dev   # Ubuntu/Debian (Mesa)
# NVIDIA: EGL ships with the NVIDIA proprietary driver package
```

#### OpenGL ES 3 (GLES 3)

The embedded-profile OpenGL used for the command-deck rendering path.

| Resource | Link |
|----------|------|
| OpenGL ES 3.x specification (Khronos) | https://registry.khronos.org/OpenGL/index_es.php |
| GLES 3.0 reference pages | https://registry.khronos.org/OpenGL-Refpages/es3/ |
| Mesa OpenGL ES support matrix | https://docs.mesa3d.org/systems.html |

#### SDL2

Optional higher-level alternative to raw DRM/KMS; handles display, input, and audio.

| Resource | Link |
|----------|------|
| SDL2 official website | https://www.libsdl.org/ |
| SDL2 source repository | https://github.com/libsdl-org/SDL |
| SDL2 touch event documentation | https://wiki.libsdl.org/SDL2/SDL_TouchFingerEvent |
| SDL2 KMS/DRM backend | https://wiki.libsdl.org/SDL2/README/kmsdrm |
| SDL2 multi-gesture event | https://wiki.libsdl.org/SDL2/SDL_MultiGestureEvent |

```bash
sudo apt-get install libsdl2-dev         # Ubuntu/Debian
sudo dnf install SDL2-devel              # Fedora/RHEL
```

---

### B.5 Monitor Control — DDC/CI

#### ddcutil

The standard Linux tool and C library for DDC/CI monitor control.

| Resource | Link |
|----------|------|
| Project website | https://www.ddcutil.com/ |
| C API reference | https://www.ddcutil.com/api_main/ |
| VCP feature codes reference | https://www.ddcutil.com/vcp_feature_codes/ |
| Source repository (GitHub) | https://github.com/rockowitz/ddcutil |
| i2c-dev prerequisites | https://www.ddcutil.com/i2c_permissions/ |

```bash
sudo apt-get install ddcutil libddcutil-dev   # Ubuntu/Debian
sudo dnf install ddcutil ddcutil-devel        # Fedora/RHEL
```

---

### B.6 CUDA & NVIDIA GPU

#### CUDA Toolkit

Required for the CUDA/OpenGL and CUDA/Vulkan interop sections.

| Resource | Link |
|----------|------|
| CUDA Toolkit download | https://developer.nvidia.com/cuda-downloads |
| CUDA C++ Programming Guide | https://docs.nvidia.com/cuda/cuda-c-programming-guide/ |
| OpenGL interoperability | https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#opengl-interoperability |
| Vulkan interoperability | https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#vulkan-interoperability |
| CUDA Runtime API reference | https://docs.nvidia.com/cuda/cuda-runtime-api/ |
| `cudaGraphicsGLRegisterImage` | https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__INTEROP.html |
| CUDA samples (vulkanCUDA) | https://github.com/NVIDIA/cuda-samples/tree/master/Samples/5_Domain_Specific/vulkanCUDA |
| CUDA samples (simpleGL) | https://github.com/NVIDIA/cuda-samples/tree/master/Samples/2_Concepts_and_Techniques/simpleGL |
| EGL/CUDA interop | https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__EGL.html |

#### NVIDIA Proprietary Driver

Required on DGX nodes for CUDA and for NVIDIA's EGL/OpenGL implementation (Mesa will not provide CUDA interop).

| Resource | Link |
|----------|------|
| NVIDIA driver downloads | https://www.nvidia.com/Download/index.aspx |
| NVIDIA Linux driver documentation | https://download.nvidia.com/XFree86/Linux-x86_64/latest/README/ |
| NVIDIA DGX OS / Base OS | https://docs.nvidia.com/dgx/dgx-os-server-release-notes/ |

#### Vulkan SDK (optional — for Vulkan/CUDA interop path)

| Resource | Link |
|----------|------|
| Vulkan SDK (LunarG) | https://vulkan.lunarg.com/sdk/home |
| Vulkan specification | https://registry.khronos.org/vulkan/ |
| `VK_KHR_external_memory_fd` extension | https://registry.khronos.org/vulkan/specs/1.3-extensions/man/html/VK_KHR_external_memory_fd.html |
| `VK_KHR_external_semaphore_fd` extension | https://registry.khronos.org/vulkan/specs/1.3-extensions/man/html/VK_KHR_external_semaphore_fd.html |

---

### B.7 Build System

#### CMake

| Resource | Link |
|----------|------|
| CMake official website | https://cmake.org/ |
| CMake download | https://cmake.org/download/ |
| `find_package` documentation | https://cmake.org/cmake/help/latest/command/find_package.html |
| `pkg_check_modules` (PkgConfig) | https://cmake.org/cmake/help/latest/module/FindPkgConfig.html |
| `FindCUDAToolkit` module | https://cmake.org/cmake/help/latest/module/FindCUDAToolkit.html |

```bash
sudo apt-get install cmake               # Ubuntu/Debian (may be outdated; prefer snap/pip for latest)
# Or download from cmake.org/download/
```

#### pkg-config

Required by CMake's `pkg_check_modules` to locate libevdev, libinput, libdrm, etc.

```bash
sudo apt-get install pkg-config          # Ubuntu/Debian
sudo dnf install pkgconf-pkg-config      # Fedora/RHEL
```

---

### B.8 Debugging & Development Tools

| Tool | Description | Install | Source |
|------|-------------|---------|--------|
| `evtest` | Displays raw events from any `/dev/input/event*` device; essential for verifying touch is working | `sudo apt-get install evtest` | https://gitlab.freedesktop.org/libevdev/evtest |
| `evemu-tools` | `evemu-describe` prints device capabilities and axis ranges; `evemu-record` captures event streams | `sudo apt-get install evemu-tools` | https://www.freedesktop.org/wiki/Evemu/ |
| `libinput-tools` | `libinput debug-events`, `libinput measure`, `libinput analyze` — inspect libinput's view of devices | `sudo apt-get install libinput-tools` | https://wayland.freedesktop.org/libinput/doc/latest/tools.html |
| `udevadm` | Inspect udev rules, trigger hotplug events, query device attributes | Ships with `systemd` | https://systemd.io/ |
| `ddcutil` (CLI) | `ddcutil detect`, `ddcutil getvcp`, `ddcutil setvcp` — test DDC/CI without writing code | `sudo apt-get install ddcutil` | https://www.ddcutil.com/ |
| `modetest` | Lists DRM connectors, CRTCs, encoders, and supported modes | `sudo apt-get install libdrm-tests` | https://gitlab.freedesktop.org/mesa/drm |
| `glxinfo` / `eglinfo` | Verify OpenGL vendor and EGL extensions on the target system | `sudo apt-get install mesa-utils` | https://mesa3d.org/ |
| `strace` | Trace system calls; used to verify epoll behavior and detect busy-polling | `sudo apt-get install strace` | https://strace.io/ |
| `nvidia-smi` | NVIDIA GPU status and management; verify CUDA device matches display GPU | Ships with NVIDIA driver | https://developer.nvidia.com/nvidia-system-management-interface |
| `i2cdetect` | Scan I2C bus for DDC address `0x37`; confirms DDC/CI is accessible | `sudo apt-get install i2c-tools` | https://i2c.wiki.kernel.org/index.php/I2C_Tools |

---

### B.9 Optional Libraries

#### Eigen

Required if implementing the full least-squares 4-point calibration matrix solver referenced in Section 16.

| Resource | Link |
|----------|------|
| Eigen project website | https://eigen.tuxfamily.org/ |
| `jacobiSvd` documentation | https://eigen.tuxfamily.org/dox/classEigen_1_1JacobiSVD.html |
| Source repository | https://gitlab.com/libeigen/eigen |

```bash
sudo apt-get install libeigen3-dev       # Ubuntu/Debian
sudo dnf install eigen3-devel            # Fedora/RHEL
```

#### libinput-dev calibration tools

For interactive touchscreen calibration (generates the `LIBINPUT_CALIBRATION_MATRIX` values):

```bash
# libinput's built-in measurement tool
sudo libinput measure touchpad-size --help

# xinput_calibrator (legacy X11 tool; still useful for generating matrix values)
sudo apt-get install xinput-calibrator
```

| Resource | Link |
|----------|------|
| `xinput_calibrator` | https://gitlab.freedesktop.org/libinput/libinput |
| libinput calibration guide | https://wayland.freedesktop.org/libinput/doc/latest/touchscreen-support.html |

---

### B.10 Quick Install Reference

One-shot installation of all required packages on Ubuntu/Debian:

```bash
# Input & display libraries
sudo apt-get install \
    libevdev-dev \
    libinput-dev \
    libudev-dev \
    libdrm-dev \
    libgbm-dev \
    libegl-dev \
    libgles2-mesa-dev \
    libddcutil-dev \
    libsdl2-dev \
    libeigen3-dev

# Build tools
sudo apt-get install \
    cmake \
    pkg-config \
    build-essential

# Debugging & development tools
sudo apt-get install \
    evtest \
    evemu-tools \
    libinput-tools \
    libdrm-tests \
    mesa-utils \
    i2c-tools \
    ddcutil \
    strace

# Kernel I2C access for DDC/CI
sudo modprobe i2c-dev
echo "i2c-dev" | sudo tee /etc/modules-load.d/i2c-dev.conf
```

On Fedora/RHEL, replace `apt-get install` with `dnf install` and use the `-devel` suffix for development packages (e.g., `libevdev-devel`, `libinput-devel`).

The NVIDIA driver and CUDA Toolkit must be installed separately from the NVIDIA developer portal; they are not available through standard distribution repositories on DGX systems.
