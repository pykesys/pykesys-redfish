// event_bus.hpp — lock-free single-producer / single-consumer queue
//
// The command deck has two concurrently running threads:
//   InputThread  — blocks in epoll_wait(), fires on every touch/key event
//   RenderThread — runs the OpenGL draw loop at 60 Hz
//
// They need to exchange data without mutex contention, because:
//   1. Mutexes introduce priority inversion risk — the render thread
//      holding a mutex could block the input thread for a full frame.
//   2. We want deterministic latency — epoll_wait() should never stall
//      waiting for the renderer to finish a frame.
//
// Solution: a lock-free SPSC (single-producer, single-consumer) ring buffer.
// The InputThread is the sole producer; the RenderThread is the sole consumer.
// SPSC requires no CAS or heavyweight atomics — a single write_ index and
// a single read_ index are sufficient, guarded by release/acquire memory
// ordering to prevent CPU reordering.
//
// Capacity must be a power of two so the wraparound mask  (N-1)  is cheap.
// If the queue is full, push() drops the event — this is intentional.
// A 256-slot queue at 60 Hz input rate gives ~4 seconds of headroom before
// any loss, which is far more than a single-frame render budget needs.
//
// Architecture note: for multiple producers or consumers, use a different
// primitive (e.g. boost::lockfree::queue or a mutex-based deque).  SPSC
// is only safe when the invariant of exactly one producer and one consumer
// is guaranteed by design — as it is here.

#pragma once
#include <array>
#include <atomic>
#include <optional>

template<typename T, std::size_t N>
class SPSCQueue {
    static_assert((N & (N - 1)) == 0, "Capacity N must be a power of two");
public:
    // push() — called ONLY from the producer thread
    // Returns false (and drops) if the queue is full rather than blocking.
    bool push(const T& item) noexcept {
        const std::size_t w    = write_.load(std::memory_order_relaxed);
        const std::size_t next = (w + 1) & mask_;

        // If next == read_, the buffer is full.  We check read_ with
        // acquire ordering so we see all writes the consumer has made.
        if (next == read_.load(std::memory_order_acquire))
            return false;

        buf_[w] = item;

        // Release: ensure buf_[w] is visible before write_ is updated.
        write_.store(next, std::memory_order_release);
        return true;
    }

    // pop() — called ONLY from the consumer thread
    // Returns std::nullopt when the queue is empty.
    std::optional<T> pop() noexcept {
        const std::size_t r = read_.load(std::memory_order_relaxed);

        // If r == write_, the queue is empty.  Acquire to see the item
        // that the producer stored before updating write_.
        if (r == write_.load(std::memory_order_acquire))
            return std::nullopt;

        T item = buf_[r];

        // Release: ensure buf_[r] is consumed before read_ advances.
        read_.store((r + 1) & mask_, std::memory_order_release);
        return item;
    }

    std::size_t size_approx() const noexcept {
        const std::size_t w = write_.load(std::memory_order_relaxed);
        const std::size_t r = read_.load(std::memory_order_relaxed);
        return (w - r) & mask_;
    }

private:
    static constexpr std::size_t mask_ = N - 1;
    std::array<T, N>        buf_{};
    std::atomic<std::size_t> read_{0};
    // Padding between read_ and write_ prevents false sharing — they live
    // on separate cache lines so the producer and consumer cores don't
    // invalidate each other's cache on every index update.
    alignas(64) std::atomic<std::size_t> write_{0};
};

// ── Concrete event bus used by the application ────────────────────────────────
#include "common.hpp"

// 256 touch events is far more than one render frame can possibly consume.
// If somehow the render thread stalls for >4 seconds while the screen is
// producing 60 touch events/second, something worse has already gone wrong.
using TouchQueue = SPSCQueue<TouchEvent, 256>;
using KeyQueue   = SPSCQueue<KeyEvent,   64>;
