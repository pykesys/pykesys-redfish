// ddc/ddc_control.hpp — DDC/CI monitor control (brightness, input, power)
//
// DDC/CI (Display Data Channel / Command Interface) is a VESA standard
// that lets the host send control commands to the monitor over the I2C
// bus embedded in the HDMI/DP/VGA cable.
//
// Each controllable feature is assigned a VCP (Virtual Control Panel) code.
// Common ones used by this application:
//   0x10  Brightness (0–100)
//   0x12  Contrast   (0–100)
//   0x60  Input source (15=DisplayPort, 17=HDMI, 1=VGA)
//   0xD6  Power mode  (1=on, 4=off)
//
// This class wraps libddcutil (the ddcutil C library).  If libddcutil is
// not installed, you can use the raw I2C path in ddc_raw.hpp instead —
// it's more work but has no dependencies beyond the kernel's i2c-dev module.
//
// Usage pattern:
//   DDCControl ddc;           // opens first detected DDC monitor
//   ddc.set_brightness(60);   // dim for night operations
//   ddc.set_input(17);        // switch to HDMI (for IFP55G1)
//
// The DDC/CI protocol has a mandatory 50ms delay between write and read.
// All get_* calls block briefly.  Don't call them in the hot render loop;
// use a dedicated control thread or a timer-driven background update.

#pragma once
#include <cstdint>
#include <utility>
#include <stdexcept>
#include <string>

// Forward-declare the ddcutil handle type to avoid exposing the full
// ddcutil header in every file that includes this header.
struct _DDCA_Display_Handle;
using DDCA_Display_Handle = _DDCA_Display_Handle*;

class DDCControl {
public:
    // Opens the first DDC-capable display.  Throws if no DDC display is
    // found or if the ddcutil library fails to initialize.
    DDCControl();

    // Opens a specific display by its ddcutil display number (1-based).
    // Use `ddcutil detect` to list available displays and their numbers.
    explicit DDCControl(int display_number);

    ~DDCControl();

    // Non-copyable: owns the display handle.
    DDCControl(const DDCControl&)            = delete;
    DDCControl& operator=(const DDCControl&) = delete;

    // Set brightness 0–100.  Clamped silently to valid range.
    void set_brightness(int pct);
    int  get_brightness();

    // Set contrast 0–100.
    void set_contrast(int pct);
    int  get_contrast();

    // Set active video input.
    // VCP 0x60 values: 1=VGA, 15=DisplayPort, 17=HDMI.
    // Exact values vary by monitor — check with `ddcutil getvcp 60`.
    void set_input(uint16_t source);
    uint16_t get_input();

    // Power management.  power_off() puts the monitor in standby;
    // power_on() wakes it.  Use these instead of the physical button
    // when scripting unattended operations.
    void power_off();
    void power_on();

    // Generic VCP get/set for features not covered above.
    // Returns {current_value, max_value}.
    std::pair<uint16_t, uint16_t> get_vcp(uint8_t code);
    void set_vcp(uint8_t code, uint16_t value);

    // Model string of the connected monitor (from EDID).
    std::string model_name() const;

private:
    DDCA_Display_Handle dh_{nullptr};

    void open_display(int number);
};
