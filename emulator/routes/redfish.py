"""All Redfish REST API routes for a single emulated BMC node.

Every route is prefixed /bmc/{node_id} in main.py. The node_id selects
the NodeState from the registry; all mutations go directly to that object.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse

from .deps import get_node, require_auth
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from node import NodeState

router = APIRouter()

Auth = Annotated[NodeState, Depends(require_auth)]


# ── helpers ──────────────────────────────────────────────────────────────────

def _b(node_id: int) -> str:
    """Redfish URI base for this node, as seen by the client."""
    return "/redfish/v1"


def _odata(node_id: int, path: str) -> str:
    return f"{_b(node_id)}{path}"


def _collection(node_id: int, path: str, members: list[str]) -> dict:
    return {
        "@odata.id": _odata(node_id, path),
        "Members": [{"@odata.id": _odata(node_id, m)} for m in members],
        "Members@odata.count": len(members),
    }


def _error(msg: str, code: int = 400) -> JSONResponse:
    return JSONResponse({"error": {"message": msg}}, status_code=code)


# ── Session ───────────────────────────────────────────────────────────────────

@router.post("/redfish/v1/SessionService/Sessions/", status_code=201)
async def create_session(body: dict, node: Annotated[NodeState, Depends(get_node)], response: Response):
    username = body.get("UserName", "")
    password = body.get("Password", "")
    result = node.create_session(username, password)
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token, session_id = result
    session_uri = f"/redfish/v1/SessionService/Sessions/{session_id}"
    response.headers["X-Auth-Token"] = token
    response.headers["Location"] = session_uri
    return {
        "@odata.id": session_uri,
        "Id": session_id,
        "UserName": username,
    }


@router.delete("/redfish/v1/SessionService/Sessions/{session_id}", status_code=204)
async def delete_session(session_id: str, node: Auth):
    node.delete_session_by_id(session_id)
    return Response(status_code=204)


# ── Service Root ──────────────────────────────────────────────────────────────

@router.get("/redfish/v1/")
async def service_root(node: Auth):
    nid = node.node_id
    return {
        "@odata.type": "#ServiceRoot.v1_15_0.ServiceRoot",
        "@odata.id": "/redfish/v1/",
        "Id": "RootService",
        "Name": "Root Service",
        "RedfishVersion": "1.15.0",
        "Systems":        {"@odata.id": "/redfish/v1/Systems/"},
        "Chassis":        {"@odata.id": "/redfish/v1/Chassis/"},
        "Managers":       {"@odata.id": "/redfish/v1/Managers/"},
        "AccountService": {"@odata.id": "/redfish/v1/AccountService/"},
        "SessionService": {"@odata.id": "/redfish/v1/SessionService/"},
        "UpdateService":  {"@odata.id": "/redfish/v1/UpdateService/"},
    }


# ── Systems ───────────────────────────────────────────────────────────────────

@router.get("/redfish/v1/Systems/")
async def systems_collection(node: Auth):
    return _collection(node.node_id, "/Systems/", ["/Systems/1/"])


@router.get("/redfish/v1/Systems/1/")
async def get_system(node: Auth):
    n = node
    return {
        "@odata.type": "#ComputerSystem.v1_20_0.ComputerSystem",
        "@odata.id": "/redfish/v1/Systems/1/",
        "Id": "1",
        "HostName": n.hostname,
        "SerialNumber": n.serial_number,
        "Model": n.model,
        "Manufacturer": n.manufacturer,
        "BiosVersion": n.bios_version,
        "PowerState": n.power_state,
        "Status": {"Health": n.health, "State": "Enabled"},
        "MemorySummary": {"TotalSystemMemoryGiB": n.memory_gib},
        "ProcessorSummary": {"Count": n.processor_count, "Model": n.processor_model},
        "IndicatorLED": n.indicator_led,
        "Boot": {
            "BootSourceOverrideTarget": n.boot_override_target,
            "BootSourceOverrideEnabled": n.boot_override_enabled,
            "BootSourceOverrideMode": n.boot_override_mode,
            "BootSourceOverrideTarget@Redfish.AllowableValues": [
                "None", "Pxe", "Hdd", "Cd", "Usb", "BiosSetup", "UefiShell", "UefiHttp",
            ],
        },
        "Actions": {
            "#ComputerSystem.Reset": {
                "target": "/redfish/v1/Systems/1/Actions/ComputerSystem.Reset",
                "ResetType@Redfish.AllowableValues": [
                    "On", "ForceOff", "GracefulShutdown", "GracefulRestart",
                    "ForceRestart", "Nmi", "PushPowerButton",
                ],
            }
        },
        "Processors": {"@odata.id": "/redfish/v1/Systems/1/Processors/"},
        "Memory":     {"@odata.id": "/redfish/v1/Systems/1/Memory/"},
        "Storage":    {"@odata.id": "/redfish/v1/Systems/1/Storage/"},
        "EthernetInterfaces": {"@odata.id": "/redfish/v1/Systems/1/EthernetInterfaces/"},
        "LogServices": {"@odata.id": "/redfish/v1/Systems/1/LogServices/"},
    }


@router.patch("/redfish/v1/Systems/1/")
async def patch_system(body: dict, node: Auth):
    if "IndicatorLED" in body:
        node.indicator_led = body["IndicatorLED"]
    if "Boot" in body:
        boot = body["Boot"]
        if "BootSourceOverrideTarget" in boot:
            node.boot_override_target = boot["BootSourceOverrideTarget"]
        if "BootSourceOverrideEnabled" in boot:
            node.boot_override_enabled = boot["BootSourceOverrideEnabled"]
        if "BootSourceOverrideMode" in boot:
            node.boot_override_mode = boot["BootSourceOverrideMode"]
    return Response(status_code=204)


@router.post("/redfish/v1/Systems/1/Actions/ComputerSystem.Reset")
async def reset_system(body: dict, node: Auth):
    reset_type = body.get("ResetType", "")
    if not node.apply_reset(reset_type):
        raise HTTPException(status_code=400, detail=f"Unsupported ResetType: {reset_type}")
    return Response(status_code=204)


@router.get("/redfish/v1/Systems/1/Processors/")
async def processors_collection(node: Auth):
    return _collection(node.node_id, "/Systems/1/Processors/", ["/Systems/1/Processors/CPU1/", "/Systems/1/Processors/CPU2/"])


@router.get("/redfish/v1/Systems/1/Processors/{cpu_id}/")
async def get_processor(cpu_id: str, node: Auth):
    idx = 1 if cpu_id == "CPU1" else 2
    return {
        "@odata.id": f"/redfish/v1/Systems/1/Processors/{cpu_id}/",
        "Id": cpu_id,
        "Name": f"Processor {idx}",
        "Model": node.processor_model,
        "TotalCores": 32,
        "TotalThreads": 64,
        "MaxSpeedMHz": 3800,
        "ProcessorArchitecture": "x86",
        "Status": {"Health": "OK", "State": "Enabled"},
    }


@router.get("/redfish/v1/Systems/1/Memory/")
async def memory_collection(node: Auth):
    return _collection(node.node_id, "/Systems/1/Memory/", ["/Systems/1/Memory/DIMM1/"])


@router.get("/redfish/v1/Systems/1/Memory/{dimm_id}/")
async def get_memory(dimm_id: str, node: Auth):
    per_dimm = node.memory_gib / 4
    return {
        "@odata.id": f"/redfish/v1/Systems/1/Memory/{dimm_id}/",
        "Id": dimm_id,
        "CapacityMiB": int(per_dimm * 1024),
        "MemoryType": "DRAM",
        "MemoryDeviceType": "DDR5",
        "OperatingSpeedMhz": 4800,
        "Manufacturer": "SimMemCo",
        "Status": {"Health": "OK", "State": "Enabled"},
    }


@router.get("/redfish/v1/Systems/1/Storage/")
async def storage_collection(node: Auth):
    return _collection(node.node_id, "/Systems/1/Storage/", ["/Systems/1/Storage/RAID1/"])


@router.get("/redfish/v1/Systems/1/Storage/RAID1/")
async def get_storage_controller(node: Auth):
    return {
        "@odata.id": "/redfish/v1/Systems/1/Storage/RAID1/",
        "Id": "RAID1",
        "Name": "Sim RAID Controller",
        "Status": {"Health": "OK", "State": "Enabled"},
        "Drives": [
            {"@odata.id": "/redfish/v1/Systems/1/Storage/RAID1/Drives/Drive1/"},
            {"@odata.id": "/redfish/v1/Systems/1/Storage/RAID1/Drives/Drive2/"},
        ],
        "Volumes": {"@odata.id": "/redfish/v1/Systems/1/Storage/RAID1/Volumes/"},
    }


@router.get("/redfish/v1/Systems/1/Storage/RAID1/Drives/{drive_id}/")
async def get_drive(drive_id: str, node: Auth):
    idx = int(drive_id.replace("Drive", ""))
    return {
        "@odata.id": f"/redfish/v1/Systems/1/Storage/RAID1/Drives/{drive_id}/",
        "Id": drive_id,
        "Name": f"Drive {idx}",
        "CapacityBytes": 1_920_000_000_000,
        "Protocol": "NVMe",
        "MediaType": "SSD",
        "Model": "SimDrive NVMe 2TB",
        "SerialNumber": f"SIMDRIVE{node.node_id:02d}{idx:02d}",
        "PredictedMediaLifeLeftPercent": 95,
        "Status": {"Health": "OK", "State": "Enabled"},
    }


@router.get("/redfish/v1/Systems/1/Storage/RAID1/Volumes/")
async def volumes_collection(node: Auth):
    return _collection(node.node_id, "/Systems/1/Storage/RAID1/Volumes/", [])


# ── SEL Log ───────────────────────────────────────────────────────────────────

@router.get("/redfish/v1/Systems/1/LogServices/")
async def log_services(node: Auth):
    return _collection(node.node_id, "/Systems/1/LogServices/", ["/Systems/1/LogServices/Sel/"])


@router.get("/redfish/v1/Systems/1/LogServices/Sel/Entries/")
async def get_sel_entries(node: Auth):
    entries = node.sel_log
    return {
        "@odata.id": "/redfish/v1/Systems/1/LogServices/Sel/Entries/",
        "Members": entries,
        "Members@odata.count": len(entries),
    }


@router.post("/redfish/v1/Systems/1/LogServices/Sel/Actions/LogService.ClearLog")
async def clear_sel(node: Auth):
    node.clear_sel()
    return Response(status_code=204)


# ── Chassis ───────────────────────────────────────────────────────────────────

@router.get("/redfish/v1/Chassis/")
async def chassis_collection(node: Auth):
    return _collection(node.node_id, "/Chassis/", ["/Chassis/1/"])


@router.get("/redfish/v1/Chassis/1/")
async def get_chassis(node: Auth):
    n = node
    return {
        "@odata.type": "#Chassis.v1_23_0.Chassis",
        "@odata.id": "/redfish/v1/Chassis/1/",
        "Id": "1",
        "ChassisType": "RackMount",
        "Manufacturer": n.manufacturer,
        "Model": n.model,
        "SerialNumber": n.serial_number,
        "IndicatorLED": n.indicator_led,
        "Status": {"Health": n.health, "State": "Enabled"},
        "Thermal": {"@odata.id": "/redfish/v1/Chassis/1/Thermal/"},
        "Power":   {"@odata.id": "/redfish/v1/Chassis/1/Power/"},
    }


@router.patch("/redfish/v1/Chassis/1/")
async def patch_chassis(body: dict, node: Auth):
    if "IndicatorLED" in body:
        node.indicator_led = body["IndicatorLED"]
    return Response(status_code=204)


@router.get("/redfish/v1/Chassis/1/Thermal/")
async def get_thermal(node: Auth):
    return {
        "@odata.id": "/redfish/v1/Chassis/1/Thermal/",
        "Temperatures": node.temperatures,
        "Fans": node.fans,
    }


@router.get("/redfish/v1/Chassis/1/Power/")
async def get_power(node: Auth):
    total_watts = sum(p.get("PowerOutputWatts", 0) for p in node.power_supplies)
    return {
        "@odata.id": "/redfish/v1/Chassis/1/Power/",
        "PowerSupplies": node.power_supplies,
        "PowerControl": [
            {
                "Name": "System Power Control",
                "PowerConsumedWatts": total_watts,
                "PowerCapacityWatts": 1600.0,
            }
        ],
    }


# ── Managers ──────────────────────────────────────────────────────────────────

@router.get("/redfish/v1/Managers/")
async def managers_collection(node: Auth):
    return _collection(node.node_id, "/Managers/", ["/Managers/BMC/"])


@router.get("/redfish/v1/Managers/BMC/")
async def get_manager(node: Auth):
    return {
        "@odata.type": "#Manager.v1_18_0.Manager",
        "@odata.id": "/redfish/v1/Managers/BMC/",
        "Id": "BMC",
        "Name": "Sim BMC",
        "ManagerType": "BMC",
        "FirmwareVersion": node.bmc_firmware_version,
        "Model": "SimBMC 4000",
        "Status": {"Health": "OK", "State": "Enabled"},
        "NetworkProtocol":   {"@odata.id": "/redfish/v1/Managers/BMC/NetworkProtocol/"},
        "EthernetInterfaces": {"@odata.id": "/redfish/v1/Managers/BMC/EthernetInterfaces/"},
        "LogServices":       {"@odata.id": "/redfish/v1/Managers/BMC/LogServices/"},
        "Actions": {
            "#Manager.Reset": {"target": "/redfish/v1/Managers/BMC/Actions/Manager.Reset"},
            "#Manager.ResetToDefaults": {"target": "/redfish/v1/Managers/BMC/Actions/Manager.ResetToDefaults"},
        },
    }


@router.post("/redfish/v1/Managers/BMC/Actions/Manager.Reset", status_code=204)
async def manager_reset(body: dict, node: Auth):
    return Response(status_code=204)


@router.post("/redfish/v1/Managers/BMC/Actions/Manager.ResetToDefaults", status_code=204)
async def manager_reset_defaults(body: dict, node: Auth):
    node.reset_to_healthy()
    return Response(status_code=204)


@router.get("/redfish/v1/Managers/BMC/NetworkProtocol/")
async def network_protocol(node: Auth):
    return {
        "@odata.id": "/redfish/v1/Managers/BMC/NetworkProtocol/",
        "HTTPS": {"ProtocolEnabled": True, "Port": 443},
        "HTTP":  {"ProtocolEnabled": False, "Port": 80},
        "SSH":   {"ProtocolEnabled": True, "Port": 22},
        "IPMI":  {"ProtocolEnabled": False, "Port": 623},
        "SNMP":  {"ProtocolEnabled": False, "Port": 161},
        "NTP":   {"ProtocolEnabled": True, "NTPServers": ["pool.ntp.org"]},
    }


@router.patch("/redfish/v1/Managers/BMC/NetworkProtocol/")
async def patch_network_protocol(body: dict, node: Auth):
    return Response(status_code=204)


@router.get("/redfish/v1/Managers/BMC/EthernetInterfaces/")
async def bmc_eth_collection(node: Auth):
    return _collection(node.node_id, "/Managers/BMC/EthernetInterfaces/", ["/Managers/BMC/EthernetInterfaces/NIC1/"])


@router.get("/redfish/v1/Managers/BMC/EthernetInterfaces/NIC1/")
async def bmc_eth_detail(node: Auth):
    return {
        "@odata.id": "/redfish/v1/Managers/BMC/EthernetInterfaces/NIC1/",
        "Id": "NIC1",
        "MACAddress": f"AA:BB:CC:DD:{node.node_id:02X}:01",
        "IPv4Addresses": [{"Address": f"192.168.100.{node.node_id}", "SubnetMask": "255.255.255.0"}],
        "DHCPv4": {"DHCPEnabled": False},
        "Status": {"Health": "OK", "State": "Enabled"},
    }


@router.get("/redfish/v1/Managers/BMC/LogServices/")
async def bmc_logs_collection(node: Auth):
    return _collection(node.node_id, "/Managers/BMC/LogServices/", ["/Managers/BMC/LogServices/Log1/"])


@router.get("/redfish/v1/Managers/BMC/LogServices/Log1/Entries/")
async def bmc_log_entries(node: Auth):
    return {
        "@odata.id": "/redfish/v1/Managers/BMC/LogServices/Log1/Entries/",
        "Members": [],
        "Members@odata.count": 0,
    }


# ── AccountService ────────────────────────────────────────────────────────────

@router.get("/redfish/v1/AccountService/")
async def account_service(node: Auth):
    return {
        "@odata.id": "/redfish/v1/AccountService/",
        "MinPasswordLength": 8,
        "MaxPasswordLength": 255,
        "AccountLockoutThreshold": 5,
        "AccountLockoutDuration": 300,
        "AccountLockoutCounterResetAfter": 120,
        "Accounts": {"@odata.id": "/redfish/v1/AccountService/Accounts/"},
        "Roles":    {"@odata.id": "/redfish/v1/AccountService/Roles/"},
    }


@router.patch("/redfish/v1/AccountService/")
async def patch_account_service(body: dict, node: Auth):
    return Response(status_code=204)


@router.get("/redfish/v1/AccountService/Accounts/")
async def list_accounts(node: Auth):
    admin = {
        "@odata.id": "/redfish/v1/AccountService/Accounts/1/",
        "Id": "1",
        "UserName": node.admin_user,
        "RoleId": "Administrator",
        "Enabled": True,
    }
    members = [{"@odata.id": f"/redfish/v1/AccountService/Accounts/{a['Id']}/"} for a in [admin] + node.accounts]
    return {
        "@odata.id": "/redfish/v1/AccountService/Accounts/",
        "Members": members,
        "Members@odata.count": len(members),
    }


@router.post("/redfish/v1/AccountService/Accounts/", status_code=201)
async def create_account(body: dict, node: Auth, response: Response):
    acc = node.add_account(body["UserName"], body.get("Password", ""), body.get("RoleId", "Operator"))
    uri = f"/redfish/v1/AccountService/Accounts/{acc['Id']}/"
    response.headers["Location"] = uri
    return {**acc, "@odata.id": uri}


@router.get("/redfish/v1/AccountService/Accounts/{account_id}/")
async def get_account(account_id: str, node: Auth):
    if account_id == "1":
        return {"@odata.id": "/redfish/v1/AccountService/Accounts/1/", "Id": "1",
                "UserName": node.admin_user, "RoleId": "Administrator", "Enabled": True}
    acc = node.get_account(account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    return {**acc, "@odata.id": f"/redfish/v1/AccountService/Accounts/{account_id}/"}


@router.patch("/redfish/v1/AccountService/Accounts/{account_id}/")
async def patch_account(account_id: str, body: dict, node: Auth):
    if account_id == "1":
        return Response(status_code=204)
    acc = node.get_account(account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    for key in ("Password", "Enabled", "RoleId"):
        if key in body:
            acc[key] = body[key]
    return Response(status_code=204)


@router.delete("/redfish/v1/AccountService/Accounts/{account_id}/", status_code=204)
async def delete_account(account_id: str, node: Auth):
    if account_id == "1":
        raise HTTPException(status_code=405, detail="Cannot delete built-in admin account")
    if not node.delete_account(account_id):
        raise HTTPException(status_code=404, detail="Account not found")
    return Response(status_code=204)


# ── UpdateService ─────────────────────────────────────────────────────────────

@router.get("/redfish/v1/UpdateService/")
async def update_service(node: Auth):
    return {
        "@odata.id": "/redfish/v1/UpdateService/",
        "FirmwareInventory": {"@odata.id": "/redfish/v1/UpdateService/FirmwareInventory/"},
        "Actions": {
            "#UpdateService.SimpleUpdate": {
                "target": "/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate"
            }
        },
    }


@router.get("/redfish/v1/UpdateService/FirmwareInventory/")
async def firmware_inventory(node: Auth):
    return {
        "@odata.id": "/redfish/v1/UpdateService/FirmwareInventory/",
        "Members": [{"@odata.id": f"/redfish/v1/UpdateService/FirmwareInventory/{f['Id']}/"} for f in node.firmware],
        "Members@odata.count": len(node.firmware),
    }


@router.get("/redfish/v1/UpdateService/FirmwareInventory/{fw_id}/")
async def get_firmware_component(fw_id: str, node: Auth):
    for f in node.firmware:
        if f["Id"] == fw_id:
            return {**f, "@odata.id": f"/redfish/v1/UpdateService/FirmwareInventory/{fw_id}/"}
    raise HTTPException(status_code=404, detail="Firmware component not found")


@router.post("/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate", status_code=202)
async def simple_update(body: dict, node: Auth, response: Response):
    task_id = "Task001"
    task_uri = f"/redfish/v1/TaskService/Tasks/{task_id}/"
    response.headers["Location"] = task_uri
    return {
        "@odata.id": task_uri,
        "Id": task_id,
        "TaskState": "Completed",
        "TaskStatus": "OK",
        "PercentComplete": 100,
        "Messages": [{"Message": f"Simulated update of {body.get('ImageURI', 'unknown')} completed."}],
    }


# ── TaskService ───────────────────────────────────────────────────────────────

@router.get("/redfish/v1/TaskService/Tasks/{task_id}/")
async def get_task(task_id: str, node: Auth):
    return {
        "@odata.id": f"/redfish/v1/TaskService/Tasks/{task_id}/",
        "Id": task_id,
        "TaskState": "Completed",
        "TaskStatus": "OK",
        "PercentComplete": 100,
    }
