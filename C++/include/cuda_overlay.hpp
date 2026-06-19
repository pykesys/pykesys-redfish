// cuda_overlay.hpp — CUDA/OpenGL interop overlay for the command deck
//
// This header is pure C++17 — no CUDA types, no cuda_runtime.h.
// The goal is that any .cpp file can #include this without needing nvcc.
// All CUDA-specific types are hidden behind void* and the implementation
// lives entirely in src/cuda/cuda_gl_interop.cu, compiled by nvcc.
//
// ── What this does ────────────────────────────────────────────────────────
//
// The command deck runs on a DGX system whose GPUs are simultaneously
// training ML models and driving this display.  CUDAOverlay bridges the
// two workloads: it lets a CUDA kernel write visualization data directly
// into the OpenGL texture that the renderer blends over the UI, without
// any CPU involvement in the data transfer.
//
// The zero-copy path:
//
//   Training kernel writes float[] to GPU memory
//       │
//   CUDAOverlay::update_from_device()
//       │  cudaGraphicsMapResources()
//       │  Colormap kernel maps float[]→RGBA into the GL texture
//       │  cudaGraphicsUnmapResources()
//       │
//   renderer.cpp draws the GL texture as a blended overlay
//       │
//   EGL swap → DRM page flip → display
//
// The CPU never touches the visualization data.  On an H100 with 80 GB of
// HBM3, the training job's activations never leave the GPU at all — the
// overlay is derived from them by a lightweight kernel that runs between
// training steps.
//
// ── Visualization modes ───────────────────────────────────────────────────
//
// HEATMAP       Single float[W*H] array → hot colormap (black→red→white)
// VIRIDIS       Single float[W*H] array → viridis colormap (colorblind-safe)
// PLASMA        Single float[W*H] array → plasma colormap (vibrant purple→yellow)
// TOUCH_DENSITY Accumulated gaussian splats from touch events → viridis
//               Shows where the operator has been touching over time.
// GPU_BARS      N utilization values (0–100) → vertical bar chart
//               Designed for monitoring all 8 H100s of a DGX node.
// CLEAR         Writes all-transparent pixels (disables overlay without
//               deregistering the texture).
//
// ── Threading model ───────────────────────────────────────────────────────
//
// All methods must be called from the render thread (the thread that called
// EGLContext::make_current()).  This is a hard constraint of CUDA GL interop:
// the GL texture can only be mapped for CUDA access from the same OS thread
// that owns the GL context.
//
// touch density updates are the exception: add_touch_point() may be called
// from the input thread because it only writes to a float[] density buffer
// (d_density_), NOT to the GL texture.  The GL texture write happens in
// render_touch_density(), which is always on the render thread.
// This split is safe because atomicAdd() in the splat kernel is thread-safe
// within a single CUDA stream.

#pragma once
#include <cstdint>
#include <vector>
#include <string>

class CUDAOverlay {
public:
    // Visualization modes — passed to update_* methods to select the kernel.
    enum class Mode {
        HEATMAP,        // float[W×H] [0,1] → black→red→orange→yellow→white
        VIRIDIS,        // float[W×H] [0,1] → dark-blue→teal→green→yellow (perceptually uniform)
        PLASMA,         // float[W×H] [0,1] → dark-purple→pink→orange→yellow (high contrast)
        TOUCH_DENSITY,  // render accumulated touch density (ignores data argument)
        GPU_BARS,       // N utilization values 0–100 → bar chart
        CLEAR,          // all-transparent write (no colormap)
    };

    // Construct attached to an already-created OpenGL texture.
    // Preconditions:
    //   - The GL context must be current on the calling thread (render thread).
    //   - gl_tex_id must be a valid 2D RGBA8 texture of dimensions width × height.
    //   - The CUDA device must be the same GPU as the OpenGL display GPU.
    //     On DGX systems, call set_cuda_device(detect_display_gpu()) first.
    CUDAOverlay(uint32_t gl_tex_id, int width, int height);
    ~CUDAOverlay();

    // Non-copyable: owns GPU resources.
    CUDAOverlay(const CUDAOverlay&)            = delete;
    CUDAOverlay& operator=(const CUDAOverlay&) = delete;

    // ── Data ingestion — device pointers ─────────────────────────────────
    //
    // Use these when the data is already on the GPU (e.g. output of a
    // training kernel or an NV-Link transfer).  No host↔device copy occurs.
    //
    // d_data: pointer to float array of width*height values in [0.0, 1.0]
    //         Must be on the same CUDA device as this overlay.
    // mode:   colormap to apply
    void update_from_device(const float* d_data, Mode mode = Mode::VIRIDIS);

    // ── Data ingestion — host pointers ────────────────────────────────────
    //
    // Use these when data is on the CPU (e.g. Redfish telemetry pulled over
    // the management network).  A cudaMemcpyAsync copies to device first.
    void update_from_host(const float* h_data, int count, Mode mode = Mode::VIRIDIS);

    // ── Touch density accumulation ────────────────────────────────────────
    //
    // Splat a gaussian blob centered at (norm_x, norm_y) into the density
    // accumulator.  Thread-safe: uses atomicAdd in the kernel.  Safe to call
    // from the input thread.
    //
    // norm_x, norm_y : normalized [0,1] screen coordinates
    // sigma          : gaussian standard deviation in normalized units
    //                  0.025 ≈ 2.5% of screen width ≈ 48px on a 1920px display
    void add_touch_point(float norm_x, float norm_y, float sigma = 0.025f);

    // Render the current density accumulator to the overlay texture.
    // The density is normalized to [0,1] before the viridis colormap is applied.
    // Pixels with density ≈ 0 are written as fully transparent (alpha=0) so they
    // don't occlude the UI where the operator hasn't touched.
    // Must be called from the render thread.
    void render_touch_density();

    // Reset the density accumulator to zero.  Useful when switching tasks.
    void clear_density();

    // ── GPU utilization bars ──────────────────────────────────────────────
    //
    // Renders a bar chart of GPU utilization values.
    // h_utils: array of `count` values in [0.0, 100.0]  (host pointer)
    // count  : number of bars (1–16).  For DGX H100: 8.
    //
    // Color scheme per bar:
    //   0–50%:  green   (#00CC44)
    //   50–80%: yellow  (#FFCC00)
    //   80–95%: orange  (#FF6600)
    //   95–100%: red    (#FF2222)
    //
    // The bar chart occupies the full texture width; bar labels are not
    // drawn here (no font rendering in CUDA — add them in the GL layer).
    void update_gpu_bars(const std::vector<float>& h_utils);

    // ── Diagnostics ───────────────────────────────────────────────────────

    // CUDA device index this overlay was created on.
    int cuda_device() const { return device_id_; }

    // Human-readable device name (e.g. "NVIDIA H100 SXM5").
    std::string device_name() const;

    // ── Static helpers ────────────────────────────────────────────────────

    // Find the CUDA device that is currently rendering to the OpenGL display.
    // On a DGX system with multiple GPUs, this is the GPU whose framebuffer
    // the display is connected to.
    // Returns -1 if no suitable device is found (fall back to device 0).
    static int detect_display_gpu();

    // Set the CUDA device for this process.  Call before constructing any
    // CUDAOverlay.  On DGX systems, call with detect_display_gpu() or
    // hard-code device 0 if you know which GPU drives the display.
    static void set_cuda_device(int device_id);

private:
    int      device_id_{0};
    int      width_, height_;

    // Hidden CUDA types — stored as void* to keep CUDA out of the header.
    void* cuda_resource_{nullptr};   // cudaGraphicsResource_t — registered GL texture
    void* stream_{nullptr};          // cudaStream_t — async stream for all our kernels
    void* d_density_{nullptr};       // float* — touch density accumulator on GPU
    void* d_scratch_{nullptr};       // float* — scratch buffer for device→device copies
    void* d_gpu_utils_{nullptr};     // float* — GPU utilization values on device
    void* d_max_reduction_{nullptr}; // float* — single-element max for density normalization

    // Map the GL texture for CUDA writes.
    // Returns a cudaSurfaceObject_t and a cudaArray_t (both as void*).
    void map_texture(void** surf_out, void** arr_out);
    void unmap_texture(void* surf, void* arr);

    // Ensure d_scratch_ is large enough for `bytes` bytes, reallocating if needed.
    void ensure_scratch(std::size_t bytes);
};
