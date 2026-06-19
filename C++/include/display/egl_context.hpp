// display/egl_context.hpp — hardware-accelerated rendering via EGL + GBM
//
// EGL is Khronos's "native platform interface" — the bridge between OpenGL
// ES (which knows nothing about operating systems) and whatever the OS uses
// to allocate renderable surfaces.  On Linux without X11/Wayland, that OS
// layer is GBM (Generic Buffer Manager).
//
// The rendering pipeline:
//
//   GPU renders a frame into a GBM buffer object (BO)
//       │  (eglSwapBuffers)
//   GBM presents the front BO to DRM
//       │  (gbm_surface_lock_front_buffer)
//   DRM scans the BO out to the display at the next vblank
//       │  (drmModePageFlip)
//   We release the old BO back to GBM for reuse
//       │  (gbm_surface_release_buffer)
//   Repeat at 60 Hz
//
// Why GBM?  Because the GPU and the display controller share memory but
// have different alignment and tiling requirements.  GBM allocates BO
// memory that satisfies both "GPU can render here" (GBM_BO_USE_RENDERING)
// and "DRM can scanout from here" (GBM_BO_USE_SCANOUT).
//
// Why EGL on GBM instead of just drawing to the dumb framebuffer?
// The dumb framebuffer is CPU memory — writing to it from an OpenGL
// shader requires a costly GPU→CPU→GPU round trip.  GBM BOs live in
// GPU memory, so the GPU renders directly to what the display hardware
// will scan out.  This is the path CUDA interop requires too (you can
// register a GBM-backed OpenGL texture with cudaGraphicsGLRegisterImage).

#pragma once
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <gbm.h>
#include <xf86drm.h>
#include <xf86drmMode.h>
#include <cstdint>
#include <stdexcept>

class EGLContext {
public:
    EGLContext(int drm_fd, uint32_t width, uint32_t height);
    ~EGLContext();

    // Non-copyable: owns EGL display, surface, context, and GBM objects.
    EGLContext(const EGLContext&)            = delete;
    EGLContext& operator=(const EGLContext&) = delete;

    // Make this context current on the calling thread.
    // Must be called before any OpenGL ES commands.
    void make_current();

    // Swap the back buffer to front, then page-flip to show it on screen.
    // Blocks until the previous page-flip completes (vblank synchronization)
    // to prevent tearing and GPU oversubscription.
    void swap_and_flip(uint32_t crtc_id, uint32_t connector_id,
                       drmModeModeInfo* mode);

    // Dimensions of the rendering surface.
    uint32_t width()  const { return width_; }
    uint32_t height() const { return height_; }

    EGLDisplay egl_display() const { return display_; }
    ::EGLContext egl_context() const { return context_; }

private:
    int      drm_fd_;
    uint32_t width_, height_;

    gbm_device*  gbm_device_{nullptr};
    gbm_surface* gbm_surface_{nullptr};

    EGLDisplay   display_{EGL_NO_DISPLAY};
    EGLSurface   surface_{EGL_NO_SURFACE};
    ::EGLContext context_{EGL_NO_CONTEXT};

    // Double-buffering state: after each page-flip we hold a reference to
    // the BO that is currently being scanned out so we don't release it
    // back to GBM prematurely (that would corrupt the display).
    gbm_bo*  prev_bo_{nullptr};
    uint32_t prev_fb_id_{0};

    void setup_gbm();
    void setup_egl();
    uint32_t bo_to_fb(gbm_bo* bo);  // register a GBM BO as a DRM framebuffer
};
