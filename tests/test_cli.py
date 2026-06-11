from __future__ import annotations

import httpx
import pytest
from typer.testing import CliRunner

from pykesys_redfish.cli.main import app

BASE = "https://bmc.test"
runner = CliRunner()

COMMON_OPTS = ["--host", BASE, "--user", "admin", "--pass", "password", "--no-verify"]


def test_info_command(mock_bmc):
    result = runner.invoke(app, ["info"] + COMMON_OPTS)
    assert result.exit_code == 0
    assert "server01" in result.output or "PowerEdge" in result.output


def test_power_status(mock_bmc):
    result = runner.invoke(app, ["power", "status"] + COMMON_OPTS)
    assert result.exit_code == 0
    assert "On" in result.output


def test_power_on(mock_bmc):
    mock_bmc.post("/redfish/v1/Systems/1/Actions/ComputerSystem.Reset").mock(
        return_value=httpx.Response(204)
    )
    result = runner.invoke(app, ["power", "on"] + COMMON_OPTS)
    assert result.exit_code == 0


def test_boot_status(mock_bmc):
    result = runner.invoke(app, ["boot", "status"] + COMMON_OPTS)
    assert result.exit_code == 0
    assert "Disabled" in result.output or "None" in result.output


def test_boot_once(mock_bmc):
    mock_bmc.patch("/redfish/v1/Systems/1/").mock(return_value=httpx.Response(204))
    mock_bmc.get("/redfish/v1/Systems/1/").mock(
        return_value=httpx.Response(200, json={"Boot": {"BootSourceOverrideTarget": "Pxe", "BootSourceOverrideEnabled": "Once"}})
    )
    result = runner.invoke(app, ["boot", "once", "Pxe"] + COMMON_OPTS)
    assert result.exit_code == 0


def test_accounts_list(mock_bmc):
    mock_bmc.get("/redfish/v1/AccountService/Accounts/").mock(
        return_value=httpx.Response(
            200,
            json={"Members": [{"@odata.id": "/redfish/v1/AccountService/Accounts/1/"}]},
        )
    )
    mock_bmc.get("/redfish/v1/AccountService/Accounts/1/").mock(
        return_value=httpx.Response(
            200,
            json={"Id": "1", "UserName": "admin", "RoleId": "Administrator", "Enabled": True},
        )
    )
    result = runner.invoke(app, ["accounts", "list"] + COMMON_OPTS)
    assert result.exit_code == 0
    assert "admin" in result.output


def test_firmware_list(mock_bmc):
    mock_bmc.get("/redfish/v1/UpdateService/FirmwareInventory/").mock(
        return_value=httpx.Response(
            200,
            json={"Members": [{"@odata.id": "/redfish/v1/UpdateService/FirmwareInventory/BIOS/"}]},
        )
    )
    mock_bmc.get("/redfish/v1/UpdateService/FirmwareInventory/BIOS/").mock(
        return_value=httpx.Response(
            200,
            json={"Id": "BIOS", "Name": "BIOS", "Version": "2.1.0", "Updateable": True},
        )
    )
    result = runner.invoke(app, ["firmware", "list"] + COMMON_OPTS)
    assert result.exit_code == 0
    assert "BIOS" in result.output
