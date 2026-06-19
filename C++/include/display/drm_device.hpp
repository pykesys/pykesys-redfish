// display/drm_device.hpp — DRM/KMS device, connector, and dumb framebuffer
//
// DRM (Direct Rendering Manager) is the Linux kernel subsystem that owns
// the display hardware.  KMS (Kernel Mode Setting) is the part of DRM that
// configures the display pipeline: resolution, refresh rate, which GPU
// output drives which monitor.
//
// The display pipeline from GPU to glass looks like this:
//
//   Framebuffer (GPU memory)
//       │
//   CRTC (Cathode Ray Tube Controller — historical name, now means
//         "the thing that scans out a framebuffer to an encoder")
//       │
//   Encoder (converts CRTC output to a wire protocol: HDMI, DP, etc.)
//       │
//   Connector (the physical port: HDMI-A-1, DP-1, etc.)
//       │
//   Monitor
//
// For a command deck application, we want "exclusive" access — no desktop
// compositor (no X11, no Wayland) is running.  We open /dev/dri/card0,
// find the active connector, and set the mode directly.  The monitor is
// then ours for as long as we hold the fd.
//
// A "dumb framebuffer" is a CPU-mappable buffer that the kernel allocates
// in regular RAM (not GPU VRAM).  It's suitable for simple 2D drawing with
// no hardware acceleration.  For OpenGL ES rendering, use EGLContext instead —
// it allocates GPU-backed GBM buffers.  Both share the same CRTC setup.

#pragma once
#include <xf86drm.h>
#include <xf86drmMode.h>
#include <cstdint>
#include <stdexcept>

// A CPU-mappable framebuffer: pixel data lives in mmap'd kernel memory.
// Write XRGB pixels to map[y * stride + x * 4] to draw without GPU.
struct DRMFramebuffer {
    uint32_t fb_id{0};     // DRM handle, passed to drmModeSetCrtc
    uint8_t* map{nullptr}; // mmap'd pointer to pixel data
    uint32_t width{0};
    uint32_t height{0};
    uint32_t stride{0};    // bytes per row (may be > width * 4 due to alignment)
    uint32_t size{0};      // total mapped bytes
    int      drm_fd{-1};
};

class DRMDevice {
public:
    explicit DRMDevice(const char* path = "/dev/dri/card0");
    ~DRMDevice();

    // Non-copyable: owns the DRM fd.
    DRMDevice(const DRMDevice&)            = delete;
    DRMDevice& operator=(const DRMDevice&) = delete;

    int            fd()        const { return fd_; }
    drmModeResPtr  resources() const { return res_; }

    // Walk the connector list and return the first one that is physically
    // connected to a monitor with at least one valid mode.
    // Returns nullptr if no display is attached.
    drmModeConnectorPtr find_connector() const;

    // Given a connector, find the encoder currently bound to it, then
    // return the CRTC ID that encoder is attached to.
    // The CRTC ID is needed for drmModeSetCrtc / drmModePageFlip.
    uint32_t find_crtc_for_connector(drmModeConnectorPtr conn) const;

    // Create a dumb (CPU-writable) framebuffer at the given resolution.
    // The returned struct's map pointer is valid until destroy_framebuffer().
    DRMFramebuffer create_dumb_framebuffer(uint32_t w, uint32_t h);
    void           destroy_framebuffer(DRMFramebuffer& fb);

    // Activate a mode on a connector using a framebuffer.
    // This is the "set the resolution" call.  After this, anything written
    // to fb.map appears on screen after the next vertical blank.
    void set_mode(uint32_t crtc_id, uint32_t connector_id,
                  uint32_t fb_id, drmModeModeInfoPtr mode);

    // Inline pixel writer: convert r,g,b to XRGB8888 and write to the fb.
    // x,y must be within [0, width) and [0, height) — no bounds check in
    // the hot path, but we guard in debug builds with an assert.
    static void draw_pixel(DRMFramebuffer& fb, int x, int y,
                           uint8_t r, uint8_t g, uint8_t b);

private:
    int           fd_{-1};
    drmModeResPtr res_{nullptr};
};
