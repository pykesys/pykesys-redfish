# Redfish BMC Emulator

The emulator is a lightweight FastAPI service that simulates up to `NUM_NODES` independent BMC nodes using the Redfish REST API. It is designed for local development, integration testing, and CI pipelines — no physical hardware or QEMU required.

## Table of Contents

- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Node Identity and Defaults](#node-identity-and-defaults)
- [Connecting the SDK to the Emulator](#connecting-the-sdk-to-the-emulator)
- [Redfish API Coverage](#redfish-api-coverage)
- [Sim Control API](#sim-control-api)
  - [Node inspection](#node-inspection)
  - [Event injection](#event-injection)
  - [Scenarios](#scenarios)
  - [Global reset](#global-reset)
- [Built-in Scenarios](#built-in-scenarios)
- [Adding Custom Scenarios](#adding-custom-scenarios)
- [Authentication](#authentication)
- [Node Configuration](#node-configuration)
- [Running Integration Tests](#running-integration-tests)
- [State Persistence](#state-persistence)
- [File Structure](#file-structure)

---

## Architecture

```
http://localhost:8888
│
├── /bmc/1/redfish/v1/   ← Node 1 — full Redfish API (auth, systems, chassis, managers, …)
├── /bmc/2/redfish/v1/   ← Node 2
│   …
├── /bmc/10/redfish/v1/  ← Node 10
│
├── /sim/                ← Sim control API (no auth — inject events, apply scenarios)
├── /healthz             ← Health check endpoint
└── /docs                ← OpenAPI / Swagger UI
```

Each node is an independent in-memory state machine (`NodeState`). State changes on node 3 do not affect node 1. Nodes reset to baseline on container restart or via `/sim/reset`.

[↑ Back to Top](#table-of-contents)

---

## Quick Start

### Local (no Docker)

```bash
cd emulator
pip install -r requirements.txt
NUM_NODES=10 uvicorn main:app --port 8888 --reload
```

### Via run-dashboard.sh

```bash
./run-dashboard.sh emulator
```

### Docker Compose — emulator only

```bash
docker compose up emulator
```

### Docker Compose — full stack (emulator + Django web app)

```bash
docker compose up
# Django API + SPA at http://localhost:8000
# Emulator API     at http://localhost:8888
```

[↑ Back to Top](#table-of-contents)

---

## Node Identity and Defaults

Each node boots with a unique identity derived from its `node_id` (1-based integer):

| Field | Pattern | Example (node 3) |
|-------|---------|-----------------|
| `hostname` | `sim-node-{id:02d}.bmc.local` | `sim-node-03.bmc.local` |
| `model` | `SimServer G{group}00` (groups of 3) | `SimServer G100` |
| `serial_number` | `SIM{id:04d}` | `SIM0003` |
| `manufacturer` | `PyKeSys Sim` | `PyKeSys Sim` |
| `memory_gib` | `128 + ((id-1) % 4) * 64` | `256` GiB |
| `processor_count` | `2` | `2` |
| `processor_model` | `Sim Xeon 6438M` | `Sim Xeon 6438M` |
| `bios_version` | `1.0.0` | `1.0.0` |
| `bmc_firmware_version` | `4.0.0` | `4.0.0` |
| `inlet_temp` | `21.0 + id * 0.3 °C` | `21.9 °C` |

**Memory sizing across a 10-node fleet** (rotates every 4 nodes):

| Node IDs | Memory |
|----------|--------|
| 1, 5, 9 | 128 GiB |
| 2, 6, 10 | 192 GiB |
| 3, 7 | 256 GiB |
| 4, 8 | 320 GiB |

**Default sensors per node:**

| Type | Name | Default reading |
|------|------|----------------|
| Temperature | Inlet Temp | 21.0 + node_id × 0.3 °C |
| Temperature | CPU1 Temp | 44.0 °C |
| Temperature | CPU2 Temp | 42.0 °C |
| Fan | Fan 1A | 3200 RPM |
| Fan | Fan 1B | 3100 RPM |
| Fan | Fan 2A | 3300 RPM |
| Fan | Fan 2B | 3250 RPM |
| PSU | PSU1 | 450 W, 220 V, OK |
| PSU | PSU2 | 448 W, 220 V, OK |

**Default firmware inventory:**

| ID | Name | Version | Updateable |
|----|------|---------|-----------|
| `BIOS` | System BIOS | 1.0.0 | Yes |
| `BMC` | BMC Firmware | 4.0.0 | Yes |
| `NIC1` | Network Adapter 1 | 22.0.7 | No |
| `HBA1` | Storage HBA | 3.1.2 | No |

**Default mutable state:**

| Field | Default |
|-------|---------|
| `power_state` | `On` |
| `health` | `OK` |
| `indicator_led` | `Off` |
| `boot_override_target` | `None` |
| `boot_override_enabled` | `Disabled` |
| `sel_log` | empty |
| `accounts` | empty (admin only) |

[↑ Back to Top](#table-of-contents)

---

## Connecting the SDK to the Emulator

Each node is addressable via a path-prefixed URL: `http://localhost:8888/bmc/{node_id}`.

```python
from pykesys_redfish import RedfishClient

# Connect to node 1
with RedfishClient("http://localhost:8888/bmc/1", "admin", "redfish", verify_ssl=False) as rf:
    system = rf.system()
    print(system.power_state)   # "On"
    print(system.health)        # "OK"
    system.graceful_restart()
```

The SDK's `RedfishSession` automatically extracts the `/bmc/1` path prefix and prepends it to every Redfish URI — standard `/redfish/v1/` paths resolve correctly without any special configuration.

**Fleet of all 10 nodes:**

```python
from pykesys_redfish.fleet import FleetManager

fm = FleetManager(
    hosts=[f"http://localhost:8888/bmc/{i}" for i in range(1, 11)],
    username="admin",
    password="redfish",
    verify_ssl=False,
)
inventory = fm.collect_inventory()
print(fm.health_summary())
```

**CLI:**

```bash
export RF_HOST=http://localhost:8888/bmc/1
export RF_USER=admin
export RF_PASS=redfish

uv run rf info
uv run rf power status
uv run rf boot once Pxe
uv run rf logs list
```

[↑ Back to Top](#table-of-contents)

---

## Redfish API Coverage

The emulator implements every endpoint the SDK uses:

| Area | Endpoint | Methods |
|------|----------|---------|
| Service root | `/redfish/v1/` | GET |
| Session service | `/redfish/v1/SessionService/Sessions/` | POST, DELETE |
| Systems | `/redfish/v1/Systems/` | GET |
| System | `/redfish/v1/Systems/1/` | GET, PATCH |
| System reset | `/redfish/v1/Systems/1/Actions/ComputerSystem.Reset` | POST |
| Processors | `/redfish/v1/Systems/1/Processors/` | GET |
| Memory | `/redfish/v1/Systems/1/Memory/` | GET |
| Storage | `/redfish/v1/Systems/1/Storage/` | GET |
| SEL log entries | `/redfish/v1/Systems/1/LogServices/Sel/Entries/` | GET |
| SEL clear | `/redfish/v1/Systems/1/LogServices/Sel/Actions/LogService.ClearLog` | POST |
| Chassis | `/redfish/v1/Chassis/` | GET |
| Chassis detail | `/redfish/v1/Chassis/1/` | GET, PATCH |
| Thermal | `/redfish/v1/Chassis/1/Thermal/` | GET |
| Power | `/redfish/v1/Chassis/1/Power/` | GET |
| Managers | `/redfish/v1/Managers/` | GET |
| Manager | `/redfish/v1/Managers/BMC/` | GET |
| Manager reset | `/redfish/v1/Managers/BMC/Actions/Manager.Reset` | POST |
| Network protocol | `/redfish/v1/Managers/BMC/NetworkProtocol/` | GET, PATCH |
| Ethernet interfaces | `/redfish/v1/Managers/BMC/EthernetInterfaces/` | GET |
| Manager logs | `/redfish/v1/Managers/BMC/LogServices/Log1/Entries/` | GET |
| Account service | `/redfish/v1/AccountService/` | GET, PATCH |
| Accounts | `/redfish/v1/AccountService/Accounts/` | GET, POST |
| Account detail | `/redfish/v1/AccountService/Accounts/{id}/` | GET, PATCH, DELETE |
| Firmware inventory | `/redfish/v1/UpdateService/FirmwareInventory/` | GET |
| Firmware item | `/redfish/v1/UpdateService/FirmwareInventory/{id}/` | GET |
| SimpleUpdate | `/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate` | POST |

All paths above are relative to `/bmc/{node_id}` — e.g., the full URL for node 3's system is `http://localhost:8888/bmc/3/redfish/v1/Systems/1/`.

[↑ Back to Top](#table-of-contents)

---

## Sim Control API

The `/sim/` prefix provides a control plane for injecting state changes without going through the Redfish API. **No authentication required.**

### Complete endpoint reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/sim/nodes/` | List all nodes with current state summary |
| GET | `/sim/nodes/{id}/` | Full state of a single node |
| POST | `/sim/nodes/{id}/health` | Set node health |
| POST | `/sim/nodes/{id}/power` | Set node power state directly |
| POST | `/sim/nodes/{id}/sel-event` | Inject a SEL log entry |
| POST | `/sim/nodes/{id}/sensor` | Update or add a sensor reading |
| POST | `/sim/nodes/{id}/firmware` | Update a firmware component version |
| POST | `/sim/nodes/{id}/reset` | Reset one node to healthy baseline |
| GET | `/sim/scenarios/` | List available scenario names |
| POST | `/sim/scenario` | Apply scenario to specific nodes |
| POST | `/sim/scenario/all` | Apply scenario to all nodes |
| POST | `/sim/reset` | Reset ALL nodes to healthy baseline |

### Node inspection

```bash
# List all nodes with current state
curl http://localhost:8888/sim/nodes/

# Full state of node 3 (all fields including sensors, firmware, SEL)
curl http://localhost:8888/sim/nodes/3/
```

### Event injection

```bash
# Set health on node 2
curl -X POST http://localhost:8888/sim/nodes/2/health \
  -H "Content-Type: application/json" \
  -d '{"health": "Warning"}'
# health values: "OK" | "Warning" | "Critical"

# Force power state on node 5
curl -X POST http://localhost:8888/sim/nodes/5/power \
  -H "Content-Type: application/json" \
  -d '{"power_state": "Off"}'
# power_state values: "On" | "Off" | "PoweringOn" | "PoweringOff"

# Inject a SEL log entry
curl -X POST http://localhost:8888/sim/nodes/1/sel-event \
  -H "Content-Type: application/json" \
  -d '{"severity": "Critical", "message": "PSU2 failure", "message_id": "Power.1.0.PowerSupplyFailed"}'

# Update or add a temperature sensor
curl -X POST http://localhost:8888/sim/nodes/1/sensor \
  -H "Content-Type: application/json" \
  -d '{"name": "CPU1 Temp", "reading": 91.5, "status": "Critical", "unit": "C"}'

# Add a fan reading (unit != "C" routes to fans list)
curl -X POST http://localhost:8888/sim/nodes/2/sensor \
  -H "Content-Type: application/json" \
  -d '{"name": "Fan 1A", "reading": 0, "status": "Critical", "unit": "RPM"}'

# Update a firmware version
curl -X POST http://localhost:8888/sim/nodes/1/firmware \
  -H "Content-Type: application/json" \
  -d '{"component": "BIOS", "version": "2.0.0"}'
# component must match an existing firmware Id: "BIOS" | "BMC" | "NIC1" | "HBA1"
```

### Scenarios

```bash
# List available scenarios
curl http://localhost:8888/sim/scenarios/

# Apply "degraded" to nodes 1, 2, 3
curl -X POST http://localhost:8888/sim/scenario \
  -H "Content-Type: application/json" \
  -d '{"name": "degraded", "nodes": [1, 2, 3]}'

# Apply "critical" to ALL nodes
curl -X POST http://localhost:8888/sim/scenario/all \
  -H "Content-Type: application/json" \
  -d '{"name": "critical"}'
```

### Global reset

```bash
# Reset ALL nodes to healthy baseline
curl -X POST http://localhost:8888/sim/reset

# Reset a single node
curl -X POST http://localhost:8888/sim/nodes/4/reset
```

[↑ Back to Top](#table-of-contents)

---

## Built-in Scenarios

| Name | Health | Power | Inlet Temp | SEL entries | Notes |
|------|--------|-------|------------|-------------|-------|
| `healthy` | OK | On | ~22 °C | 0 | All fans running, PSUs OK, empty SEL |
| `degraded` | Warning | On | 46 °C | 1 warning | Fan 1A at 0 RPM, inlet temp elevated |
| `critical` | Critical | On | 62 °C | 3 critical | CPU1 at 91 °C, PSU2 failed, multiple critical SEL entries |

[↑ Back to Top](#table-of-contents)

---

## Adding Custom Scenarios

Create a JSON file in `emulator/scenarios/`:

```json
{
  "name": "my-scenario",
  "description": "Custom test scenario",
  "overrides": {
    "health": "Warning",
    "power_state": "On",
    "temperatures": [
      {
        "Name": "Inlet Temp",
        "ReadingCelsius": 50.0,
        "UpperThresholdCritical": 55.0,
        "Status": {"Health": "Warning", "State": "Enabled"}
      }
    ],
    "sel_log": [
      {
        "Id": "1",
        "Created": "2025-01-01T00:00:00Z",
        "Severity": "Warning",
        "Message": "Custom test event",
        "MessageId": "Test.1.0.TestEvent",
        "EntryType": "Event"
      }
    ]
  }
}
```

The `overrides` dict maps directly to `NodeState` attributes. Any attribute defined in `NodeState.__init__` is settable: `health`, `power_state`, `indicator_led`, `boot_override_target`, `boot_override_enabled`, `temperatures`, `fans`, `power_supplies`, `firmware`, `sel_log`.

The scenario is available immediately — no restart required:

```bash
curl -X POST http://localhost:8888/sim/scenario \
  -H "Content-Type: application/json" \
  -d '{"name": "my-scenario", "nodes": [1]}'
```

[↑ Back to Top](#table-of-contents)

---

## Authentication

Each node accepts two authentication methods, mirroring the real Redfish spec:

**Session token (default):**
```bash
# Create session
TOKEN=$(curl -s -X POST http://localhost:8888/bmc/1/redfish/v1/SessionService/Sessions/ \
  -H "Content-Type: application/json" \
  -d '{"UserName":"admin","Password":"redfish"}' \
  | jq -r '.["@odata.id"]')
# X-Auth-Token is in the response headers

# Use token
curl -H "X-Auth-Token: <token>" http://localhost:8888/bmc/1/redfish/v1/Systems/
```

**HTTP Basic:**
```bash
curl -u admin:redfish http://localhost:8888/bmc/1/redfish/v1/Systems/
```

Sessions are per-node. A token for node 1 is not valid for node 2.

[↑ Back to Top](#table-of-contents)

---

## Node Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `NUM_NODES` | `10` | Number of virtual BMC nodes |
| `ADMIN_USER` | `admin` | Admin username (all nodes) |
| `ADMIN_PASS` | `redfish` | Admin password (all nodes) |

[↑ Back to Top](#table-of-contents)

---

## Running Integration Tests

```bash
# Start the emulator
./run-dashboard.sh emulator
# or: cd emulator && uvicorn main:app --port 8888

# Run the integration tests
EMULATOR_URL=http://localhost:8888 uv run pytest tests/integration/ -v
```

The integration tests auto-skip (not fail) when `EMULATOR_URL` is unreachable, so unit tests pass cleanly in CI without an emulator.

```bash
# Convenience wrappers
./run_tests_local.sh integration    # auto-starts emulator
./runtests.sh integration           # same

# Full CI (Docker — emulator + integration tests)
docker compose -f docker-compose.ci.yml up \
  --abort-on-container-exit \
  --exit-code-from tests
```

[↑ Back to Top](#table-of-contents)

---

## State Persistence

Node state is **in-memory only** and resets on restart. This is intentional for test isolation. To pre-load a specific state, use the sim control API or scenarios at test setup time:

```python
# In a pytest fixture
import requests

@pytest.fixture(autouse=True)
def reset_emulator():
    requests.post(f"{EMULATOR_URL}/sim/reset")
    yield
    requests.post(f"{EMULATOR_URL}/sim/reset")
```

[↑ Back to Top](#table-of-contents)

---

## File Structure

```
emulator/
├── main.py              FastAPI app — startup, route registration, /healthz
├── node.py              NodeState — all mutable BMC state + session/power/SEL helpers
├── registry.py          NodeRegistry — dict of NodeState, initialized from NUM_NODES
├── routes/
│   ├── deps.py          FastAPI dependencies: get_node, require_auth (token + Basic)
│   ├── redfish.py       All /bmc/{node_id}/redfish/v1/ route handlers
│   └── sim.py           All /sim/ control route handlers
├── scenarios/
│   ├── healthy.json     All-OK baseline
│   ├── degraded.json    Warning state — elevated temps, fan fault
│   └── critical.json    Critical state — thermal breach, PSU fault, SEL flood
├── requirements.txt     fastapi, uvicorn[standard], pydantic
└── Dockerfile
```

[↑ Back to Top](#table-of-contents)
