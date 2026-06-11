# Redfish BMC Emulator

The emulator is a lightweight FastAPI service that simulates 10 independent BMC nodes using the Redfish REST API. It is designed for local development, integration testing, and CI pipelines — no physical hardware or QEMU required.

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
├── /healthz             ← Health check
└── /docs                ← OpenAPI / Swagger UI
```

Each node is an independent in-memory state machine. State changes on node 3 do not affect node 1. Nodes reset to baseline on container restart or via the `/sim/reset` API.

---

## Quick Start

### Local (no Docker)

```bash
cd emulator
pip install -r requirements.txt
NUM_NODES=10 ADMIN_USER=admin ADMIN_PASS=redfish uvicorn main:app --port 8888 --reload
```

### Docker Compose — emulator only

```bash
docker compose up emulator
```

### Docker Compose — full stack (emulator + Django web app)

```bash
docker compose up
# Django API + SPA at http://localhost:8000
# Emulator API at http://localhost:8888
```

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

The SDK's `session.py` automatically extracts the `/bmc/1` path prefix and prepends it to every Redfish URI, so the standard `/redfish/v1/` paths work transparently.

For the `rf` CLI:

```bash
export RF_HOST=http://localhost:8888/bmc/1
export RF_USER=admin
export RF_PASS=redfish

uv run rf info
uv run rf power status
uv run rf boot once Pxe
```

---

## Redfish API Coverage

The emulator implements every endpoint the SDK uses:

| Area | Endpoints |
|------|-----------|
| Auth | Session create, session delete |
| Service root | `GET /redfish/v1/` |
| Systems | Collection, system detail, PATCH (boot/LED), Reset action, Processors, Memory, Storage, SEL log, Clear log |
| Chassis | Collection, chassis detail, PATCH (LED), Thermal (temps + fans), Power (PSUs + control) |
| Managers | Collection, manager detail, Reset action, NetworkProtocol PATCH, EthernetInterfaces, LogServices |
| AccountService | Collection, list/create/patch/delete accounts |
| UpdateService | FirmwareInventory, SimpleUpdate action, TaskService |

---

## Sim Control API

The `/sim/` prefix provides a control plane for injecting state changes without going through the Redfish API. No authentication required.

### Node inspection

```bash
# List all nodes with current state
curl http://localhost:8888/sim/nodes/

# Full state of node 3
curl http://localhost:8888/sim/nodes/3/
```

### Inject events

```bash
# Set health on node 2 to Warning
curl -X POST http://localhost:8888/sim/nodes/2/health \
  -H "Content-Type: application/json" \
  -d '{"health": "Warning"}'

# Force power off on node 5
curl -X POST http://localhost:8888/sim/nodes/5/power \
  -d '{"power_state": "Off"}' -H "Content-Type: application/json"

# Inject a SEL log entry
curl -X POST http://localhost:8888/sim/nodes/1/sel-event \
  -H "Content-Type: application/json" \
  -d '{"severity": "Critical", "message": "PSU2 failure", "message_id": "Power.1.0.PowerSupplyFailed"}'

# Spike a temperature sensor
curl -X POST http://localhost:8888/sim/nodes/1/sensor \
  -H "Content-Type: application/json" \
  -d '{"name": "CPU1 Temp", "reading": 91.5, "status": "Critical", "unit": "C"}'

# Update a firmware version
curl -X POST http://localhost:8888/sim/nodes/1/firmware \
  -H "Content-Type: application/json" \
  -d '{"component": "BIOS", "version": "2.0.0"}'
```

### Scenarios

Scenarios are JSON files in `emulator/scenarios/`. Each applies a set of field overrides to a node's state.

```bash
# List available scenarios
curl http://localhost:8888/sim/scenarios/

# Apply "degraded" scenario to nodes 1, 2, and 3
curl -X POST http://localhost:8888/sim/scenario \
  -H "Content-Type: application/json" \
  -d '{"name": "degraded", "nodes": [1, 2, 3]}'

# Apply "critical" scenario to ALL nodes
curl -X POST http://localhost:8888/sim/scenario/all \
  -d '{"name": "critical"}' -H "Content-Type: application/json"

# Reset all nodes to healthy baseline
curl -X POST http://localhost:8888/sim/reset

# Reset a single node
curl -X POST http://localhost:8888/sim/nodes/4/reset
```

### Built-in Scenarios

| Name | Health | Effect |
|------|--------|--------|
| `healthy` | OK | All on, normal temps (22°C), all fans running, empty SEL |
| `degraded` | Warning | Elevated temps (46°C inlet), Fan 1A at 0 RPM, one SEL warning entry |
| `critical` | Critical | Temps above critical threshold (62°C inlet, 91°C CPU), PSU2 failed, multiple critical SEL entries |

### Adding Custom Scenarios

Create a new JSON file in `emulator/scenarios/`:

```json
{
  "name": "my-scenario",
  "description": "Custom test scenario",
  "overrides": {
    "health": "Warning",
    "power_state": "On",
    "temperatures": [
      {"Name": "Inlet Temp", "ReadingCelsius": 50.0, "UpperThresholdCritical": 55.0, "Status": {"Health": "Warning", "State": "Enabled"}}
    ],
    "sel_log": [
      {"Id": "1", "Created": "2025-01-01T00:00:00Z", "Severity": "Warning", "Message": "Custom test event", "MessageId": "Test.1.0.TestEvent", "EntryType": "Event"}
    ]
  }
}
```

The `overrides` dict maps directly to `NodeState` attributes. Any attribute listed in `NodeState.__init__` can be overridden.

---

## Node Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `NUM_NODES` | `10` | Number of virtual BMC nodes to create |
| `ADMIN_USER` | `admin` | Admin username (shared across all nodes) |
| `ADMIN_PASS` | `redfish` | Admin password |

---

## Running Integration Tests

```bash
# Start the emulator
docker compose up emulator   # or: cd emulator && uvicorn main:app --port 8888

# Run the integration tests
EMULATOR_URL=http://localhost:8888 pytest tests/integration/ -v
```

If the emulator is unreachable, all integration tests are auto-skipped (not failed), so unit tests can still run in CI without the emulator.

### CI Pipeline

```bash
# Full CI run — emulator + integration tests in Docker
docker compose -f docker-compose.ci.yml up \
  --abort-on-container-exit \
  --exit-code-from tests
```

---

## State Persistence

Node state is **in-memory only** — it resets on container restart. This is intentional for test isolation. If you need to pre-load a specific state, use the sim control API or the scenarios mechanism at test setup time.

---

## File Structure

```
emulator/
├── main.py              Entry point — FastAPI app, route registration, /healthz
├── node.py              NodeState class — all mutable BMC state + helper methods
├── registry.py          NodeRegistry — dict of NodeState, initialized from NUM_NODES
├── routes/
│   ├── deps.py          FastAPI dependencies: get_node, require_auth
│   ├── redfish.py       All /redfish/v1/ route handlers
│   └── sim.py           All /sim/ control route handlers
├── scenarios/
│   ├── healthy.json
│   ├── degraded.json
│   └── critical.json
├── requirements.txt     fastapi, uvicorn, pydantic
└── Dockerfile
```
