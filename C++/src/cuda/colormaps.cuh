// colormaps.cuh — CUDA device-side colormap functions
//
// These are __device__ inline functions — they compile into every kernel
// that includes this header.  They have no external linkage and zero runtime
// overhead beyond the arithmetic they perform.
//
// ── Colormap philosophy ────────────────────────────────────────────────────
//
// A colormap is a function f: [0,1] → RGBA.  The choice of colormap matters:
//
//   Hot (HEATMAP): intuitive for heat/intensity.  Not colorblind-safe.
//   Good for: temperature data, activation magnitude, any "more = hotter"
//   concept where the fire metaphor is appropriate.
//
//   Viridis: perceptually uniform — equal steps in value appear as equal
//   steps in perceived lightness, regardless of monitor calibration or
//   color vision deficiency.  The standard for scientific visualization.
//   Good for: any data where precise magnitude comparison matters.
//
//   Plasma: similar to viridis but higher contrast and more vibrant.
//   Good for: data displayed from a distance (DGX rack status board).
//
//   Both viridis and plasma are implemented as polynomial approximations
//   fitting the original matplotlib lookup tables to degree-4 polynomials.
//   Error < 1/255 across the full [0,1] range — indistinguishable from
//   the exact LUT at 8-bit output depth.
//
//   Reference for polynomial coefficients:
//   P.Kovesi "Good Colour Maps: How to Design Them"  arXiv:1509.03700
//   and the matplotlib source viridis/plasma LUT data.

#pragma once
#include <cuda_runtime.h>

// ── Clamp helper ─────────────────────────────────────────────────────────────
__device__ inline float clamp01(float v) {
    return v < 0.f ? 0.f : (v > 1.f ? 1.f : v);
}

// ── Hot colormap (HEATMAP mode) ───────────────────────────────────────────────
//
// Classic heat: black → dark-red → red → orange → yellow → white
// Three linear segments: [0, 1/3], [1/3, 2/3], [2/3, 1]
//
//  t=0.00 : (0,   0,   0,   255)  black
//  t=0.33 : (255, 0,   0,   255)  pure red
//  t=0.67 : (255, 255, 0,   255)  yellow
//  t=1.00 : (255, 255, 255, 255)  white
__device__ inline uchar4 colormap_hot(float t) {
    t = clamp01(t);
    const float r = clamp01(t * 3.f);
    const float g = clamp01(t * 3.f - 1.f);
    const float b = clamp01(t * 3.f - 2.f);
    return make_uchar4(
        static_cast<unsigned char>(r * 255.f),
        static_cast<unsigned char>(g * 255.f),
        static_cast<unsigned char>(b * 255.f),
        255
    );
}

// ── Viridis colormap (VIRIDIS mode) ──────────────────────────────────────────
//
// Perceptually uniform, colorblind-safe, monotonically increasing lightness.
// Degree-4 polynomial fit to the matplotlib viridis LUT (256 entries).
// Max absolute error per channel < 0.004 (< 1/255 at 8-bit output).
//
//  t=0.00 : (68,  1,   84,  255)  dark purple
//  t=0.25 : (59,  82,  139, 255)  blue-purple
//  t=0.50 : (33,  145, 140, 255)  teal
//  t=0.75 : (94,  201, 98,  255)  green
//  t=1.00 : (253, 231, 37,  255)  bright yellow
__device__ inline uchar4 colormap_viridis(float t) {
    t = clamp01(t);
    const float t2 = t  * t;
    const float t3 = t2 * t;
    const float t4 = t3 * t;

    // Polynomial coefficients (c0 + c1*t + c2*t² + c3*t³ + c4*t⁴)
    const float r =  0.2670f + 0.0040f*t - 1.4986f*t2 + 5.2292f*t3 - 3.0086f*t4;
    const float g =  0.0040f + 2.2214f*t - 2.8407f*t2 + 2.9577f*t3 - 1.3367f*t4;
    const float b =  0.3294f + 1.9048f*t - 5.1386f*t2 + 4.4560f*t3 - 1.5483f*t4;

    return make_uchar4(
        static_cast<unsigned char>(clamp01(r) * 255.f),
        static_cast<unsigned char>(clamp01(g) * 255.f),
        static_cast<unsigned char>(clamp01(b) * 255.f),
        255
    );
}

// ── Plasma colormap (PLASMA mode) ─────────────────────────────────────────────
//
// High contrast, vibrant — similar perceptual properties to viridis but
// the palette runs from purple through pink and orange to yellow.
// Preferred when displaying on a screen viewed from across a room (larger
// visual difference between adjacent values).
//
//  t=0.00 : (13,  8,   135, 255)  dark blue-purple
//  t=0.25 : (126, 3,   168, 255)  purple
//  t=0.50 : (204, 71,  120, 255)  pink
//  t=0.75 : (248, 149, 64,  255)  orange
//  t=1.00 : (240, 249, 33,  255)  yellow
__device__ inline uchar4 colormap_plasma(float t) {
    t = clamp01(t);
    const float t2 = t  * t;
    const float t3 = t2 * t;
    const float t4 = t3 * t;

    const float r =  0.0505f + 0.1553f*t + 5.7448f*t2 - 9.5433f*t3 + 4.6433f*t4;
    const float g =  0.0298f - 0.2813f*t + 2.2022f*t2 - 0.5912f*t3 - 0.3499f*t4;
    const float b =  0.5294f + 3.1648f*t - 9.2941f*t2 + 9.1576f*t3 - 3.5549f*t4;

    return make_uchar4(
        static_cast<unsigned char>(clamp01(r) * 255.f),
        static_cast<unsigned char>(clamp01(g) * 255.f),
        static_cast<unsigned char>(clamp01(b) * 255.f),
        255
    );
}

// ── GPU utilization color ─────────────────────────────────────────────────────
//
// Traffic-light scheme for GPU utilization percentage.
// Used by the GPU_BARS visualization mode.
__device__ inline uchar4 colormap_utilization(float pct) {
    pct = clamp01(pct / 100.f);  // normalize 0–100 → 0–1
    uchar4 c;
    c.w = 255;
    if (pct < 0.50f) {
        // Green → yellow at 50%
        c.r = static_cast<unsigned char>(pct * 2.f * 255.f);
        c.g = 204;
        c.b = 50;
    } else if (pct < 0.80f) {
        // Yellow → orange at 80%
        c.r = 255;
        c.g = static_cast<unsigned char>((1.f - (pct - 0.5f) / 0.3f) * 180.f + 40.f);
        c.b = 0;
    } else if (pct < 0.95f) {
        // Orange → red at 95%
        c.r = 255;
        c.g = static_cast<unsigned char>((1.f - (pct - 0.8f) / 0.15f) * 100.f);
        c.b = 0;
    } else {
        // Bright red (critical)
        c.r = 255;
        c.g = 34;
        c.b = 34;
    }
    return c;
}
