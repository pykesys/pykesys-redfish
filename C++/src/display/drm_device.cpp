// display/drm_device.cpp — DRM/KMS device, mode setting, dumb framebuffer
//
// See display/drm_device.hpp for the conceptual background.
// This file handles everything up to "pixels are on screen" without GL.

#include "display/drm_device.hpp"
#include <sys/mman.h>
#include <cstring>
#include <cassert>
#include <fcntl.h>
#include <unistd.h>
#include <stdexcept>
#include <string>
#include <cerrno>

DRMDevice::DRMDevice(const char* path) {
    // O_RDWR required: we need to write mode settings, not just read state.
    // O_CLOEXEC: child processes shouldn't inherit the DRM master handle.
    fd_ = open(path, O_RDWR | O_CLOEXEC);
    if (fd_ < 0)
        throw std::runtime_error(std::string("Cannot open DRM device ") + path
                                 + ": " + strerror(errno));

    // Request the capabilities we need.
    // UNIVERSAL_PLANES: exposes primary, cursor, and overlay planes separately.
    // ATOMIC: enables atomic modesetting (set many properties in one ioctl).
    // Both are optional for our simple use case but good practice.
    drmSetClientCap(fd_, DRM_CLIENT_CAP_UNIVERSAL_PLANES, 1);
    drmSetClientCap(fd_, DRM_CLIENT_CAP_ATOMIC,           1);

    res_ = drmModeGetResources(fd_);
    if (!res_)
        throw std::runtime_error("drmModeGetResources failed — "
                                 "is another application using the display?");
}

DRMDevice::~DRMDevice() {
    if (res_) drmModeFreeResources(res_);
    if (fd_ >= 0) close(fd_);
}

drmModeConnectorPtr DRMDevice::find_connector() const {
    // Walk all connectors.  A connector represents a physical output port
    // (HDMI-A-1, DP-1, VGA-1, etc.).  We return the first one that reports
    // DRM_MODE_CONNECTED (a monitor is plugged in) and has at least one mode.
    // modes[0] is the monitor's preferred mode (highest resolution/refresh).
    for (int i = 0; i < res_->count_connectors; ++i) {
        auto* conn = drmModeGetConnector(fd_, res_->connectors[i]);
        if (conn
            && conn->connection == DRM_MODE_CONNECTED
            && conn->count_modes > 0)
        {
            return conn;  // caller must call drmModeFreeConnector()
        }
        if (conn) drmModeFreeConnector(conn);
    }
    return nullptr;
}

uint32_t DRMDevice::find_crtc_for_connector(drmModeConnectorPtr conn) const {
    // The connector has an encoder_id if it's currently active.
    if (conn->encoder_id) {
        auto* enc = drmModeGetEncoder(fd_, conn->encoder_id);
        if (enc) {
            const uint32_t crtc_id = enc->crtc_id;
            drmModeFreeEncoder(enc);
            if (crtc_id) return crtc_id;
        }
    }

    // Fallback: find any compatible CRTC by checking which encoders
    // each CRTC can work with.  This handles the case where the connector
    // is not yet active (first boot, display just plugged in, etc.).
    for (int e = 0; e < conn->count_encoders; ++e) {
        auto* enc = drmModeGetEncoder(fd_, conn->encoders[e]);
        if (!enc) continue;

        for (int c = 0; c < res_->count_crtcs; ++c) {
            // possible_crtcs is a bitmask of CRTC indices.
            if (enc->possible_crtcs & (1u << c)) {
                const uint32_t crtc_id = res_->crtcs[c];
                drmModeFreeEncoder(enc);
                return crtc_id;
            }
        }
        drmModeFreeEncoder(enc);
    }

    throw std::runtime_error("No compatible CRTC found for connector");
}

DRMFramebuffer DRMDevice::create_dumb_framebuffer(uint32_t w, uint32_t h) {
    // "Dumb" buffers are allocated in regular (CPU-visible) memory.
    // They have no GPU acceleration but are sufficient for a composited
    // software UI or debug overlay.  For GL rendering, use EGLContext instead.
    struct drm_mode_create_dumb create{};
    create.width  = w;
    create.height = h;
    create.bpp    = 32;  // XRGB8888: 1 byte per channel, 1 unused byte
    if (drmIoctl(fd_, DRM_IOCTL_MODE_CREATE_DUMB, &create) < 0)
        throw std::runtime_error("DRM_IOCTL_MODE_CREATE_DUMB failed");

    // Register the dumb buffer as a DRM framebuffer so the display hardware
    // can scan it out.  fb_id is what we pass to drmModeSetCrtc.
    uint32_t fb_id = 0;
    if (drmModeAddFB(fd_, w, h, 24, 32,
                     create.pitch, create.handle, &fb_id) < 0)
        throw std::runtime_error("drmModeAddFB failed");

    // Map the buffer into our process's address space so we can write pixels.
    struct drm_mode_map_dumb map_dumb{};
    map_dumb.handle = create.handle;
    if (drmIoctl(fd_, DRM_IOCTL_MODE_MAP_DUMB, &map_dumb) < 0)
        throw std::runtime_error("DRM_IOCTL_MODE_MAP_DUMB failed");

    void* mapped = mmap(nullptr, create.size,
                        PROT_READ | PROT_WRITE, MAP_SHARED,
                        fd_, map_dumb.offset);
    if (mapped == MAP_FAILED)
        throw std::runtime_error("mmap of dumb framebuffer failed");

    // Initialize to black.
    memset(mapped, 0, create.size);

    return DRMFramebuffer{
        .fb_id  = fb_id,
        .map    = static_cast<uint8_t*>(mapped),
        .width  = w,
        .height = h,
        .stride = static_cast<uint32_t>(create.pitch),
        .size   = static_cast<uint32_t>(create.size),
        .drm_fd = fd_,
    };
}

void DRMDevice::destroy_framebuffer(DRMFramebuffer& fb) {
    if (fb.map)   munmap(fb.map, fb.size);
    if (fb.fb_id) drmModeRmFB(fd_, fb.fb_id);
    fb = {};
}

void DRMDevice::set_mode(uint32_t crtc_id, uint32_t connector_id,
                         uint32_t fb_id, drmModeModeInfoPtr mode)
{
    // This is the "legacy" modesetting API — simple and widely supported.
    // The newer atomic API is more flexible (supports planes, async flips)
    // but requires more setup.  Legacy is fine for a single-screen kiosk.
    if (drmModeSetCrtc(fd_, crtc_id, fb_id, 0, 0,
                       &connector_id, 1, mode) < 0)
        throw std::runtime_error("drmModeSetCrtc failed");
}

void DRMDevice::draw_pixel(DRMFramebuffer& fb, int x, int y,
                            uint8_t r, uint8_t g, uint8_t b)
{
    // XRGB8888 in little-endian memory: B, G, R, X (low to high byte).
    // 0xFF << 24 sets the X byte to 0xFF (opaque / don't care).
    assert(x >= 0 && x < static_cast<int>(fb.width));
    assert(y >= 0 && y < static_cast<int>(fb.height));

    auto* row = reinterpret_cast<uint32_t*>(fb.map + y * fb.stride);
    row[x] = (0xFFu << 24) | (static_cast<uint32_t>(r) << 16)
                            | (static_cast<uint32_t>(g) <<  8)
                            |  static_cast<uint32_t>(b);
}
