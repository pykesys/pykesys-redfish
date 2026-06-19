// input_loop.cpp — epoll-based unified input dispatch
//
// This is the nervous system of the command deck: it bridges the kernel's
// event device layer and everything that cares about user input.
// run() lives on a dedicated OS thread (see main.cpp).
//
// Why a dedicated input thread?
// The render thread blocks for up to 16ms waiting for GPU vsync.  If touch
// events were read on the render thread, that 16ms stall would delay
// response — unacceptable when users expect <25ms feedback.  The input
// thread blocks in epoll_wait() and wakes the instant the kernel delivers
// an event, regardless of what the render thread is doing.

#include "input_loop.hpp"
#include <libevdev/libevdev.h>
#include <sys/epoll.h>
#include <fcntl.h>
#include <unistd.h>
#include <cerrno>
#include <cstring>
#include <stdexcept>
#include <linux/input.h>

// Tag encoding: high 32 bits = device type, low 32 bits = array index.
// This lets epoll_wait tell us which device fired without a lookup table.
static constexpr uint64_t TAG_TOUCH_BASE = 0x100000000ULL;
static constexpr uint64_t TAG_KBD        = 0x200000000ULL;

InputLoop::~InputLoop() {
    if (kbd_dev_) libevdev_free(kbd_dev_);
    if (kbd_fd_ >= 0) close(kbd_fd_);
    if (epfd_ >= 0) close(epfd_);
    // touch_sources_ unique_ptrs clean up TouchDevice/MTTracker automatically.
}

void InputLoop::add_touch(const std::string& path) {
    auto src    = InputSource{};
    src.device  = std::make_unique<TouchDevice>(path);
    src.tracker = std::make_unique<MTTracker>(src.device->max_slots());

    if (epfd_ < 0) init_epoll();

    const uint64_t tag = TAG_TOUCH_BASE + touch_sources_.size();
    add_fd(src.device->fd(), tag);
    touch_sources_.push_back(std::move(src));
}

void InputLoop::add_keyboard(const std::string& path) {
    if (epfd_ < 0) init_epoll();

    kbd_fd_ = open(path.c_str(), O_RDONLY | O_NONBLOCK);
    if (kbd_fd_ < 0)
        throw std::runtime_error("Cannot open keyboard " + path + ": " + strerror(errno));

    int rc = libevdev_new_from_fd(kbd_fd_, &kbd_dev_);
    if (rc < 0)
        throw std::runtime_error("libevdev_new_from_fd (keyboard) failed");

    add_fd(kbd_fd_, TAG_KBD);
}

void InputLoop::run(const TouchCallback& touch_cb, const KeyCallback& key_cb) {
    if (epfd_ < 0)
        throw std::runtime_error("InputLoop::run() called before any devices were added");

    running_.store(true, std::memory_order_relaxed);

    // 16 entries is plenty: epoll_wait returns one entry per ready *fd*,
    // not one per event.  We typically have 2–3 fds total.
    constexpr int MAX_EVENTS = 16;
    struct epoll_event events[MAX_EVENTS];

    while (running_.load(std::memory_order_relaxed)) {
        // 100ms timeout lets us check running_ even when no input arrives.
        // When input IS available we wake immediately (sub-ms latency).
        const int n = epoll_wait(epfd_, events, MAX_EVENTS, 100);

        if (n < 0) {
            if (errno == EINTR) continue;  // signal interrupted us, retry
            throw std::runtime_error(std::string("epoll_wait: ") + strerror(errno));
        }

        for (int i = 0; i < n; ++i) {
            const uint64_t tag = events[i].data.u64;

            if (tag == TAG_KBD) {
                drain_keyboard(key_cb);
            } else if (tag >= TAG_TOUCH_BASE) {
                const std::size_t idx = static_cast<std::size_t>(tag - TAG_TOUCH_BASE);
                if (idx < touch_sources_.size())
                    drain_touch(touch_sources_[idx], touch_cb);
            }
        }
    }
}

void InputLoop::init_epoll() {
    // EPOLL_CLOEXEC: close the epoll fd on exec() so child processes don't
    // inherit it.  Good hygiene even though we don't fork.
    epfd_ = epoll_create1(EPOLL_CLOEXEC);
    if (epfd_ < 0)
        throw std::runtime_error(std::string("epoll_create1: ") + strerror(errno));
}

void InputLoop::add_fd(int fd, uint64_t tag) {
    struct epoll_event ev{};
    ev.events   = EPOLLIN;
    ev.data.u64 = tag;
    if (epoll_ctl(epfd_, EPOLL_CTL_ADD, fd, &ev) < 0)
        throw std::runtime_error(std::string("epoll_ctl ADD: ") + strerror(errno));
}

void InputLoop::drain_touch(InputSource& src, const TouchCallback& cb) {
    struct input_event ev;
    int rc;
    // LIBEVDEV_READ_FLAG_NORMAL: read the next event; return -EAGAIN when
    // the queue is empty.  We drain the whole queue per epoll wakeup so we
    // never leave events sitting until the next epoll cycle.
    while ((rc = libevdev_next_event(src.device->dev(),
                                     LIBEVDEV_READ_FLAG_NORMAL, &ev)) == 0) {
        src.tracker->process(ev, *src.device, cb);
    }
    // rc == -EAGAIN is normal exit.  Other errors are non-fatal but odd.
}

void InputLoop::drain_keyboard(const KeyCallback& cb) {
    if (!kbd_dev_) return;

    struct input_event ev;
    int rc;
    while ((rc = libevdev_next_event(kbd_dev_,
                                     LIBEVDEV_READ_FLAG_NORMAL, &ev)) == 0) {
        // Filter to EV_KEY only.  The keyboard device also emits
        // EV_MSC/MSC_SCAN (hardware scancodes) and EV_SYN events — noise.
        if (ev.type == EV_KEY) {
            cb(KeyEvent{
                .code  = ev.code,
                .value = ev.value,
                .time  = std::chrono::steady_clock::now(),
            });
        }
    }
}
