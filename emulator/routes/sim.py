"""Sim control API — inject events, apply scenarios, inspect node state.

Routes are prefixed /sim/ in main.py. No auth required (control plane only).
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import registry
from node import NodeState

router = APIRouter(prefix="/sim")

_SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"


def _node_summary(node: NodeState) -> dict:
    return {
        "node_id": node.node_id,
        "hostname": node.hostname,
        "power_state": node.power_state,
        "health": node.health,
        "indicator_led": node.indicator_led,
        "boot_override_target": node.boot_override_target,
        "boot_override_enabled": node.boot_override_enabled,
        "sel_entry_count": len(node.sel_log),
        "active_sessions": len(node.sessions),
        "base_url_path": f"/bmc/{node.node_id}",
    }


def _get_node_or_404(node_id: int) -> NodeState:
    node = registry.get(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return node


# ── Fleet-level ───────────────────────────────────────────────────────────────

@router.get("/nodes/")
async def list_nodes():
    """Return a summary of all emulated nodes."""
    return [_node_summary(n) for n in registry.all_nodes().values()]


@router.get("/nodes/{node_id}/")
async def get_node_state(node_id: int):
    """Return full state of a single node."""
    node = _get_node_or_404(node_id)
    return {
        **_node_summary(node),
        "model": node.model,
        "serial_number": node.serial_number,
        "bios_version": node.bios_version,
        "bmc_firmware_version": node.bmc_firmware_version,
        "memory_gib": node.memory_gib,
        "processor_count": node.processor_count,
        "processor_model": node.processor_model,
        "temperatures": node.temperatures,
        "fans": node.fans,
        "power_supplies": node.power_supplies,
        "firmware": node.firmware,
        "accounts": [{"Id": a["Id"], "UserName": a["UserName"], "RoleId": a["RoleId"], "Enabled": a["Enabled"]} for a in node.accounts],
        "sel_log": node.sel_log,
    }


# ── Per-node event injection ──────────────────────────────────────────────────

@router.post("/nodes/{node_id}/health")
async def set_health(node_id: int, body: dict):
    """Set node health. Body: {"health": "Critical"}"""
    node = _get_node_or_404(node_id)
    health = body.get("health")
    if health not in ("OK", "Warning", "Critical"):
        raise HTTPException(status_code=400, detail="health must be OK, Warning, or Critical")
    node.health = health
    return {"node_id": node_id, "health": node.health}


@router.post("/nodes/{node_id}/power")
async def set_power(node_id: int, body: dict):
    """Set node power state directly. Body: {"power_state": "Off"}"""
    node = _get_node_or_404(node_id)
    state = body.get("power_state")
    if state not in ("On", "Off", "PoweringOn", "PoweringOff"):
        raise HTTPException(status_code=400, detail="Invalid power_state")
    node.power_state = state
    return {"node_id": node_id, "power_state": node.power_state}


@router.post("/nodes/{node_id}/sel-event")
async def inject_sel_event(node_id: int, body: dict):
    """Inject a SEL log entry. Body: {"severity": "Warning", "message": "Fan speed low", "message_id": "..."}"""
    node = _get_node_or_404(node_id)
    severity = body.get("severity", "Warning")
    message = body.get("message", "Simulated event")
    message_id = body.get("message_id", "")
    entry = node.add_sel_entry(severity, message, message_id)
    return {"node_id": node_id, "entry": entry}


@router.post("/nodes/{node_id}/sensor")
async def set_sensor(node_id: int, body: dict):
    """Update or add a sensor reading.
    Body: {"name": "CPU1 Temp", "reading": 95.0, "status": "Critical", "unit": "C"}
    """
    node = _get_node_or_404(node_id)
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    reading = body.get("reading")
    status = body.get("status", "OK")
    unit = body.get("unit", "C")

    # Find existing sensor and update it
    target_list = node.temperatures if unit in ("C", "F", "") else node.fans
    for sensor in target_list:
        if sensor["Name"] == name:
            if reading is not None:
                sensor["ReadingCelsius" if unit in ("C", "") else "Reading"] = reading
            sensor["Status"] = {"Health": status, "State": "Enabled"}
            return {"node_id": node_id, "sensor": sensor}

    # Not found — add new temperature sensor
    new_sensor = {
        "Name": name,
        "ReadingCelsius": reading,
        "UpperThresholdCritical": body.get("upper_threshold_critical", 85.0),
        "Status": {"Health": status, "State": "Enabled"},
    }
    node.temperatures.append(new_sensor)
    return {"node_id": node_id, "sensor": new_sensor}


@router.post("/nodes/{node_id}/firmware")
async def set_firmware(node_id: int, body: dict):
    """Update a firmware component version. Body: {"component": "BIOS", "version": "2.0.0"}"""
    node = _get_node_or_404(node_id)
    component = body.get("component")
    version = body.get("version")
    if not component or not version:
        raise HTTPException(status_code=400, detail="component and version are required")
    for fw in node.firmware:
        if fw["Id"] == component:
            fw["Version"] = version
            return {"node_id": node_id, "component": component, "version": version}
    raise HTTPException(status_code=404, detail=f"Firmware component '{component}' not found")


@router.post("/nodes/{node_id}/reset")
async def reset_node(node_id: int):
    """Reset a single node to the healthy baseline."""
    node = _get_node_or_404(node_id)
    node.reset_to_healthy()
    return {"node_id": node_id, "status": "reset to healthy baseline"}


# ── Scenario application ──────────────────────────────────────────────────────

def _load_scenario(name: str) -> dict:
    path = _SCENARIOS_DIR / f"{name}.json"
    if not path.exists():
        available = [p.stem for p in _SCENARIOS_DIR.glob("*.json")]
        raise HTTPException(status_code=404, detail=f"Scenario '{name}' not found. Available: {available}")
    return json.loads(path.read_text())


@router.post("/scenario")
async def apply_scenario(body: dict):
    """Apply a named scenario to specific nodes.
    Body: {"name": "degraded", "nodes": [1, 3, 5]}
    """
    name = body.get("name")
    node_ids = body.get("nodes", [])
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    if not node_ids:
        raise HTTPException(status_code=400, detail="nodes list is required")

    scenario = _load_scenario(name)
    overrides = scenario.get("overrides", {})
    results = []
    for nid in node_ids:
        node = _get_node_or_404(nid)
        node.apply_scenario(overrides)
        results.append({"node_id": nid, "applied": name})
    return {"scenario": name, "results": results}


@router.post("/scenario/all")
async def apply_scenario_all(body: dict):
    """Apply a named scenario to ALL nodes. Body: {"name": "degraded"}"""
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    scenario = _load_scenario(name)
    overrides = scenario.get("overrides", {})
    for node in registry.all_nodes().values():
        node.apply_scenario(overrides)
    return {"scenario": name, "applied_to": registry.node_ids()}


@router.get("/scenarios/")
async def list_scenarios():
    """List all available scenario names."""
    return {"scenarios": [p.stem for p in sorted(_SCENARIOS_DIR.glob("*.json"))]}


# ── Global reset ─────────────────────────────────────────────────────────────

@router.post("/reset")
async def reset_all():
    """Reset ALL nodes to the healthy baseline."""
    for node in registry.all_nodes().values():
        node.reset_to_healthy()
    return {"status": "all nodes reset to healthy baseline", "node_count": len(registry.node_ids())}
