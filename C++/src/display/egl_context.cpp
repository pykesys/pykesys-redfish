// display/egl_context.cpp — EGL + GBM hardware-accelerated rendering context
//
// See display/egl_context.hpp for the conceptual pipeline description.
// This file wires together GBM surface creation, EGL initialisation,
// and the page-flip loop that presents rendered frames to the display.

#include "display/egl_context.hpp"
#include <EGL/eglext.h>
#include <cstring>
#include <stdexcept>
#include <string>

// Retrieve an EGL extension function pointer.
// EGL functions beyond the core 1.4 spec must be loaded at runtime with
// eglGetProcAddress — they are not in the shared library's export table.
template<typename T>
static T egl_proc(const char* name) {
    auto fn = reinterpret_cast<T>(eglGetProcAddress(name));
    if (!fn)
        throw std::runtime_error(std::string("eglGetProcAddress failed: ") + name);
    return fn;
}

EGLContext::EGLContext(int drm_fd, uint32_t width, uint32_t height)
    : drm_fd_(drm_fd), width_(width), height_(height)
{
    setup_gbm();
    setup_egl();
}

EGLContext::~EGLContext() {
    // Release resources in reverse order of creation.
    if (prev_bo_) {
        drmModeRmFB(drm_fd_, prev_fb_id_);
        gbm_surface_release_buffer(gbm_surface_, prev_bo_);
    }
    if (context_ != EGL_NO_CONTEXT) eglDestroyContext(display_, context_);
    if (surface_ != EGL_NO_SURFACE) eglDestroySurface(display_, surface_);
    if (display_ != EGL_NO_DISPLAY) eglTerminate(display_);
    if (gbm_surface_) gbm_surface_destroy(gbm_surface_);
    if (gbm_device_)  gbm_device_destroy(gbm_device_);
}

void EGLContext::make_current() {
    if (!eglMakeCurrent(display_, surface_, surface_, context_))
        throw std::runtime_error("eglMakeCurrent failed");
}

void EGLContext::swap_and_flip(uint32_t crtc_id, uint32_t connector_id,
                                drmModeModeInfo* mode)
{
    // Step 1: Ask EGL to swap the back buffer to front.
    // Internally this tells GBM the current back buffer is done rendering.
    eglSwapBuffers(display_, surface_);

    // Step 2: Grab the newly presented front buffer as a GBM BO.
    // gbm_surface_lock_front_buffer returns the BO that eglSwapBuffers
    // just promoted — it's ready for display hardware to scan out.
    auto* bo = gbm_surface_lock_front_buffer(gbm_surface_);
    if (!bo) throw std::runtime_error("gbm_surface_lock_front_buffer failed");

    const uint32_t fb_id = bo_to_fb(bo);

    // Step 3: Queue a page flip.
    // The display hardware will switch to fb_id at the next vertical blank.
    // DRM_MODE_PAGE_FLIP_EVENT asks the kernel to send us a drm event when
    // the flip completes so we know when to release the old BO.
    drmModePageFlip(drm_fd_, crtc_id, fb_id, DRM_MODE_PAGE_FLIP_EVENT, nullptr);

    // Step 4: Wait for the flip to complete.
    // We block here to avoid overwriting a BO that the display is still
    // scanning out.  This is vblank synchronization — it naturally caps
    // the render loop at the display's refresh rate (typically 60 Hz).
    fd_set fds;
    FD_ZERO(&fds);
    FD_SET(drm_fd_, &fds);
    select(drm_fd_ + 1, &fds, nullptr, nullptr, nullptr);

    // Drain the DRM event (page_flip_handler is called here).
    // We use a no-op handler — we just need to drain the event fd.
    drmEventContext evctx{};
    evctx.version          = 2;
    evctx.page_flip_handler = [](int, unsigned, unsigned, unsigned, void*){};
    drmHandleEvent(drm_fd_, &evctx);

    // Step 5: Release the previous BO now that the display has moved on.
    if (prev_bo_) {
        drmModeRmFB(drm_fd_, prev_fb_id_);
        gbm_surface_release_buffer(gbm_surface_, prev_bo_);
    }
    prev_bo_    = bo;
    prev_fb_id_ = fb_id;
}

void EGLContext::setup_gbm() {
    // Create a GBM device from the DRM fd.  GBM is the buffer allocator;
    // it knows which memory alignment and tiling formats the GPU needs.
    gbm_device_ = gbm_create_device(drm_fd_);
    if (!gbm_device_)
        throw std::runtime_error("gbm_create_device failed");

    // Create a GBM surface.  This is the "native window" that EGL will
    // attach to.  GBM_BO_USE_SCANOUT means the buffers must be in a format
    // the display controller can read directly — this constrains tiling.
    // GBM_BO_USE_RENDERING means the GPU can render into them.
    gbm_surface_ = gbm_surface_create(
        gbm_device_, width_, height_,
        GBM_FORMAT_XRGB8888,
        GBM_BO_USE_SCANOUT | GBM_BO_USE_RENDERING);
    if (!gbm_surface_)
        throw std::runtime_error("gbm_surface_create failed");
}

void EGLContext::setup_egl() {
    // Use the EGL_KHR_platform_gbm extension to create an EGLDisplay from
    // our GBM device.  This ties EGL to our specific GPU/DRM setup.
    auto eglGetPlatformDisplayEXT =
        egl_proc<PFNEGLGETPLATFORMDISPLAYEXTPROC>("eglGetPlatformDisplayEXT");
    display_ = eglGetPlatformDisplayEXT(EGL_PLATFORM_GBM_KHR,
                                        gbm_device_, nullptr);
    if (display_ == EGL_NO_DISPLAY)
        throw std::runtime_error("eglGetPlatformDisplayEXT returned NO_DISPLAY");

    EGLint major, minor;
    if (!eglInitialize(display_, &major, &minor))
        throw std::runtime_error("eglInitialize failed");

    // Request an RGBA8 surface with depth and OpenGL ES 3 rendering.
    const EGLint config_attrs[] = {
        EGL_RED_SIZE,         8,
        EGL_GREEN_SIZE,       8,
        EGL_BLUE_SIZE,        8,
        EGL_ALPHA_SIZE,       8,
        EGL_DEPTH_SIZE,      24,
        EGL_STENCIL_SIZE,     8,
        EGL_RENDERABLE_TYPE,  EGL_OPENGL_ES3_BIT,
        EGL_SURFACE_TYPE,     EGL_WINDOW_BIT,
        EGL_NONE
    };
    EGLConfig config;
    EGLint    n_configs;
    if (!eglChooseConfig(display_, config_attrs, &config, 1, &n_configs)
        || n_configs == 0)
        throw std::runtime_error("eglChooseConfig found no matching config");

    // Create an OpenGL ES 3 context.
    eglBindAPI(EGL_OPENGL_ES_API);
    const EGLint ctx_attrs[] = { EGL_CONTEXT_CLIENT_VERSION, 3, EGL_NONE };
    context_ = eglCreateContext(display_, config, EGL_NO_CONTEXT, ctx_attrs);
    if (context_ == EGL_NO_CONTEXT)
        throw std::runtime_error("eglCreateContext failed");

    // Create a window surface from the GBM surface.
    // EGL will allocate the actual GBM BOs internally.
    surface_ = eglCreateWindowSurface(
        display_, config,
        reinterpret_cast<EGLNativeWindowType>(gbm_surface_), nullptr);
    if (surface_ == EGL_NO_SURFACE)
        throw std::runtime_error("eglCreateWindowSurface failed");

    // Make current so setup code (shader compilation, buffer creation)
    // can use OpenGL ES immediately.
    make_current();
}

uint32_t EGLContext::bo_to_fb(gbm_bo* bo) {
    // Convert a GBM BO to a DRM framebuffer ID so the display hardware
    // knows how to scan it out.  drmModeAddFB2 supports multi-planar formats;
    // we use single-plane XRGB8888 here.
    const uint32_t handles[4] = { gbm_bo_get_handle(bo).u32 };
    const uint32_t strides[4] = { gbm_bo_get_stride(bo) };
    const uint32_t offsets[4] = { 0 };
    uint32_t fb_id = 0;

    if (drmModeAddFB2(drm_fd_, width_, height_, DRM_FORMAT_XRGB8888,
                      handles, strides, offsets, &fb_id, 0) < 0)
        throw std::runtime_error("drmModeAddFB2 failed");

    return fb_id;
}
