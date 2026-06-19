// ddc/ddc_control.cpp — DDC/CI monitor control via libddcutil
//
// See ddc/ddc_control.hpp for the conceptual background.
// libddcutil handles the low-level I2C framing, checksum, and 50ms delays
// required by the DDC/CI spec.  We just call the high-level API.
//
// If HAVE_DDCUTIL is not defined (libddcutil not installed), all methods
// become no-ops with warning messages.  This lets the application build and
// run without DDC support — useful on development machines without a real
// DDC-capable display attached.

#include "ddc/ddc_control.hpp"
#include <cstdio>
#include <cstring>

#ifdef HAVE_DDCUTIL
#include <ddcutil_c_api.h>
#include <ddcutil_types.h>

// Undefine the forward-declared type alias so the real one from ddcutil applies.
#undef DDCA_Display_Handle
using DDCA_Display_Handle = void*;

static void check_ddca(DDCA_Status rc, const char* ctx) {
    if (rc != DDCRC_OK)
        throw std::runtime_error(std::string(ctx) + ": " + ddca_rc_name(rc));
}
#endif

DDCControl::DDCControl() {
    open_display(1);  // display number 1 = first detected DDC monitor
}

DDCControl::DDCControl(int display_number) {
    open_display(display_number);
}

DDCControl::~DDCControl() {
#ifdef HAVE_DDCUTIL
    if (dh_) ddca_close_display(static_cast<DDCA_Display_Handle>(dh_));
#endif
}

void DDCControl::open_display(int number) {
#ifdef HAVE_DDCUTIL
    // Initialize the ddcutil library.  The second argument selects the
    // syslog verbosity (DDCA_SYSLOG_NOT_USED = no syslog output).
    check_ddca(ddca_init(nullptr, DDCA_SYSLOG_NOT_USED, DDCA_INIT_OPTIONS_NONE),
               "ddca_init");

    // Enumerate connected DDC-capable displays.
    DDCA_Display_Info_List* dlist = nullptr;
    check_ddca(ddca_get_display_info_list2(false, &dlist),
               "ddca_get_display_info_list2");

    if (!dlist || dlist->ct < number)
        throw std::runtime_error("DDC display #" + std::to_string(number)
                                 + " not found.  Connected displays: "
                                 + std::to_string(dlist ? dlist->ct : 0));

    // Open the requested display.  false = non-exclusive (other processes
    // can also query the display simultaneously).
    DDCA_Display_Ref dref = dlist->info[number - 1].dref;
    DDCA_Display_Handle handle = nullptr;
    check_ddca(ddca_open_display2(dref, false, &handle), "ddca_open_display2");
    dh_ = handle;

    ddca_free_display_info_list(dlist);
#else
    (void)number;
    fprintf(stderr, "[DDCControl] libddcutil not available — DDC/CI disabled\n");
#endif
}

std::pair<uint16_t, uint16_t> DDCControl::get_vcp(uint8_t code) {
#ifdef HAVE_DDCUTIL
    DDCA_Non_Table_Vcp_Value val{};
    auto rc = ddca_get_non_table_vcp_value(
        static_cast<DDCA_Display_Handle>(dh_), code, &val);
    if (rc != DDCRC_OK) return {0, 0};
    return {val.cur_val, val.max_val};
#else
    (void)code; return {0, 0};
#endif
}

void DDCControl::set_vcp(uint8_t code, uint16_t value) {
#ifdef HAVE_DDCUTIL
    auto rc = ddca_set_non_table_vcp_value(
        static_cast<DDCA_Display_Handle>(dh_), code, 0, value);
    if (rc != DDCRC_OK)
        fprintf(stderr, "[DDCControl] set_vcp 0x%02X = %u failed: %s\n",
                code, value, ddca_rc_name(rc));
#else
    (void)code; (void)value;
#endif
}

void DDCControl::set_brightness(int pct) {
    // Clamp to [0, 100] — some monitors misbehave with out-of-range values.
    const uint16_t v = static_cast<uint16_t>(pct < 0 ? 0 : pct > 100 ? 100 : pct);
    set_vcp(0x10, v);
}

int DDCControl::get_brightness() {
    return static_cast<int>(get_vcp(0x10).first);
}

void DDCControl::set_contrast(int pct) {
    const uint16_t v = static_cast<uint16_t>(pct < 0 ? 0 : pct > 100 ? 100 : pct);
    set_vcp(0x12, v);
}

int DDCControl::get_contrast() {
    return static_cast<int>(get_vcp(0x12).first);
}

void DDCControl::set_input(uint16_t source) {
    // VCP 0x60 selects the active input.  Common values:
    //   1  = VGA
    //   15 = DisplayPort
    //   17 = HDMI
    // Check with `ddcutil getvcp 60` to see what your monitor accepts.
    set_vcp(0x60, source);
}

uint16_t DDCControl::get_input() {
    return get_vcp(0x60).first;
}

void DDCControl::power_off() {
    // VCP 0xD6 power mode: 1=on, 4=off (standby).
    // This cuts the backlight and puts the monitor in low-power state.
    // The DDC/CI bus remains active so power_on() can wake it.
    set_vcp(0xD6, 4);
}

void DDCControl::power_on() {
    set_vcp(0xD6, 1);
}

std::string DDCControl::model_name() const {
#ifdef HAVE_DDCUTIL
    if (!dh_) return "(no display)";
    // ddcutil reads the model string from the monitor's EDID.
    // EDID (Extended Display Identification Data) is a 128-byte block
    // the monitor stores in its own ROM describing its capabilities.
    DDCA_Monitor_Model_Key key;
    if (ddca_get_monitor_model_key(
            static_cast<DDCA_Display_Handle>(dh_), &key) == DDCRC_OK) {
        return std::string(key.model_name);
    }
#endif
    return "(unavailable)";
}
