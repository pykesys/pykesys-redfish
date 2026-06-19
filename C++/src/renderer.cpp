// renderer.cpp — OpenGL ES 3 rendering: touch surface, trails, ripples
//
// Rendering layers per active finger (back to front):
//   1. Comet trail     — fading history of last 16 positions
//   2. Pressure halo   — outer ring whose radius scales with pressure
//   3. Contact ellipse — sized from ABS_MT_TOUCH_MAJOR/MINOR data
//   4. Ripple burst    — expanding ring on DOWN, fades in 350ms
//
// All 10 slots are rendered simultaneously, each with a unique color from
// SLOT_COLORS[] so fingers are identifiable at a glance across the screen.
// Slots that are not active are simply skipped.

#include "renderer.hpp"
#include <GLES3/gl3.h>
#include <stdexcept>
#include <cstdio>
#include <cstring>
#include <cmath>
#include <chrono>

// ── GLSL shaders ──────────────────────────────────────────────────────────────

// Solid-color geometry: maps normalized [0,1] screen coords to clip space.
// Y is flipped because our touch origin (top-left) is opposite to GL's (bottom-left).
static const char* VERT_SOLID = R"GLSL(
#version 300 es
layout(location = 0) in vec2 a_pos;
uniform vec4 u_color;
out vec4 v_color;
void main() {
    gl_Position = vec4(a_pos.x * 2.0 - 1.0,
                       -(a_pos.y * 2.0 - 1.0),
                       0.0, 1.0);
    v_color = u_color;
}
)GLSL";

static const char* FRAG_SOLID = R"GLSL(
#version 300 es
precision mediump float;
in  vec4 v_color;
out vec4 frag_color;
void main() { frag_color = v_color; }
)GLSL";

// Textured quad for the CUDA ML overlay.
static const char* VERT_TEXTURE = R"GLSL(
#version 300 es
layout(location = 0) in vec2 a_pos;
layout(location = 1) in vec2 a_uv;
out vec2 v_uv;
void main() {
    gl_Position = vec4(a_pos.x * 2.0 - 1.0,
                       -(a_pos.y * 2.0 - 1.0),
                       0.0, 1.0);
    v_uv = a_uv;
}
)GLSL";

static const char* FRAG_TEXTURE = R"GLSL(
#version 300 es
precision mediump float;
uniform sampler2D u_tex;
uniform float     u_alpha;
in  vec2 v_uv;
out vec4 frag_color;
void main() {
    vec4 c = texture(u_tex, v_uv);
    frag_color = vec4(c.rgb, c.a * u_alpha);
}
)GLSL";

// ── Shader compilation helpers ────────────────────────────────────────────────

static uint32_t compile_shader(GLenum type, const char* src) {
    uint32_t sh = glCreateShader(type);
    glShaderSource(sh, 1, &src, nullptr);
    glCompileShader(sh);
    GLint ok;
    glGetShaderiv(sh, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char log[512]; glGetShaderInfoLog(sh, sizeof(log), nullptr, log);
        glDeleteShader(sh);
        throw std::runtime_error(std::string("Shader compile error: ") + log);
    }
    return sh;
}

static uint32_t link_program(const char* vs, const char* fs) {
    uint32_t v = compile_shader(GL_VERTEX_SHADER,   vs);
    uint32_t f = compile_shader(GL_FRAGMENT_SHADER, fs);
    uint32_t p = glCreateProgram();
    glAttachShader(p, v); glAttachShader(p, f);
    glLinkProgram(p);
    glDeleteShader(v);    glDeleteShader(f);
    GLint ok; glGetProgramiv(p, GL_LINK_STATUS, &ok);
    if (!ok) {
        char log[512]; glGetProgramInfoLog(p, sizeof(log), nullptr, log);
        glDeleteProgram(p);
        throw std::runtime_error(std::string("Program link error: ") + log);
    }
    return p;
}

// ── Color unpacking helper ────────────────────────────────────────────────────
// 0xRRGGBBAA → four floats in [0,1]
static void unpack_color(uint32_t c, float& r, float& g, float& b, float& a) {
    r = ((c >> 24) & 0xFF) / 255.f;
    g = ((c >> 16) & 0xFF) / 255.f;
    b = ((c >>  8) & 0xFF) / 255.f;
    a = ( c        & 0xFF) / 255.f;
}

// ── Renderer ──────────────────────────────────────────────────────────────────

Renderer::Renderer(EGLContext& ctx, uint32_t width, uint32_t height)
    : ctx_(ctx), width_(width), height_(height)
{
    init_shaders();
    init_buffers();
    init_overlay_texture();
    glEnable(GL_BLEND);
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
}

Renderer::~Renderer() {
    if (prog_solid_)   glDeleteProgram(prog_solid_);
    if (prog_texture_) glDeleteProgram(prog_texture_);
    if (overlay_tex_)  glDeleteTextures(1, &overlay_tex_);
    if (vbo_)          glDeleteBuffers(1, &vbo_);
    if (vao_)          glDeleteVertexArrays(1, &vao_);
}

void Renderer::draw(const std::vector<TouchIndicator>& indicators, TimePoint now) {
    glClearColor(0.04f, 0.04f, 0.08f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT);
    glViewport(0, 0, static_cast<GLsizei>(width_), static_cast<GLsizei>(height_));

    if (overlay_visible_) draw_overlay();

    int active_count = 0;
    for (const auto& ind : indicators) {
        if (!ind.active) continue;
        ++active_count;
        draw_finger(ind, now);
    }

    draw_finger_count(active_count);
}

// ── draw_finger: all layers for one finger ────────────────────────────────────

void Renderer::draw_finger(const TouchIndicator& ind, TimePoint now) {
    const uint32_t col = ind.color();

    // Layer 1: comet trail (oldest to newest, fading in)
    draw_trail(ind);

    // Layer 2: pressure halo — an outer ring whose size scales with pressure.
    // When pressure is 0 (no data from device), the halo radius matches the
    // contact ellipse, so it's invisible.  When pressure > 0 it expands.
    if (ind.pressure > 0.01f) {
        const float halo_r = ind.major_radius * (1.f + ind.pressure * 0.6f);
        // Semi-transparent version of the slot color for the halo ring.
        const uint32_t halo_color = (col & 0xFFFFFF00u) | 0x44u;
        draw_ring(ind.x, ind.y,
                  ind.major_radius * 1.05f, halo_r,
                  halo_color, 0.5f + ind.pressure * 0.3f);
    }

    // Layer 3: contact ellipse — the main finger footprint.
    // Uses TOUCH_MAJOR and TOUCH_MINOR for realistic shape; falls back to
    // a default radius when the device doesn't report contact size.
    draw_ellipse(ind.x, ind.y, ind.major_radius, ind.minor_radius, col);

    // Bright centre dot — a small high-contrast point for precision reference.
    const float dot_r = ind.major_radius * 0.2f;
    const uint32_t white = 0xFFFFFFCCu;
    draw_ellipse(ind.x, ind.y, dot_r, dot_r, white, 12);

    // Layer 4: ripple burst on DOWN
    const float rp = ind.ripple_progress(now);
    if (rp >= 0.f) {
        // Ring expands from 0 to 3× the contact radius as rp goes 0→1.
        // Alpha fades from 0.8 to 0 so it vanishes as it expands.
        const float outer  = ind.major_radius * (1.f + rp * 3.f);
        const float inner  = outer * 0.85f;
        const float alpha  = (1.f - rp) * 0.8f;
        draw_ring(ind.x, ind.y, inner, outer, col, alpha);
    }
}

// ── draw_trail ────────────────────────────────────────────────────────────────

void Renderer::draw_trail(const TouchIndicator& ind) {
    // Draw trail_count – 1 line segments, from oldest to newest.
    // Alpha fades from 0 (oldest) to ~0.5 (one step behind current).
    // The current position is not included here — the ellipse covers it.
    if (ind.trail_count < 2) return;

    const uint32_t col = ind.color();
    float r, g, b, a_ignored;
    unpack_color(col, r, g, b, a_ignored);

    // We draw each segment as a thin elongated ellipse (a "blob") rather
    // than a GL_LINES call, because GL ES 3 line width > 1.0 is not reliably
    // supported.  A blob of radius trail_blob_r gives a smooth comet shape.
    const float trail_blob_r = ind.major_radius * 0.35f;

    for (int i = 0; i < ind.trail_count - 1; ++i) {
        // Index into the ring buffer, newest-first: step 0 = newest trail point.
        const int idx = (ind.trail_head - 1 - i + TouchIndicator::TRAIL_LEN)
                        % TouchIndicator::TRAIL_LEN;
        const auto& pt = ind.trail_pts[idx];

        // Alpha: full at newest, approaches 0 at oldest.
        const float alpha = 0.45f * (1.f - static_cast<float>(i)
                                          / static_cast<float>(ind.trail_count));
        const uint32_t trail_color =
            (static_cast<uint32_t>(r * 255) << 24) |
            (static_cast<uint32_t>(g * 255) << 16) |
            (static_cast<uint32_t>(b * 255) <<  8) |
             static_cast<uint32_t>(alpha * 255);

        draw_ellipse(pt.x, pt.y, trail_blob_r, trail_blob_r, trail_color, 12);
    }
}

// ── draw_finger_count badge ───────────────────────────────────────────────────
// Shows how many fingers are currently active in the top-right corner.
// Each active finger is represented by a small colored square, using the
// slot color palette.  This gives the operator immediate feedback that all
// their touches are being registered — no mystery about dropped inputs.

void Renderer::draw_finger_count(int count) {
    if (count == 0) return;

    constexpr float BADGE_SIZE  = 0.018f;  // normalized width/height per square
    constexpr float BADGE_PAD   = 0.006f;  // gap between squares
    constexpr float BADGE_TOP   = 0.012f;  // top margin
    constexpr float BADGE_RIGHT = 0.012f;  // right margin

    for (int i = 0; i < count && i < static_cast<int>(SLOT_COLORS.size()); ++i) {
        const float x = 1.f - BADGE_RIGHT - BADGE_SIZE
                        - i * (BADGE_SIZE + BADGE_PAD);
        const Rect r{x, BADGE_TOP, BADGE_SIZE, BADGE_SIZE};
        draw_rect(r, SLOT_COLORS[static_cast<std::size_t>(i)]);
    }
}

// ── Geometric primitives ──────────────────────────────────────────────────────

void Renderer::draw_rect(const Rect& r, uint32_t color) {
    const float x0 = r.x, y0 = r.y, x1 = r.x + r.w, y1 = r.y + r.h;
    const float v[] = { x0,y0, x1,y0, x0,y1, x1,y0, x1,y1, x0,y1 };
    float fr, fg, fb, fa; unpack_color(color, fr, fg, fb, fa);

    glUseProgram(prog_solid_);
    glUniform4f(glGetUniformLocation(prog_solid_, "u_color"), fr, fg, fb, fa);
    glBindVertexArray(vao_);
    glBindBuffer(GL_ARRAY_BUFFER, vbo_);
    glBufferSubData(GL_ARRAY_BUFFER, 0, sizeof(v), v);
    glDrawArrays(GL_TRIANGLES, 0, 6);
    glBindVertexArray(0);
}

void Renderer::draw_ellipse(float cx, float cy,
                             float major_r, float minor_r,
                             uint32_t color, int segments)
{
    // The display aspect ratio must correct the Y radius so that a
    // "circle" doesn't appear as a tall oval on a 16:9 screen.
    // Example: on a 1920×1080 display, aspect = 1.778.
    // A normalized radius of 0.02 in X = 38.4 pixels.
    // Without correction, 0.02 in Y = 38.4 pixels * (1920/1080) = 68 pixels.
    // With correction: Y radius = major_r * aspect → same pixel count on Y.
    const float aspect = static_cast<float>(width_) / static_cast<float>(height_);
    const float ry = minor_r * aspect;

    // Triangle fan: centre vertex + segments+1 perimeter vertices.
    // Maximum segments=40; at 40 bytes per vertex, 42 verts = 336 bytes.
    const int vcount = segments + 2;
    float verts[42 * 2]{};   // enough for 40 segments
    verts[0] = cx; verts[1] = cy;
    for (int i = 0; i <= segments; ++i) {
        const float angle = 6.28318530718f * static_cast<float>(i)
                                           / static_cast<float>(segments);
        verts[2 + i * 2 + 0] = cx + major_r * std::cos(angle);
        verts[2 + i * 2 + 1] = cy + ry      * std::sin(angle);
    }

    float fr, fg, fb, fa; unpack_color(color, fr, fg, fb, fa);
    glUseProgram(prog_solid_);
    glUniform4f(glGetUniformLocation(prog_solid_, "u_color"), fr, fg, fb, fa);
    glBindVertexArray(vao_);
    glBindBuffer(GL_ARRAY_BUFFER, vbo_);
    glBufferSubData(GL_ARRAY_BUFFER, 0,
                    static_cast<GLsizeiptr>(vcount * 2 * sizeof(float)), verts);
    glDrawArrays(GL_TRIANGLE_FAN, 0, vcount);
    glBindVertexArray(0);
}

void Renderer::draw_ring(float cx, float cy,
                          float inner_r, float outer_r,
                          uint32_t color, float alpha, int segments)
{
    // A ring is a triangle strip alternating between the inner and outer circle.
    // segments*2 + 2 vertices; each vertex = 2 floats.
    const float aspect = static_cast<float>(width_) / static_cast<float>(height_);
    const int   vcount = (segments + 1) * 2;
    float verts[84 * 2]{};  // 40 segments * 2 rings + 2 = 82 max

    for (int i = 0; i <= segments; ++i) {
        const float angle = 6.28318530718f * static_cast<float>(i)
                                           / static_cast<float>(segments);
        const float ca = std::cos(angle), sa = std::sin(angle);
        verts[i * 4 + 0] = cx + outer_r * ca;
        verts[i * 4 + 1] = cy + outer_r * sa * aspect;
        verts[i * 4 + 2] = cx + inner_r * ca;
        verts[i * 4 + 3] = cy + inner_r * sa * aspect;
    }

    float fr, fg, fb, fa_unused; unpack_color(color, fr, fg, fb, fa_unused);
    glUseProgram(prog_solid_);
    glUniform4f(glGetUniformLocation(prog_solid_, "u_color"), fr, fg, fb, alpha);
    glBindVertexArray(vao_);
    glBindBuffer(GL_ARRAY_BUFFER, vbo_);
    glBufferSubData(GL_ARRAY_BUFFER, 0,
                    static_cast<GLsizeiptr>(vcount * 2 * sizeof(float)), verts);
    glDrawArrays(GL_TRIANGLE_STRIP, 0, vcount);
    glBindVertexArray(0);
}

// ── GL initialization ─────────────────────────────────────────────────────────

void Renderer::init_shaders() {
    prog_solid_   = link_program(VERT_SOLID,   FRAG_SOLID);
    prog_texture_ = link_program(VERT_TEXTURE, FRAG_TEXTURE);
}

void Renderer::init_buffers() {
    glGenVertexArrays(1, &vao_);
    glGenBuffers(1, &vbo_);
    glBindVertexArray(vao_);
    glBindBuffer(GL_ARRAY_BUFFER, vbo_);
    // 512 vertices × 2 floats × 4 bytes = 4 KB — plenty for all per-frame geometry.
    glBufferData(GL_ARRAY_BUFFER, 512 * 2 * sizeof(float), nullptr, GL_DYNAMIC_DRAW);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 2 * sizeof(float), nullptr);
    glBindVertexArray(0);
}

void Renderer::init_overlay_texture() {
    glGenTextures(1, &overlay_tex_);
    glBindTexture(GL_TEXTURE_2D, overlay_tex_);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8,
                 static_cast<GLsizei>(width_), static_cast<GLsizei>(height_),
                 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glBindTexture(GL_TEXTURE_2D, 0);
}

void Renderer::update_ml_overlay(float* /*d_data*/) {
#ifdef HAVE_CUDA
    extern void cuda_update_texture(uint32_t, float*, int, int);
    cuda_update_texture(overlay_tex_, d_data,
                        static_cast<int>(width_), static_cast<int>(height_));
#endif
}

void Renderer::draw_overlay() {
    const float v[] = {
        0.f,0.f, 0.f,0.f,
        1.f,0.f, 1.f,0.f,
        0.f,1.f, 0.f,1.f,
        1.f,0.f, 1.f,0.f,
        1.f,1.f, 1.f,1.f,
        0.f,1.f, 0.f,1.f,
    };
    glUseProgram(prog_texture_);
    glUniform1i(glGetUniformLocation(prog_texture_, "u_tex"),   0);
    glUniform1f(glGetUniformLocation(prog_texture_, "u_alpha"), 0.6f);
    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, overlay_tex_);
    glBindVertexArray(vao_);
    glBindBuffer(GL_ARRAY_BUFFER, vbo_);
    glBufferSubData(GL_ARRAY_BUFFER, 0, sizeof(v), v);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4*sizeof(float), nullptr);
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4*sizeof(float),
                          reinterpret_cast<const void*>(2*sizeof(float)));
    glEnableVertexAttribArray(1);
    glDrawArrays(GL_TRIANGLES, 0, 6);
    glDisableVertexAttribArray(1);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 2*sizeof(float), nullptr);
    glBindVertexArray(0);
    glBindTexture(GL_TEXTURE_2D, 0);
}

//
// Coordinate convention in GL shaders:
//   Clip space: [-1, +1] in both axes, +Y up.
//   Screen space: [0, 1] in both axes, +Y down (matches touch coords).
// We convert touch coords to clip space with: clip = norm * 2.0 - 1.0
// and then flip Y: clip_y = -(norm_y * 2.0 - 1.0)

#include "renderer.hpp"
#include <GLES3/gl3.h>
#include <stdexcept>
#include <cstdio>
#include <cstring>
#include <cmath>

// ── GLSL shader sources ───────────────────────────────────────────────────────

// Solid-color vertex shader: maps normalized [0,1] screen coords to clip space.
static const char* VERT_SOLID = R"GLSL(
#version 300 es
layout(location = 0) in vec2 a_pos;   // normalized screen position [0,1]
uniform vec4 u_color;
out vec4 v_color;
void main() {
    // Convert from [0,1] to [-1,+1], flipping Y because GL's +Y is up
    // but our touch coordinate system has +Y pointing down.
    gl_Position = vec4(a_pos.x * 2.0 - 1.0,
                       -(a_pos.y * 2.0 - 1.0),
                       0.0, 1.0);
    v_color = u_color;
}
)GLSL";

static const char* FRAG_SOLID = R"GLSL(
#version 300 es
precision mediump float;
in  vec4 v_color;
out vec4 frag_color;
void main() { frag_color = v_color; }
)GLSL";

// Texture overlay vertex + fragment shaders (for the CUDA ML heatmap).
static const char* VERT_TEXTURE = R"GLSL(
#version 300 es
layout(location = 0) in vec2 a_pos;
layout(location = 1) in vec2 a_uv;
out vec2 v_uv;
void main() {
    gl_Position = vec4(a_pos.x * 2.0 - 1.0,
                       -(a_pos.y * 2.0 - 1.0),
                       0.0, 1.0);
    v_uv = a_uv;
}
)GLSL";

static const char* FRAG_TEXTURE = R"GLSL(
#version 300 es
precision mediump float;
uniform sampler2D u_tex;
uniform float     u_alpha;
in  vec2 v_uv;
out vec4 frag_color;
void main() {
    vec4 c = texture(u_tex, v_uv);
    frag_color = vec4(c.rgb, c.a * u_alpha);
}
)GLSL";

// ── Helper: compile + link a shader program ───────────────────────────────────

static uint32_t compile_shader(GLenum type, const char* src) {
    uint32_t sh = glCreateShader(type);
    glShaderSource(sh, 1, &src, nullptr);
    glCompileShader(sh);

    GLint ok;
    glGetShaderiv(sh, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char log[512];
        glGetShaderInfoLog(sh, sizeof(log), nullptr, log);
        glDeleteShader(sh);
        throw std::runtime_error(std::string("Shader compile error: ") + log);
    }
    return sh;
}

static uint32_t link_program(const char* vert_src, const char* frag_src) {
    uint32_t vs   = compile_shader(GL_VERTEX_SHADER,   vert_src);
    uint32_t fs   = compile_shader(GL_FRAGMENT_SHADER, frag_src);
    uint32_t prog = glCreateProgram();
    glAttachShader(prog, vs);
    glAttachShader(prog, fs);
    glLinkProgram(prog);
    glDeleteShader(vs);
    glDeleteShader(fs);

    GLint ok;
    glGetProgramiv(prog, GL_LINK_STATUS, &ok);
    if (!ok) {
        char log[512];
        glGetProgramInfoLog(prog, sizeof(log), nullptr, log);
        glDeleteProgram(prog);
        throw std::runtime_error(std::string("Program link error: ") + log);
    }
    return prog;
}

// ── Renderer public interface ─────────────────────────────────────────────────

Renderer::Renderer(EGLContext& ctx, uint32_t width, uint32_t height)
    : ctx_(ctx), width_(width), height_(height)
{
    // make_current() must have been called on this thread before construction.
    init_shaders();
    init_buffers();
    init_overlay_texture();

    glEnable(GL_BLEND);
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
}

Renderer::~Renderer() {
    if (prog_solid_)   glDeleteProgram(prog_solid_);
    if (prog_texture_) glDeleteProgram(prog_texture_);
    if (overlay_tex_)  glDeleteTextures(1, &overlay_tex_);
    if (vbo_)          glDeleteBuffers(1, &vbo_);
    if (vao_)          glDeleteVertexArrays(1, &vao_);
}

void Renderer::draw(const std::vector<TouchIndicator>& touches) {
    // Clear to a dark command-deck background.
    glClearColor(0.04f, 0.04f, 0.08f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT);
    glViewport(0, 0, static_cast<GLsizei>(width_),
                     static_cast<GLsizei>(height_));

    // Draw the ML overlay if enabled.
    if (overlay_visible_) draw_overlay();

    // Draw a touch indicator circle for each active finger.
    // These give visual feedback that the touchscreen is working and
    // show the operator where the system thinks their fingers are —
    // useful during calibration and development.
    for (const auto& t : touches) {
        if (!t.active) continue;
        draw_circle(t.x, t.y, t.radius,
                    t.color ? t.color : 0xFF4488FFu);
    }

    // The caller is responsible for calling ctx_.swap_and_flip() after draw().
}

void Renderer::update_ml_overlay(float* /*d_data*/) {
    // CUDA interop path: the CUDA kernel writes directly into overlay_tex_.
    // This method is a hook for the main loop to trigger the kernel;
    // the actual cuda_gl_interop logic lives in src/cuda/cuda_gl_interop.cu.
    // Without CUDA, this is a no-op.
#ifdef HAVE_CUDA
    // (Implemented in cuda_gl_interop.cu — linked at build time.)
    extern void cuda_update_texture(uint32_t tex_id, float* d_data,
                                    int w, int h);
    cuda_update_texture(overlay_tex_, d_data,
                        static_cast<int>(width_), static_cast<int>(height_));
#endif
}

// ── Private helpers ───────────────────────────────────────────────────────────

void Renderer::init_shaders() {
    prog_solid_   = link_program(VERT_SOLID,   FRAG_SOLID);
    prog_texture_ = link_program(VERT_TEXTURE, FRAG_TEXTURE);
}

void Renderer::init_buffers() {
    // A single VAO + VBO.  We upload geometry into the VBO dynamically
    // each frame via glBufferSubData — simpler than managing a pool for
    // a UI that changes every frame.
    glGenVertexArrays(1, &vao_);
    glGenBuffers(1, &vbo_);
    glBindVertexArray(vao_);
    glBindBuffer(GL_ARRAY_BUFFER, vbo_);
    // Reserve space for up to 256 vertices (each vertex = 2 floats = 8 bytes).
    glBufferData(GL_ARRAY_BUFFER, 256 * 2 * sizeof(float), nullptr, GL_DYNAMIC_DRAW);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 2 * sizeof(float), nullptr);
    glBindVertexArray(0);
}

void Renderer::init_overlay_texture() {
    // Allocate a full-screen RGBA8 texture that the CUDA kernel writes into.
    // On first use it will be all zeros (transparent black) — invisible.
    glGenTextures(1, &overlay_tex_);
    glBindTexture(GL_TEXTURE_2D, overlay_tex_);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8,
                 static_cast<GLsizei>(width_), static_cast<GLsizei>(height_),
                 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glBindTexture(GL_TEXTURE_2D, 0);
}

void Renderer::draw_rect(const Rect& r, uint32_t color) {
    // Two triangles forming a quad, in normalized [0,1] screen coords.
    const float x0 = r.x,        y0 = r.y;
    const float x1 = r.x + r.w,  y1 = r.y + r.h;
    const float verts[] = {
        x0,y0,  x1,y0,  x0,y1,
        x1,y0,  x1,y1,  x0,y1,
    };

    const float ra = ((color >> 24) & 0xFF) / 255.f;
    const float rb = ((color >> 16) & 0xFF) / 255.f;
    const float gb = ((color >>  8) & 0xFF) / 255.f;
    const float bb = ( color        & 0xFF) / 255.f;

    glUseProgram(prog_solid_);
    glUniform4f(glGetUniformLocation(prog_solid_, "u_color"), rb, gb, bb, ra);
    glBindVertexArray(vao_);
    glBindBuffer(GL_ARRAY_BUFFER, vbo_);
    glBufferSubData(GL_ARRAY_BUFFER, 0, sizeof(verts), verts);
    glDrawArrays(GL_TRIANGLES, 0, 6);
    glBindVertexArray(0);
}

void Renderer::draw_circle(float cx, float cy, float radius, uint32_t color) {
    // Approximate a circle with a triangle fan.
    // 32 segments gives a visually smooth circle at the scales we use
    // (touch indicators are ~2% of screen width).
    constexpr int   SEG   = 32;
    constexpr float TWO_PI = 6.28318530718f;

    // The screen is not square; circles would appear as ellipses if we use
    // the same radius in both axes.  Correct by scaling Y by the aspect ratio.
    const float aspect = static_cast<float>(width_) / static_cast<float>(height_);
    const float ry = radius * aspect;  // Y radius adjusted for aspect ratio

    float verts[2 + (SEG + 1) * 2];
    verts[0] = cx;  verts[1] = cy;  // centre vertex
    for (int i = 0; i <= SEG; ++i) {
        const float angle = TWO_PI * static_cast<float>(i) / static_cast<float>(SEG);
        verts[2 + i * 2 + 0] = cx + radius * std::cos(angle);
        verts[2 + i * 2 + 1] = cy + ry     * std::sin(angle);
    }

    const float ra = ((color >> 24) & 0xFF) / 255.f;
    const float rb = ((color >> 16) & 0xFF) / 255.f;
    const float gb = ((color >>  8) & 0xFF) / 255.f;
    const float bb = ( color        & 0xFF) / 255.f;

    glUseProgram(prog_solid_);
    glUniform4f(glGetUniformLocation(prog_solid_, "u_color"), rb, gb, bb, ra);
    glBindVertexArray(vao_);
    glBindBuffer(GL_ARRAY_BUFFER, vbo_);
    glBufferSubData(GL_ARRAY_BUFFER, 0, sizeof(verts), verts);
    glDrawArrays(GL_TRIANGLE_FAN, 0, 2 + SEG + 1);
    glBindVertexArray(0);
}

void Renderer::draw_overlay() {
    // Full-screen textured quad, blended on top of the UI.
    const float verts[] = {
        // position    UV
        0.f, 0.f,   0.f, 0.f,
        1.f, 0.f,   1.f, 0.f,
        0.f, 1.f,   0.f, 1.f,
        1.f, 0.f,   1.f, 0.f,
        1.f, 1.f,   1.f, 1.f,
        0.f, 1.f,   0.f, 1.f,
    };

    glUseProgram(prog_texture_);
    glUniform1i(glGetUniformLocation(prog_texture_, "u_tex"),   0);
    glUniform1f(glGetUniformLocation(prog_texture_, "u_alpha"), 0.6f);

    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, overlay_tex_);

    glBindVertexArray(vao_);
    glBindBuffer(GL_ARRAY_BUFFER, vbo_);
    glBufferSubData(GL_ARRAY_BUFFER, 0, sizeof(verts), verts);

    // Temporarily configure the VAO to expect 4-float vertices (pos + UV).
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(float), nullptr);
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(float),
                          reinterpret_cast<const void*>(2 * sizeof(float)));
    glEnableVertexAttribArray(1);
    glDrawArrays(GL_TRIANGLES, 0, 6);
    glDisableVertexAttribArray(1);
    // Restore 2-float stride for subsequent solid draws.
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 2 * sizeof(float), nullptr);

    glBindVertexArray(0);
    glBindTexture(GL_TEXTURE_2D, 0);
}
