// cuda_gl_interop.cu — CUDA/OpenGL interop implementation
//
// Compiled by nvcc, not g++.  Includes CUDA runtime headers that are
// not available to the rest of the codebase.
//
// ── Why this file exists ──────────────────────────────────────────────────
//
// The DGX H100 is simultaneously:
//   (a) training ML models (activations, gradients, metrics → GPU memory)
//   (b) running this command-deck display (OpenGL ES on the same GPU)
//
// The naive approach — copy metrics to CPU, send to Python, plot, upload
// as a PNG, texture it — adds 10–50ms of latency and wastes PCIe bandwidth.
//
// cudaGraphicsGLRegisterImage() lets us hand the same physical GPU memory
// to BOTH the OpenGL driver (as a texture) AND CUDA (as a surface).
// Our visualization kernels write RGBA pixels directly into the texture.
// The GL driver then reads those pixels in the same frame.
// The CPU is never involved in the data transfer.
//
// ── Memory model ─────────────────────────────────────────────────────────
//
// The GL texture lives in GPU VRAM.  cudaGraphicsMapResources() tells the
// driver to "hand over" the texture from GL's ownership to CUDA's.  While
// mapped, GL cannot read the texture (undefined behavior if it tries).
// cudaGraphicsUnmapResources() returns ownership to GL before eglSwapBuffers.
//
// This ownership handoff is why ALL overlay updates must happen BEFORE
// renderer.draw() calls glBindTexture — it's a strict ordering requirement.
//
// ── CUDA device requirement ───────────────────────────────────────────────
//
// CUDA GL interop requires the CUDA context to be on the SAME physical GPU
// as the OpenGL context.  On a DGX with 8 GPUs, the display is connected to
// ONE of them (typically GPU 0 or the GPU specified in X11/Wayland config).
// detect_display_gpu() uses the EGL/DRM device path to identify the right GPU.
// If the wrong CUDA device is set, cudaGraphicsGLRegisterImage returns
// cudaErrorInvalidDevice.

#include "cuda_overlay.hpp"
#include "colormaps.cuh"

#include <cuda_runtime.h>
#include <cuda_gl_interop.h>
#include <GLES3/gl3.h>      // for GL_TEXTURE_2D — needed by cudaGraphicsGLRegisterImage

#include <cstring>
#include <cstdio>
#include <stdexcept>
#include <string>
#include <algorithm>

// ── Error checking macros ─────────────────────────────────────────────────────
//
// CUDA API functions return cudaError_t.  We wrap every call so that errors
// produce a human-readable message with file + line rather than a silent wrong
// result.  In a shipping binary you might demote some checks to warnings, but
// for a command-deck application correctness matters more than speed.
#define CUDA_CHECK(call) do {                                                \
    cudaError_t _err = (call);                                               \
    if (_err != cudaSuccess) {                                               \
        char _msg[256];                                                      \
        snprintf(_msg, sizeof(_msg),                                         \
                 "CUDA error at %s:%d — %s: %s",                            \
                 __FILE__, __LINE__, #call,                                  \
                 cudaGetErrorString(_err));                                  \
        throw std::runtime_error(_msg);                                      \
    }                                                                        \
} while(0)

// ── Thread/block geometry ─────────────────────────────────────────────────────
//
// 16×16 = 256 threads per block is the standard starting point for 2D image
// processing kernels.  It fits well within the 1024-thread warp-multiple limit
// and gives good occupancy on H100 (which has 128 CUDA cores per SM).
// For the 1920×1080 display: gridDim = (120, 68) = 8,160 blocks × 256 = 2,088,960
// threads — each handling exactly one pixel.
static constexpr int BLK = 16;

// ── Kernel: colormap to surface ───────────────────────────────────────────────
//
// Reads one float per pixel from d_data, applies the selected colormap,
// and writes the result as uchar4 RGBA into the CUDA surface object that
// maps the GL overlay texture.
//
// The output alpha channel is set to 255 (fully opaque) so the GL blend
// equation blends based on the u_alpha uniform in the texture shader —
// the renderer can fade the overlay without this kernel knowing about it.
enum class ColormapType { HOT, VIRIDIS, PLASMA };

__global__ void colormap_kernel(cudaSurfaceObject_t surf,
                                const float*        d_data,
                                int width, int height,
                                ColormapType        cmap)
{
    const int x = blockIdx.x * blockDim.x + threadIdx.x;
    const int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= width || y >= height) return;

    const float v = d_data[y * width + x];

    uchar4 pixel;
    switch (cmap) {
    case ColormapType::HOT:    pixel = colormap_hot(v);     break;
    case ColormapType::PLASMA: pixel = colormap_plasma(v);  break;
    default:                   pixel = colormap_viridis(v); break;
    }

    // surf2Dwrite expects the byte offset in the x dimension, not the pixel index.
    // For RGBA8 (4 bytes per pixel), byte_offset_x = x * 4.
    surf2Dwrite(pixel, surf, x * static_cast<int>(sizeof(uchar4)), y);
}

// ── Kernel: clear surface to transparent ─────────────────────────────────────
__global__ void clear_kernel(cudaSurfaceObject_t surf, int width, int height)
{
    const int x = blockIdx.x * blockDim.x + threadIdx.x;
    const int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= width || y >= height) return;
    surf2Dwrite(make_uchar4(0, 0, 0, 0), surf,
                x * static_cast<int>(sizeof(uchar4)), y);
}

// ── Kernel: gaussian splat into density buffer ────────────────────────────────
//
// Adds a soft gaussian blob centered at (cx_norm, cy_norm) to the float
// density buffer.  Uses atomicAdd so multiple simultaneous touch points from
// different CUDA blocks don't race.
//
// The gaussian is truncated at 3σ for performance — beyond 3σ the contribution
// is < 1% of the peak, which is below 1-bit precision at 8-bit output.
__global__ void gaussian_splat_kernel(float* d_density,
                                       int width, int height,
                                       float cx_norm, float cy_norm,
                                       float sigma,   float weight)
{
    const int x = blockIdx.x * blockDim.x + threadIdx.x;
    const int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= width || y >= height) return;

    const float px = (x + 0.5f) / static_cast<float>(width);
    const float py = (y + 0.5f) / static_cast<float>(height);
    const float dx = px - cx_norm;
    const float dy = py - cy_norm;
    const float dist2 = dx*dx + dy*dy;
    const float sigma2 = sigma * sigma;

    // Skip pixels beyond 3σ — the kernel launch already bounds this via
    // the grid size, but an explicit test avoids the exp() for distant pixels.
    if (dist2 > 9.f * sigma2) return;

    const float g = weight * __expf(-dist2 / (2.f * sigma2));
    atomicAdd(&d_density[y * width + x], g);
}

// ── Kernel: find max value in density buffer (parallel reduction) ─────────────
//
// Used to normalize the density map before applying the colormap.
// A single-pass per-block reduction that writes per-block maxima into d_out.
// A second pass (host side: thrust::reduce or manual kernel) finds the global max.
//
// We use shared memory to avoid global atomics on every thread — 16×16 = 256
// threads reduce to 1 value per block using a log2-step tree.
__global__ void max_reduce_kernel(const float* d_data, float* d_out,
                                   int n)
{
    extern __shared__ float sdata[];

    const int tid = threadIdx.x;
    int idx = blockIdx.x * blockDim.x * 2 + threadIdx.x;

    // Each thread loads two elements and takes the max before the tree reduction.
    float v = 0.f;
    if (idx < n)       v = d_data[idx];
    if (idx + blockDim.x < n) v = fmaxf(v, d_data[idx + blockDim.x]);
    sdata[tid] = v;
    __syncthreads();

    // Standard parallel reduction tree.
    for (int stride = blockDim.x / 2; stride > 0; stride >>= 1) {
        if (tid < stride)
            sdata[tid] = fmaxf(sdata[tid], sdata[tid + stride]);
        __syncthreads();
    }

    if (tid == 0) d_out[blockIdx.x] = sdata[0];
}

// ── Kernel: density buffer → surface ─────────────────────────────────────────
//
// Renders the normalized density map to the GL texture using viridis.
// Pixels with density < 1% of peak are fully transparent so they don't
// occlude the UI where the operator hasn't touched.
__global__ void density_to_surface_kernel(cudaSurfaceObject_t surf,
                                           const float* d_density,
                                           int width, int height,
                                           float max_density)
{
    const int x = blockIdx.x * blockDim.x + threadIdx.x;
    const int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= width || y >= height) return;

    const float raw = d_density[y * width + x];
    const float v   = (max_density > 1e-6f) ? fminf(raw / max_density, 1.f) : 0.f;

    uchar4 pixel;
    if (v < 0.01f) {
        // Fully transparent — no touch here.
        pixel = make_uchar4(0, 0, 0, 0);
    } else {
        pixel = colormap_viridis(v);
        // Alpha scales with density so sparse areas are semi-transparent.
        pixel.w = static_cast<unsigned char>(fminf(v * 2.f, 1.f) * 220.f);
    }
    surf2Dwrite(pixel, surf, x * static_cast<int>(sizeof(uchar4)), y);
}

// ── Kernel: GPU utilization bar chart ─────────────────────────────────────────
//
// Renders a horizontal array of N vertical bars, each representing one GPU's
// utilization.  The bars are evenly spaced across the full texture width.
// A bar's height proportional to its utilization is filled; the rest is dark.
//
// Bar layout:
//   Bar i occupies columns [i * bar_w, (i+1) * bar_w - gap]
//   Bar i is filled from row [height - bar_height] to row [height - 1]
//   (the bottom of the texture = 100% utilization to match DGX dashboard convention)
__global__ void gpu_bars_kernel(cudaSurfaceObject_t surf,
                                 int width, int height,
                                 const float* d_utils,
                                 int n_gpus)
{
    const int x = blockIdx.x * blockDim.x + threadIdx.x;
    const int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= width || y >= height) return;

    // Which GPU does column x belong to?
    const float bar_w_f = static_cast<float>(width) / static_cast<float>(n_gpus);
    const int   gpu_idx = static_cast<int>(x / bar_w_f);
    if (gpu_idx >= n_gpus) {
        surf2Dwrite(make_uchar4(0,0,0,0), surf, x*4, y);
        return;
    }

    // Is x within the active bar area (leave a 2px gap between bars)?
    const int bar_left  = static_cast<int>(gpu_idx * bar_w_f) + 1;
    const int bar_right = static_cast<int>((gpu_idx + 1) * bar_w_f) - 2;
    if (x < bar_left || x > bar_right) {
        surf2Dwrite(make_uchar4(0,0,0,0), surf, x*4, y);
        return;
    }

    const float util = d_utils[gpu_idx];  // 0–100
    const float fill = util / 100.f;

    // y=0 is the top of the texture; bars grow upward from y=height-1.
    const float fill_top = (1.f - fill) * static_cast<float>(height);
    const float row_norm = static_cast<float>(y);

    uchar4 pixel;
    if (row_norm >= fill_top) {
        // Inside the bar — apply utilization colormap.
        pixel = colormap_utilization(util);
    } else {
        // Above the bar — dark background.
        pixel = make_uchar4(15, 15, 25, 180);
    }
    surf2Dwrite(pixel, surf, x * static_cast<int>(sizeof(uchar4)), y);
}

// ── CUDAOverlay implementation ────────────────────────────────────────────────

static dim3 grid2d(int w, int h) {
    return dim3((w + BLK - 1) / BLK, (h + BLK - 1) / BLK);
}
static dim3 block2d() { return dim3(BLK, BLK); }

CUDAOverlay::CUDAOverlay(uint32_t gl_tex_id, int width, int height)
    : width_(width), height_(height)
{
    // ── Select CUDA device ────────────────────────────────────────────────
    // CUDA GL interop requires the CUDA context to be on the display GPU.
    // detect_display_gpu() returns the best candidate; we set it here.
    device_id_ = detect_display_gpu();
    if (device_id_ < 0) {
        fprintf(stderr, "[CUDAOverlay] WARNING: could not detect display GPU, "
                        "using device 0.  If CUDA GL interop fails, check which "
                        "GPU is connected to the display.\n");
        device_id_ = 0;
    }
    CUDA_CHECK(cudaSetDevice(device_id_));

    cudaDeviceProp prop;
    CUDA_CHECK(cudaGetDeviceProperties(&prop, device_id_));
    printf("[CUDAOverlay] Device %d: %s  CC %d.%d  %.0f GB HBM\n",
           device_id_, prop.name,
           prop.major, prop.minor,
           prop.totalGlobalMem / 1e9);

    // ── Create async stream ───────────────────────────────────────────────
    // We use a dedicated stream so the overlay kernels don't block training
    // kernels running on the default stream.  The sync point is only at
    // cudaGraphicsUnmapResources(), which we call just before the GL draw.
    cudaStream_t s;
    CUDA_CHECK(cudaStreamCreate(&s));
    stream_ = s;

    // ── Register GL texture with CUDA ─────────────────────────────────────
    // cudaGraphicsRegisterFlagsSurfaceLoadStore: we will both read and write
    // the texture from CUDA.  If we only wrote, we could use
    // cudaGraphicsRegisterFlagsWriteDiscard for a slight performance benefit.
    cudaGraphicsResource_t res;
    CUDA_CHECK(cudaGraphicsGLRegisterImage(
        &res, gl_tex_id, GL_TEXTURE_2D,
        cudaGraphicsRegisterFlagsSurfaceLoadStore));
    cuda_resource_ = res;

    // ── Allocate GPU buffers ──────────────────────────────────────────────
    const std::size_t n = static_cast<std::size_t>(width_) * height_;

    // Density accumulator: initialized to zero, accumulates gaussian splats.
    float* d_den;
    CUDA_CHECK(cudaMalloc(&d_den, n * sizeof(float)));
    CUDA_CHECK(cudaMemset(d_den, 0, n * sizeof(float)));
    d_density_ = d_den;

    // Scratch buffer: sized lazily in ensure_scratch(), starts at full frame.
    float* d_scr;
    CUDA_CHECK(cudaMalloc(&d_scr, n * sizeof(float)));
    d_scratch_ = d_scr;

    // GPU utilization array: 16 floats max (DGX H100 SXM5 has 8 GPUs).
    float* d_util;
    CUDA_CHECK(cudaMalloc(&d_util, 16 * sizeof(float)));
    CUDA_CHECK(cudaMemset(d_util, 0, 16 * sizeof(float)));
    d_gpu_utils_ = d_util;

    // Max reduction output: one float per block for the per-block max.
    // At 1920×1080 with 256 threads/block, we need ceil(2073600/256) = 8100 blocks.
    const int n_reduce_blocks = (static_cast<int>(n) + 511) / 512;
    float* d_max;
    CUDA_CHECK(cudaMalloc(&d_max, n_reduce_blocks * sizeof(float)));
    d_max_reduction_ = d_max;
}

CUDAOverlay::~CUDAOverlay() {
    if (cuda_resource_) {
        cudaGraphicsUnregisterResource(
            static_cast<cudaGraphicsResource_t>(cuda_resource_));
    }
    if (d_density_)       cudaFree(d_density_);
    if (d_scratch_)       cudaFree(d_scratch_);
    if (d_gpu_utils_)     cudaFree(d_gpu_utils_);
    if (d_max_reduction_) cudaFree(d_max_reduction_);
    if (stream_)          cudaStreamDestroy(static_cast<cudaStream_t>(stream_));
}

void CUDAOverlay::map_texture(void** surf_out, void** arr_out) {
    auto res = static_cast<cudaGraphicsResource_t>(cuda_resource_);
    auto str = static_cast<cudaStream_t>(stream_);

    CUDA_CHECK(cudaGraphicsMapResources(1, &res, str));

    cudaArray_t arr;
    CUDA_CHECK(cudaGraphicsSubResourceGetMappedArray(&arr, res, 0, 0));

    // Create a surface object from the mapped array.
    // A surface object is a lightweight GPU handle that kernels use to
    // call surf2Dwrite/surf2Dread.  It is valid only while the resource is mapped.
    cudaResourceDesc rdesc{};
    rdesc.resType         = cudaResourceTypeArray;
    rdesc.res.array.array = arr;
    cudaSurfaceObject_t surf = 0;
    CUDA_CHECK(cudaCreateSurfaceObject(&surf, &rdesc));

    *surf_out = reinterpret_cast<void*>(surf);
    *arr_out  = arr;
}

void CUDAOverlay::unmap_texture(void* surf_void, void* /*arr*/) {
    auto surf = static_cast<cudaSurfaceObject_t>(
                    reinterpret_cast<std::uintptr_t>(surf_void));
    auto res  = static_cast<cudaGraphicsResource_t>(cuda_resource_);
    auto str  = static_cast<cudaStream_t>(stream_);

    CUDA_CHECK(cudaDestroySurfaceObject(surf));
    CUDA_CHECK(cudaGraphicsUnmapResources(1, &res, str));
    // Synchronize: GL must not read the texture until all CUDA writes are done.
    CUDA_CHECK(cudaStreamSynchronize(str));
}

void CUDAOverlay::update_from_device(const float* d_data, Mode mode) {
    void* surf_v; void* arr_v;
    map_texture(&surf_v, &arr_v);
    auto surf = static_cast<cudaSurfaceObject_t>(
                    reinterpret_cast<std::uintptr_t>(surf_v));
    auto str  = static_cast<cudaStream_t>(stream_);

    const dim3 g = grid2d(width_, height_);
    const dim3 b = block2d();

    switch (mode) {
    case Mode::HEATMAP:
        colormap_kernel<<<g, b, 0, str>>>(surf, d_data, width_, height_, ColormapType::HOT);
        break;
    case Mode::PLASMA:
        colormap_kernel<<<g, b, 0, str>>>(surf, d_data, width_, height_, ColormapType::PLASMA);
        break;
    case Mode::CLEAR:
        clear_kernel<<<g, b, 0, str>>>(surf, width_, height_);
        break;
    default:  // VIRIDIS and anything else
        colormap_kernel<<<g, b, 0, str>>>(surf, d_data, width_, height_, ColormapType::VIRIDIS);
        break;
    }

    unmap_texture(surf_v, arr_v);
}

void CUDAOverlay::update_from_host(const float* h_data, int count, Mode mode) {
    ensure_scratch(static_cast<std::size_t>(count) * sizeof(float));
    auto str = static_cast<cudaStream_t>(stream_);
    CUDA_CHECK(cudaMemcpyAsync(d_scratch_, h_data,
                               static_cast<std::size_t>(count) * sizeof(float),
                               cudaMemcpyHostToDevice, str));
    update_from_device(static_cast<float*>(d_scratch_), mode);
}

void CUDAOverlay::add_touch_point(float norm_x, float norm_y, float sigma) {
    auto str = static_cast<cudaStream_t>(stream_);
    // Bound the launch grid to a (6σ × 6σ) window around the touch point.
    // Beyond 3σ the gaussian contribution is negligible and we save time
    // by not launching threads that will immediately return.
    const int window_px = static_cast<int>(sigma * 6.f * width_) + 1;
    const int gx = (window_px + BLK - 1) / BLK;
    const int cx_px = static_cast<int>(norm_x * width_);
    const int cy_px = static_cast<int>(norm_y * height_);

    // We launch a grid centered on the touch point by passing the offset
    // into the density buffer explicitly.  Simpler than a custom launch
    // with thread offset arithmetic.
    // For brevity, launch over the full texture and let the kernel skip
    // out-of-range pixels.  At 1080p this is 8,100 blocks — negligible for H100.
    gaussian_splat_kernel<<<grid2d(width_, height_), block2d(), 0, str>>>(
        static_cast<float*>(d_density_),
        width_, height_,
        norm_x, norm_y,
        sigma,
        1.0f  // weight: can make this pressure-dependent later
    );
    (void)window_px; (void)gx; (void)cx_px; (void)cy_px;
}

void CUDAOverlay::render_touch_density() {
    auto str = static_cast<cudaStream_t>(stream_);
    const int n = width_ * height_;

    // ── Find max density value (for normalization) ─────────────────────────
    // We use a two-pass reduction: first per-block maxima, then a tiny
    // host-side max over the block results.
    const int n_blocks = (n + 511) / 512;
    max_reduce_kernel<<<n_blocks, 256, 256 * sizeof(float), str>>>(
        static_cast<float*>(d_density_),
        static_cast<float*>(d_max_reduction_),
        n);

    // Copy block maxima to host and find global max.
    std::vector<float> h_maxes(static_cast<std::size_t>(n_blocks));
    CUDA_CHECK(cudaMemcpyAsync(h_maxes.data(),
                               d_max_reduction_,
                               static_cast<std::size_t>(n_blocks) * sizeof(float),
                               cudaMemcpyDeviceToHost, str));
    CUDA_CHECK(cudaStreamSynchronize(str));
    const float max_val = *std::max_element(h_maxes.begin(), h_maxes.end());

    // ── Render to surface ─────────────────────────────────────────────────
    void* surf_v; void* arr_v;
    map_texture(&surf_v, &arr_v);
    auto surf = static_cast<cudaSurfaceObject_t>(
                    reinterpret_cast<std::uintptr_t>(surf_v));

    density_to_surface_kernel<<<grid2d(width_, height_), block2d(), 0, str>>>(
        surf,
        static_cast<float*>(d_density_),
        width_, height_,
        max_val);

    unmap_texture(surf_v, arr_v);
}

void CUDAOverlay::clear_density() {
    auto str = static_cast<cudaStream_t>(stream_);
    CUDA_CHECK(cudaMemsetAsync(d_density_, 0,
                               static_cast<std::size_t>(width_) * height_ * sizeof(float),
                               str));
    CUDA_CHECK(cudaStreamSynchronize(str));
}

void CUDAOverlay::update_gpu_bars(const std::vector<float>& h_utils) {
    const int count = static_cast<int>(h_utils.size());
    if (count == 0 || count > 16) return;

    auto str = static_cast<cudaStream_t>(stream_);
    CUDA_CHECK(cudaMemcpyAsync(d_gpu_utils_, h_utils.data(),
                               static_cast<std::size_t>(count) * sizeof(float),
                               cudaMemcpyHostToDevice, str));

    void* surf_v; void* arr_v;
    map_texture(&surf_v, &arr_v);
    auto surf = static_cast<cudaSurfaceObject_t>(
                    reinterpret_cast<std::uintptr_t>(surf_v));

    gpu_bars_kernel<<<grid2d(width_, height_), block2d(), 0, str>>>(
        surf, width_, height_,
        static_cast<float*>(d_gpu_utils_), count);

    unmap_texture(surf_v, arr_v);
}

std::string CUDAOverlay::device_name() const {
    cudaDeviceProp prop;
    if (cudaGetDeviceProperties(&prop, device_id_) == cudaSuccess)
        return std::string(prop.name);
    return "(unknown)";
}

void CUDAOverlay::ensure_scratch(std::size_t bytes) {
    // Lazy realloc: if the existing scratch is large enough, do nothing.
    // If not, free and reallocate.  We never shrink — worst-case we hold
    // max(all_update_sizes) bytes, which for a 1080p float frame is 8 MB.
    const std::size_t current = static_cast<std::size_t>(width_) * height_ * sizeof(float);
    if (bytes <= current) return;  // already big enough
    CUDA_CHECK(cudaFree(d_scratch_));
    CUDA_CHECK(cudaMalloc(&d_scratch_, bytes));
}

// ── Static helpers ────────────────────────────────────────────────────────────

int CUDAOverlay::detect_display_gpu() {
    // Strategy: iterate CUDA devices and find the one whose PCI bus ID
    // matches the DRM device that OpenGL is using.
    //
    // On DGX systems, /sys/class/drm/card0/device/uevent contains the PCI ID.
    // We read that and compare with cudaDeviceGetPCIBusId().
    //
    // This is best-effort: if we can't determine the PCI ID, return device 0
    // and let the caller decide whether to trust it.

    // Read PCI ID of the DRM device OpenGL is using.
    FILE* f = fopen("/sys/class/drm/card0/device/uevent", "r");
    if (!f) {
        // card0 doesn't exist — try renderD128 (another common path on DGX).
        f = fopen("/sys/bus/pci/devices/0000:00:02.0/uevent", "r");
        if (!f) return 0;  // give up, use device 0
    }

    char drm_pci_id[64] = {};
    char line[256];
    while (fgets(line, sizeof(line), f)) {
        // Look for "PCI_ID=10DE:XXXX" (NVIDIA vendor ID is 0x10DE)
        if (strncmp(line, "PCI_SLOT_NAME=", 14) == 0) {
            // PCI_SLOT_NAME=0000:0a:00.0  →  domain:bus:device.function
            strncpy(drm_pci_id, line + 14, sizeof(drm_pci_id) - 1);
            // Strip trailing newline
            const auto len = strlen(drm_pci_id);
            if (len > 0 && drm_pci_id[len-1] == '\n') drm_pci_id[len-1] = '\0';
            break;
        }
    }
    fclose(f);

    if (drm_pci_id[0] == '\0') return 0;

    // Compare with each CUDA device's PCI bus ID.
    int device_count = 0;
    if (cudaGetDeviceCount(&device_count) != cudaSuccess) return 0;

    for (int d = 0; d < device_count; ++d) {
        char cuda_pci_id[64] = {};
        // cudaDeviceGetPCIBusId returns "0000:0a:00.0" format — same as DRM.
        if (cudaDeviceGetPCIBusId(cuda_pci_id, sizeof(cuda_pci_id), d) != cudaSuccess)
            continue;
        if (strcmp(cuda_pci_id, drm_pci_id) == 0) {
            printf("[CUDAOverlay] Display GPU detected: device %d (%s)\n",
                   d, drm_pci_id);
            return d;
        }
    }

    // No match found — this can happen on DGX if the display is on an
    // integrated GPU or a GPU not enumerated by CUDA.  Fall back to 0.
    fprintf(stderr, "[CUDAOverlay] Could not match DRM PCI ID '%s' to a CUDA device.  "
                    "Falling back to device 0.\n", drm_pci_id);
    return 0;
}

void CUDAOverlay::set_cuda_device(int device_id) {
    CUDA_CHECK(cudaSetDevice(device_id));
}

// ── C linkage shim — called from renderer.cpp inside #ifdef HAVE_CUDA ─────────
//
// renderer.cpp is compiled by g++ (not nvcc) so it can't call CUDA API
// directly.  We expose this plain-C function as the bridge.
// The function signature matches the `extern void` declaration in renderer.cpp.
extern "C" void cuda_update_texture(uint32_t /*tex_id*/,
                                     float*    /*d_data*/,
                                     int       /*w*/,
                                     int       /*h*/)
{
    // The renderer.cpp shim is retained for backward compatibility but the
    // preferred path is to call CUDAOverlay::update_from_device() directly
    // from main.cpp, which has full access to the CUDAOverlay instance.
    // This stub prevents a linker error if renderer.cpp calls it.
}
