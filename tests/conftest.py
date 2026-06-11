"""Shared fixtures for the pykesys-redfish test suite.

Uses respx to mock httpx at the transport layer — no real BMCs needed.
"""

from __future__ import annotations

import pytest
import respx
import httpx

BASE = "https://bmc.test"

SERVICE_ROOT = {
    "@odata.type": "#ServiceRoot.v1_15_0.ServiceRoot",
    "@odata.id": "/redfish/v1/",
    "RedfishVersion": "1.15.0",
    "Systems": {"@odata.id": "/redfish/v1/Systems/"},
    "Chassis": {"@odata.id": "/redfish/v1/Chassis/"},
    "Managers": {"@odata.id": "/redfish/v1/Managers/"},
    "AccountService": {"@odata.id": "/redfish/v1/AccountService/"},
    "SessionService": {"@odata.id": "/redfish/v1/SessionService/"},
}

SYSTEMS_COLLECTION = {
    "@odata.id": "/redfish/v1/Systems/",
    "Members": [{"@odata.id": "/redfish/v1/Systems/1/"}],
    "Members@odata.count": 1,
}

SYSTEM_1 = {
    "@odata.type": "#ComputerSystem.v1_20_0.ComputerSystem",
    "@odata.id": "/redfish/v1/Systems/1/",
    "Id": "1",
    "HostName": "server01.example.com",
    "SerialNumber": "ABC123",
    "Model": "PowerEdge R750",
    "Manufacturer": "Dell",
    "BiosVersion": "2.1.0",
    "PowerState": "On",
    "Status": {"Health": "OK", "State": "Enabled"},
    "MemorySummary": {"TotalSystemMemoryGiB": 256},
    "ProcessorSummary": {"Count": 2, "Model": "Intel Xeon Gold 6338"},
    "Boot": {
        "BootSourceOverrideTarget": "None",
        "BootSourceOverrideEnabled": "Disabled",
        "BootSourceOverrideTarget@Redfish.AllowableValues": ["None", "Pxe", "Hdd", "Cd", "Usb"],
    },
    "IndicatorLED": "Off",
    "Actions": {
        "#ComputerSystem.Reset": {
            "target": "/redfish/v1/Systems/1/Actions/ComputerSystem.Reset",
        }
    },
    "Processors": {"@odata.id": "/redfish/v1/Systems/1/Processors/"},
    "Memory": {"@odata.id": "/redfish/v1/Systems/1/Memory/"},
    "Storage": {"@odata.id": "/redfish/v1/Systems/1/Storage/"},
}

CHASSIS_COLLECTION = {
    "@odata.id": "/redfish/v1/Chassis/",
    "Members": [{"@odata.id": "/redfish/v1/Chassis/1/"}],
}

CHASSIS_1 = {
    "@odata.id": "/redfish/v1/Chassis/1/",
    "Id": "1",
    "ChassisType": "RackMount",
    "Manufacturer": "Dell",
    "Model": "PowerEdge R750",
    "SerialNumber": "ABC123",
    "Status": {"Health": "OK"},
    "IndicatorLED": "Off",
}

MANAGERS_COLLECTION = {
    "@odata.id": "/redfish/v1/Managers/",
    "Members": [{"@odata.id": "/redfish/v1/Managers/iDRAC.Embedded.1/"}],
}

MANAGER_1 = {
    "@odata.id": "/redfish/v1/Managers/iDRAC.Embedded.1/",
    "Id": "iDRAC.Embedded.1",
    "ManagerType": "BMC",
    "FirmwareVersion": "6.10.30.00",
    "Model": "iDRAC9",
    "Status": {"Health": "OK"},
    "NetworkProtocol": {"@odata.id": "/redfish/v1/Managers/iDRAC.Embedded.1/NetworkProtocol/"},
    "Actions": {
        "#Manager.Reset": {
            "target": "/redfish/v1/Managers/iDRAC.Embedded.1/Actions/Manager.Reset"
        }
    },
}

ACCOUNTS_SERVICE = {
    "@odata.id": "/redfish/v1/AccountService/",
    "MinPasswordLength": 8,
    "AccountLockoutThreshold": 5,
    "AccountLockoutDuration": 300,
    "Accounts": {"@odata.id": "/redfish/v1/AccountService/Accounts/"},
}

SESSION_RESPONSE_HEADERS = {
    "X-Auth-Token": "test-token-abc123",
    "Location": "/redfish/v1/SessionService/Sessions/1",
}


@pytest.fixture
def mock_bmc():
    """Set up a respx mock router for all standard Redfish endpoints."""
    with respx.mock(base_url=BASE, assert_all_called=False) as router:
        # Session create
        router.post("/redfish/v1/SessionService/Sessions/").mock(
            return_value=httpx.Response(
                201,
                json={"@odata.id": "/redfish/v1/SessionService/Sessions/1"},
                headers=SESSION_RESPONSE_HEADERS,
            )
        )
        # Session delete
        router.delete("/redfish/v1/SessionService/Sessions/1").mock(
            return_value=httpx.Response(204)
        )
        # Service root
        router.get("/redfish/v1/").mock(return_value=httpx.Response(200, json=SERVICE_ROOT))
        # Systems
        router.get("/redfish/v1/Systems/").mock(
            return_value=httpx.Response(200, json=SYSTEMS_COLLECTION)
        )
        router.get("/redfish/v1/Systems/1/").mock(
            return_value=httpx.Response(200, json=SYSTEM_1)
        )
        # Chassis
        router.get("/redfish/v1/Chassis/").mock(
            return_value=httpx.Response(200, json=CHASSIS_COLLECTION)
        )
        router.get("/redfish/v1/Chassis/1/").mock(
            return_value=httpx.Response(200, json=CHASSIS_1)
        )
        # Managers
        router.get("/redfish/v1/Managers/").mock(
            return_value=httpx.Response(200, json=MANAGERS_COLLECTION)
        )
        router.get("/redfish/v1/Managers/iDRAC.Embedded.1/").mock(
            return_value=httpx.Response(200, json=MANAGER_1)
        )
        # AccountService
        router.get("/redfish/v1/AccountService/").mock(
            return_value=httpx.Response(200, json=ACCOUNTS_SERVICE)
        )
        yield router
