cmake_minimum_required(VERSION 3.20)
project(CommandDeck LANGUAGES CXX)

# ── Options ────────────────────────────────────────────────────────────────
option(ENABLE_CUDA   "Build CUDA/OpenGL overlay support"  OFF)
option(ENABLE_SDL2   "Build SDL2 backend instead of raw DRM/KMS" OFF)
option(ENABLE_DDCUTIL "Build DDC/CI display-control support"    OFF)
option(ENABLE_ASAN   "Enable AddressSanitizer (Debug only)"     OFF)
option(ENABLE_TSAN   "Enable ThreadSanitizer (Debug only)"      OFF)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)   # for clangd / IDEs

# ── Default build type ─────────────────────────────────────────────────────
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

# ── CUDA language (only when enabled) ─────────────────────────────────────
if(ENABLE_CUDA)
  enable_language(CUDA)
  set(CMAKE_CUDA_STANDARD 17)
  find_package(CUDAToolkit REQUIRED)
endif()

# ── Required packages ──────────────────────────────────────────────────────
find_package(PkgConfig REQUIRED)

pkg_check_modules(LIBEVDEV  REQUIRED libevdev)
pkg_check_modules(LIBINPUT  REQUIRED libinput)
pkg_check_modules(LIBUDEV   REQUIRED libudev)
pkg_check_modules(LIBDRM    REQUIRED libdrm)
pkg_check_modules(GBM       REQUIRED gbm)
pkg_check_modules(EGL       REQUIRED egl)
pkg_check_modules(GLESV2    REQUIRED glesv2)

# ── Optional packages ──────────────────────────────────────────────────────
if(ENABLE_DDCUTIL)
  pkg_check_modules(DDCUTIL REQUIRED ddcutil)
endif()

if(ENABLE_SDL2)
  find_package(SDL2 REQUIRED)
endif()

# ── Source files ──────────────────────────────────────────────────────────
set(CORE_SOURCES
    src/main.cpp
    src/input_loop.cpp
    src/mt_tracker.cpp
    src/gesture/tap.cpp
    src/gesture/swipe.cpp
    src/gesture/pinch.cpp
    src/display/drm_device.cpp
    src/display/egl_context.cpp
    src/ddc/ddc_control.cpp
)

if(ENABLE_CUDA)
  list(APPEND CORE_SOURCES src/cuda/cuda_gl_interop.cu)
endif()

# ── Executable ────────────────────────────────────────────────────────────
add_executable(command_deck ${CORE_SOURCES})

target_include_directories(command_deck PRIVATE
    include/
    ${LIBEVDEV_INCLUDE_DIRS}
    ${LIBINPUT_INCLUDE_DIRS}
    ${LIBUDEV_INCLUDE_DIRS}
    ${LIBDRM_INCLUDE_DIRS}
    ${GBM_INCLUDE_DIRS}
    ${EGL_INCLUDE_DIRS}
)

target_link_libraries(command_deck PRIVATE
    ${LIBEVDEV_LIBRARIES}
    ${LIBINPUT_LIBRARIES}
    ${LIBUDEV_LIBRARIES}
    ${LIBDRM_LIBRARIES}
    ${GBM_LIBRARIES}
    ${EGL_LIBRARIES}
    ${GLESV2_LIBRARIES}
    pthread
)

target_compile_options(command_deck PRIVATE
    -Wall -Wextra -Wpedantic
    $<$<CONFIG:Release>:-O2 -march=native>
    $<$<CONFIG:Debug>:-O0 -g3>
)

# ── Feature definitions ────────────────────────────────────────────────────
if(ENABLE_DDCUTIL)
  target_compile_definitions(command_deck PRIVATE HAVE_DDCUTIL)
  target_include_directories(command_deck PRIVATE ${DDCUTIL_INCLUDE_DIRS})
  target_link_libraries(command_deck PRIVATE ${DDCUTIL_LIBRARIES})
endif()

if(ENABLE_CUDA)
  target_compile_definitions(command_deck PRIVATE HAVE_CUDA)
  target_link_libraries(command_deck PRIVATE CUDA::cudart CUDA::cuda_driver)
  set_target_properties(command_deck PROPERTIES
      CUDA_SEPARABLE_COMPILATION ON
  )
endif()

if(ENABLE_SDL2)
  target_compile_definitions(command_deck PRIVATE HAVE_SDL2)
  target_link_libraries(command_deck PRIVATE SDL2::SDL2)
endif()

# ── Sanitizers (Debug only) ────────────────────────────────────────────────
if(ENABLE_ASAN AND CMAKE_BUILD_TYPE STREQUAL "Debug")
  target_compile_options(command_deck PRIVATE -fsanitize=address,undefined)
  target_link_options(command_deck PRIVATE -fsanitize=address,undefined)
endif()

if(ENABLE_TSAN AND CMAKE_BUILD_TYPE STREQUAL "Debug")
  target_compile_options(command_deck PRIVATE -fsanitize=thread)
  target_link_options(command_deck PRIVATE -fsanitize=thread)
endif()

# ── Install ────────────────────────────────────────────────────────────────
install(TARGETS command_deck DESTINATION bin)

# ── Status summary ────────────────────────────────────────────────────────
message(STATUS "")
message(STATUS "CommandDeck build configuration:")
message(STATUS "  Build type   : ${CMAKE_BUILD_TYPE}")
message(STATUS "  C++ standard : ${CMAKE_CXX_STANDARD}")
message(STATUS "  CUDA support : ${ENABLE_CUDA}")
message(STATUS "  SDL2 backend : ${ENABLE_SDL2}")
message(STATUS "  DDC/CI       : ${ENABLE_DDCUTIL}")
message(STATUS "  ASan/TSan    : ${ENABLE_ASAN}/${ENABLE_TSAN}")
message(STATUS "")
