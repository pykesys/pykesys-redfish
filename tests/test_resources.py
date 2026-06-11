from __future__ import annotations

import httpx
import pytest

from pykesys_redfish import RedfishClient

BASE = "https://bmc.test"


class TestComputerSystem:
    def test_properties(self, mock_bmc):
        with RedfishClient(BASE, "admin", "password") as rf:
            s = rf.system()
            assert s.id == "1"
            assert s.hostname == "server01.example.com"
            assert s.serial_number == "ABC123"
            assert s.model == "PowerEdge R750"
            assert s.manufacturer == "Dell"
            assert s.bios_version == "2.1.0"
            assert s.power_state == "On"
            assert s.health == "OK"
            assert s.total_memory_gib == 256
            assert s.processor_count == 2
            assert s.processor_model == "Intel Xeon Gold 6338"

    def test_summary_dict(self, mock_bmc):
        with RedfishClient(BASE, "admin", "password") as rf:
            summary = rf.system().summary()
            assert summary["hostname"] == "server01.example.com"
            assert summary["health"] == "OK"

    def test_power_on_posts_reset(self, mock_bmc):
        mock_bmc.post("/redfish/v1/Systems/1/Actions/ComputerSystem.Reset").mock(
            return_value=httpx.Response(204)
        )
        with RedfishClient(BASE, "admin", "password") as rf:
            rf.system().power_on()

    def test_set_boot_once(self, mock_bmc):
        mock_bmc.patch("/redfish/v1/Systems/1/").mock(return_value=httpx.Response(204))
        mock_bmc.get("/redfish/v1/Systems/1/").mock(
            return_value=httpx.Response(200, json={"Boot": {"BootSourceOverrideTarget": "Pxe"}})
        )
        with RedfishClient(BASE, "admin", "password") as rf:
            rf.system().set_boot_once("Pxe")

    def test_boot_allowable_values(self, mock_bmc):
        with RedfishClient(BASE, "admin", "password") as rf:
            vals = rf.system().boot_allowable_values
            assert "Pxe" in vals

    def test_identify(self, mock_bmc):
        mock_bmc.patch("/redfish/v1/Systems/1/").mock(return_value=httpx.Response(204))
        mock_bmc.get("/redfish/v1/Systems/1/").mock(
            return_value=httpx.Response(200, json={"IndicatorLED": "Blinking"})
        )
        with RedfishClient(BASE, "admin", "password") as rf:
            rf.system().identify("Blinking")


class TestChassis:
    def test_properties(self, mock_bmc):
        with RedfishClient(BASE, "admin", "password") as rf:
            c = rf.chassis()
            assert c.id == "1"
            assert c.health == "OK"
            assert c.chassis_type == "RackMount"


class TestManager:
    def test_properties(self, mock_bmc):
        with RedfishClient(BASE, "admin", "password") as rf:
            m = rf.manager()
            assert m.firmware_version == "6.10.30.00"
            assert m.manager_type == "BMC"
            assert m.health == "OK"

    def test_reset(self, mock_bmc):
        mock_bmc.post("/redfish/v1/Managers/iDRAC.Embedded.1/Actions/Manager.Reset").mock(
            return_value=httpx.Response(204)
        )
        with RedfishClient(BASE, "admin", "password") as rf:
            rf.manager().reset()
