# User Guide — pykesys-redfish

This guide covers everything a user of this stack needs: the web observability dashboard, the `rf` CLI, the Python SDK, and direct Redfish API access via `curl`. No prior Redfish experience is assumed.

See [redfish.md](redfish.md) for Redfish protocol background, [sdk.md](sdk.md) for the full SDK reference, and [cli.md](cli.md) for the complete CLI reference.

## Table of Contents

- [Web Observability Dashboard](#web-observability-dashboard)
  - [Accessing the dashboard](#accessing-the-dashboard)
  - [Fleet overview](#fleet-overview)
  - [Host detail](#host-detail)
  - [Alerts](#alerts)
  - [REST API](#rest-api)
- [rf CLI](#rf-cli)
  - [Installation](#installation)
  - [Credentials](#credentials)
  - [Command reference](#command-reference)
- [Python SDK](#python-sdk)
  - [Single BMC](#single-bmc)
  - [Fleet operations](#fleet-operations)
- [Direct Redfish API (curl)](#direct-redfish-api-curl)
  - [Connecting](#connecting)
  - [Authentication](#authentication)
  - [Querying system information](#querying-system-information)
  - [Power operations](#power-operations)
  - [Boot override](#boot-override)
  - [Reading event logs](#reading-event-logs)
  - [Sensor data](#sensor-data)
  - [Identification LED](#identification-led)
  - [Event subscriptions](#event-subscriptions)
- [Scripting Patterns](#scripting-patterns)
- [Troubleshooting](#troubleshooting)

---

## Web Observability Dashboard

The web app (`redfish_web/` + `frontend/`) provides a React SPA backed by a Django REST API. It polls all registered BMC hosts on a configurable interval and stores inventory snapshots, sensor readings, log entries, and alert events.

### Accessing the dashboard

| Mode | URL |
|------|-----|
| Docker Compose (full stack) | `http://localhost:8000` |
| Local dev server | `http://localhost:8000` (Django) + `http://localhost:5173` (Vite) |

```bash
# Start full stack
docker compose up

# Or run locally
./run-dashboard.sh all    # Django + React + emulator in background
```

### Fleet overview

The dashboard home page (`/`) shows a grid of all registered BMC hosts. Each card displays:

- Hostname and BMC address
- Current power state (`On` / `Off`) with color coding
- Health rollup (`OK` / `Warning` / `Critical`)
- Last polled timestamp
- Any open alert events

Click any host card to open the host detail view.

### Host detail

The host detail page (`/hosts/{id}`) shows:

**Summary tab** — current snapshot: system model, serial, BIOS version, memory, processor count/model, health, power state.

**Sensors tab** — latest sensor readings from the most recent snapshot: all temperature probes (°C with thresholds) and fan speeds (RPM).

**Logs tab** — SEL entries stored from the last poll, filterable by severity.

**Snapshots tab** — historical inventory timeline. Click any row to see the full snapshot detail including raw JSON.

**Actions** (top-right button group):
- **Poll now** — trigger an immediate out-of-cycle poll for this host
- **Power** — send a power reset (`GracefulRestart` default, configurable)
- **Boot** — set a one-time boot override target

### Alerts

The Alerts page (`/alerts`) lists all open and historical alert events.

**Alert rules** are configured by an admin (see [Admin Guide — Alert rules configuration](guide-admin.md#alert-rules-configuration)). When a polled snapshot matches a rule condition, an alert event is created and (optionally) a Slack webhook is called.

**Resolving an alert** — click the Resolve button on any open event. This sets `resolved_at` and closes the event. The rule continues to evaluate on future polls; a new event is created if the condition is matched again.

### REST API

The web app exposes a REST API for automation and integration.

#### Hosts

```bash
# List all registered BMC hosts
curl http://localhost:8000/api/hosts/

# Create a new host
curl -X POST http://localhost:8000/api/hosts/ \
  -H "Content-Type: application/json" \
  -d '{
    "host": "bmc-dgx-01.mgmt",
    "display_name": "DGX Node 01",
    "username": "admin",
    "password": "secret",
    "poll_interval": 60,
    "verify_ssl": false
  }'

# Get a specific host
curl http://localhost:8000/api/hosts/1/

# Update poll interval
curl -X PATCH http://localhost:8000/api/hosts/1/ \
  -H "Content-Type: application/json" \
  -d '{"poll_interval": 120}'

# Trigger an immediate poll
curl -X POST http://localhost:8000/api/hosts/1/poll/

# Delete a host
curl -X DELETE http://localhost:8000/api/hosts/1/
```

#### Power and boot actions (via API)

```bash
# Graceful restart via web API
curl -X POST http://localhost:8000/api/hosts/1/power/ \
  -H "Content-Type: application/json" \
  -d '{"reset_type": "GracefulRestart"}'

# Force power off
curl -X POST http://localhost:8000/api/hosts/1/power/ \
  -H "Content-Type: application/json" \
  -d '{"reset_type": "ForceOff"}'

# Set one-time PXE boot
curl -X POST http://localhost:8000/api/hosts/1/boot/ \
  -H "Content-Type: application/json" \
  -d '{"target": "Pxe", "enabled": "Once"}'

# Clear boot override
curl -X POST http://localhost:8000/api/hosts/1/boot/ \
  -H "Content-Type: application/json" \
  -d '{"target": "None", "enabled": "Disabled"}'
```

#### Fleet dashboard data

```bash
# All hosts with their latest snapshot embedded
curl http://localhost:8000/api/fleet/
```

#### Inventory and sensors

```bash
# Snapshot history for host 1
curl http://localhost:8000/api/hosts/1/snapshots/

# Specific snapshot (full detail with raw JSON)
curl http://localhost:8000/api/hosts/1/snapshots/42/

# Sensor readings from the latest snapshot
curl http://localhost:8000/api/hosts/1/sensors/

# SEL log entries stored from polls
curl http://localhost:8000/api/hosts/1/logs/
```

#### Alert rules and events

```bash
# List alert rules
curl http://localhost:8000/api/alerts/rules/

# List open alert events
curl "http://localhost:8000/api/alerts/events/?open=true"

# List events for a specific host
curl "http://localhost:8000/api/alerts/events/?host=1"

# Resolve an event
curl -X POST http://localhost:8000/api/alerts/events/7/resolve/
```

[↑ Back to Top](#table-of-contents)

---

## rf CLI

The `rf` CLI provides single-BMC operations from the terminal. It uses the same `RedfishClient` as the SDK.

### Installation

```bash
# Install with uv (within the project)
uv sync
uv run rf --help

# Or install the package globally
pip install pykesys-redfish
rf --help
```

### Credentials

Set once per environment via environment variables to avoid typing credentials on every command:

```bash
export RF_HOST=https://192.168.1.100   # or http://localhost:8888/bmc/1 for emulator
export RF_USER=admin
export RF_PASS=password
export RF_VERIFY_SSL=false             # only if using self-signed/no cert
```

All three can also be passed per-command:

```bash
uv run rf --host https://bmc.example.com --user admin --pass secret info
```

If credentials are missing, the CLI will prompt interactively.

### Command reference

#### `rf info`

Show a full system summary table.

```bash
uv run rf info
```

Output: Rich table with ID, hostname, manufacturer, model, serial, BIOS version, power state, health, RAM (GiB), CPU count, CPU model.

---

#### `rf power`

```bash
rf power status             # Show current power state
rf power on                 # ResetType=On
rf power off                # ResetType=GracefulShutdown
rf power off --force        # ResetType=ForceOff (immediate — no OS shutdown)
rf power reset              # ResetType=GracefulRestart (default)
rf power reset --type <T>   # Any ResetType value
rf power nmi                # Inject NMI (triggers crash dump)
```

Valid `--type` values: `On`, `ForceOff`, `GracefulShutdown`, `GracefulRestart`, `ForceRestart`, `Nmi`, `ForceOn`, `PushPowerButton`.

---

#### `rf boot`

```bash
rf boot status              # Show current boot override settings and allowed values
rf boot once <target>       # Set one-time boot override
rf boot once Pxe            # PXE boot on next boot only
rf boot once Hdd            # Hard drive
rf boot once BiosSetup      # BIOS setup screen
rf boot once Pxe --mode UEFI   # Explicit UEFI mode
rf boot clear               # Clear override, revert to normal boot order
```

Common `target` values: `None`, `Pxe`, `Hdd`, `Cd`, `Usb`, `BiosSetup`, `UefiShell`. Supported values for your specific BMC are shown by `rf boot status` under "Allowed".

---

#### `rf logs`

```bash
rf logs list                          # Last 50 SEL entries (default)
rf logs list --limit 100              # Last 100 entries
rf logs list --service System         # Different log service
rf logs clear                         # Prompts for confirmation
rf logs clear --yes                   # Skip confirmation
rf logs clear --service AuditLog
```

---

#### `rf firmware`

```bash
rf firmware list                        # List all firmware components and versions
rf firmware update <image-uri>          # Trigger SimpleUpdate from HTTPS URI
rf firmware update https://fw.example.com/bios-2.1.bin
rf firmware update <uri> --target /redfish/v1/UpdateService/FirmwareInventory/BIOS
```

The update command sends `SimpleUpdate` and prints the task URI if the BMC returns one.

---

#### `rf accounts`

```bash
rf accounts list                        # List all user accounts
rf accounts create <username>           # Create account (prompts for password)
rf accounts create operator1 --role Operator
rf accounts create readonly1 --role ReadOnly
rf accounts delete <account-uri>        # Prompts for confirmation
rf accounts delete /redfish/v1/AccountService/Accounts/3/ --yes
```

---

#### Global options

All commands accept:

| Option | Short | Description |
|--------|-------|-------------|
| `--host` | `-H` | BMC hostname or URL (overrides `RF_HOST`) |
| `--user` | `-u` | Username (overrides `RF_USER`) |
| `--pass` | `-p` | Password (overrides `RF_PASS`) |
| `--no-verify` | | Disable TLS certificate verification |

[↑ Back to Top](#table-of-contents)

---

## Python SDK

For anything beyond single-BMC operations — scripting, automation, fleet management — use the `pykesys_redfish` SDK. See [sdk.md](sdk.md) for the full reference.

### Single BMC

```python
from pykesys_redfish import RedfishClient

with RedfishClient("https://192.168.1.100", "admin", "password") as rf:
    system = rf.system()

    # Read hardware state
    print(f"Model:   {system.model}")
    print(f"Serial:  {system.serial_number}")
    print(f"BIOS:    {system.bios_version}")
    print(f"RAM:     {system.total_memory_gib} GiB")
    print(f"CPUs:    {system.processor_count}x {system.processor_model}")
    print(f"Power:   {system.power_state}")
    print(f"Health:  {system.health}")

    # Power operations
    system.graceful_restart()
    system.power_off()           # graceful shutdown
    system.power_off()           # hard power cut (ForceOff)

    # Boot override — PXE on next boot
    system.set_boot_once("Pxe")
    system.power_on()

    # Read SEL
    for entry in system.log_entries():
        print(f"[{entry['Severity']}] {entry['Created']}: {entry['Message']}")

    # Thermal
    chassis = rf.chassis()
    for temp in chassis.temperatures():
        print(f"{temp['Name']}: {temp.get('ReadingCelsius')}°C")
```

**Against the emulator:**

```bash
export RF_HOST=http://localhost:8888/bmc/1
export RF_USER=admin
export RF_PASS=redfish
export RF_VERIFY_SSL=false
```

```python
from pykesys_redfish import RedfishClient

with RedfishClient.from_env() as rf:
    system = rf.system()
    print(system.summary())
```

### Fleet operations

```python
from pykesys_redfish.fleet import FleetManager

# DGX SuperPod — 10 nodes
fm = FleetManager(
    hosts=[f"bmc-dgx-{i:02d}.mgmt" for i in range(1, 11)],
    username="admin",
    password="password",
)

# Health check before maintenance window
summary = fm.health_summary()
print(f"OK={summary['health_ok']}  "
      f"Warning={summary['health_warning']}  "
      f"Critical={summary['health_critical']}  "
      f"Errors={summary['errors']}")

# Collect full inventory
results = fm.collect_inventory()
fm.export_csv(results, "dgx-inventory.csv")
fm.export_json(results, "dgx-inventory.json")

# PXE boot entire fleet for OS imaging
def pxe_boot(rf, host):
    s = rf.system()
    s.set_boot_once("Pxe")
    s.power_on() if s.power_state == "Off" else s.graceful_restart()
    return {"host": host, "status": "pxe triggered"}

fm.run(pxe_boot)

# Graceful shutdown for maintenance
fm.power_all("GracefulShutdown")
```

[↑ Back to Top](#table-of-contents)

---

## Direct Redfish API (curl)

These examples use `curl` for direct API access — useful for one-off queries, debugging, and shell scripts without a Python environment.

The variable `BMC` is used throughout for brevity:

```bash
BMC="https://192.168.1.100"
AUTH="-u admin:password"

# Or use session token (see Authentication below)
TOKEN="abc123tokenvalue"
AUTH="-H 'X-Auth-Token: ${TOKEN}'"
```

For the emulator:

```bash
BMC="http://localhost:8888/bmc/1"
AUTH="-u admin:redfish"
```

### Connecting

The Redfish service root is always at `/redfish/v1/`:

```bash
curl -k $AUTH ${BMC}/redfish/v1/ | python3 -m json.tool
```

`-k` skips TLS verification. In production use `--cacert /path/to/bmc-ca.pem`.

A successful response returns `RedfishVersion` and links to top-level collections.

### Authentication

#### HTTP Basic Auth

Suitable for one-off queries and scripts:

```bash
curl -k -u admin:password ${BMC}/redfish/v1/Systems/1/
```

#### Session token

Preferred for multi-request workflows — single auth round-trip, lighter BMC load:

```bash
# Create session — capture X-Auth-Token from response headers
TOKEN=$(curl -sk -X POST \
  -H "Content-Type: application/json" \
  -d '{"UserName":"admin","Password":"password"}' \
  ${BMC}/redfish/v1/SessionService/Sessions/ \
  -D /dev/stderr -o /dev/null 2>&1 \
  | grep -i x-auth-token | awk '{print $2}' | tr -d '\r')

# Use the token on subsequent requests
curl -k -H "X-Auth-Token: ${TOKEN}" ${BMC}/redfish/v1/Systems/1/

# Delete session when done
curl -k -X DELETE \
  -H "X-Auth-Token: ${TOKEN}" \
  ${BMC}/redfish/v1/SessionService/Sessions/1
```

### Querying system information

#### System summary

```bash
curl -k $AUTH ${BMC}/redfish/v1/Systems/1/ | python3 -m json.tool
```

Key fields:

| Field | Description |
|-------|-------------|
| `PowerState` | `On`, `Off`, `PoweringOn`, `PoweringOff` |
| `Status.Health` | `OK`, `Warning`, `Critical` |
| `BiosVersion` | Running BIOS version |
| `MemorySummary.TotalSystemMemoryGiB` | Total installed RAM |
| `ProcessorSummary.Count` | CPU socket count |
| `ProcessorSummary.Model` | CPU model string |
| `HostName` | OS-reported hostname |
| `SerialNumber` | Chassis serial |

#### CPU details

```bash
curl -k $AUTH ${BMC}/redfish/v1/Systems/1/Processors/
curl -k $AUTH ${BMC}/redfish/v1/Systems/1/Processors/CPU1/
```

Fields: `TotalCores`, `TotalThreads`, `MaxSpeedMHz`, `ProcessorArchitecture`.

#### Memory (DIMMs)

```bash
curl -k $AUTH ${BMC}/redfish/v1/Systems/1/Memory/
```

Each DIMM: `CapacityMiB`, `MemoryType` (DDR4/DDR5), `OperatingSpeedMhz`, `Manufacturer`, `PartNumber`, `Status.Health`.

#### Storage

```bash
# Controllers
curl -k $AUTH ${BMC}/redfish/v1/Systems/1/Storage/

# Drives on a controller
curl -k $AUTH ${BMC}/redfish/v1/Systems/1/Storage/RAID1/Drives/

# Individual drive
curl -k $AUTH ${BMC}/redfish/v1/Systems/1/Storage/RAID1/Drives/Drive1/
```

Drive fields: `CapacityBytes`, `Protocol` (SAS/SATA/NVMe), `MediaType` (HDD/SSD), `PredictedMediaLifeLeftPercent`, `Status.Health`.

#### Network interfaces

```bash
curl -k $AUTH ${BMC}/redfish/v1/Systems/1/EthernetInterfaces/
```

### Power operations

Power actions POST to `Actions/ComputerSystem.Reset`:

```bash
# Power on
curl -k $AUTH -X POST -H "Content-Type: application/json" \
  -d '{"ResetType":"On"}' \
  ${BMC}/redfish/v1/Systems/1/Actions/ComputerSystem.Reset

# Graceful shutdown
curl -k $AUTH -X POST -H "Content-Type: application/json" \
  -d '{"ResetType":"GracefulShutdown"}' \
  ${BMC}/redfish/v1/Systems/1/Actions/ComputerSystem.Reset

# Hard power cut
curl -k $AUTH -X POST -H "Content-Type: application/json" \
  -d '{"ResetType":"ForceOff"}' \
  ${BMC}/redfish/v1/Systems/1/Actions/ComputerSystem.Reset

# Graceful restart
curl -k $AUTH -X POST -H "Content-Type: application/json" \
  -d '{"ResetType":"GracefulRestart"}' \
  ${BMC}/redfish/v1/Systems/1/Actions/ComputerSystem.Reset

# Hard reset (power cycle — no OS shutdown)
curl -k $AUTH -X POST -H "Content-Type: application/json" \
  -d '{"ResetType":"ForceRestart"}' \
  ${BMC}/redfish/v1/Systems/1/Actions/ComputerSystem.Reset

# NMI — triggers crash dump on hung systems
curl -k $AUTH -X POST -H "Content-Type: application/json" \
  -d '{"ResetType":"Nmi"}' \
  ${BMC}/redfish/v1/Systems/1/Actions/ComputerSystem.Reset
```

**ResetType reference:**

| ResetType | Effect |
|-----------|--------|
| `On` | Power on from off state |
| `ForceOff` | Immediate power cut |
| `GracefulShutdown` | ACPI shutdown signal to OS |
| `GracefulRestart` | ACPI restart signal to OS |
| `ForceRestart` | Hard reset (power cycle, no OS notification) |
| `Nmi` | Inject Non-Maskable Interrupt |
| `ForceOn` | Force power on even if in error state |
| `PushPowerButton` | Simulate front-panel button |

Not all values are supported by all BMC implementations. Check `AllowableValues` in the system's `Actions` object.

### Boot override

#### Check current boot settings

```bash
curl -k $AUTH ${BMC}/redfish/v1/Systems/1/ \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d['Boot'], indent=2))"
```

| Field | Meaning |
|-------|---------|
| `BootSourceOverrideTarget` | Active override target |
| `BootSourceOverrideEnabled` | `Disabled`, `Once`, `Continuous` |
| `BootSourceOverrideMode` | `Legacy` (BIOS) or `UEFI` |
| `BootSourceOverrideTarget@Redfish.AllowableValues` | What this BMC supports |

#### Set one-time PXE boot

```bash
curl -k $AUTH -X PATCH -H "Content-Type: application/json" \
  -d '{"Boot":{"BootSourceOverrideTarget":"Pxe","BootSourceOverrideEnabled":"Once"}}' \
  ${BMC}/redfish/v1/Systems/1/
```

#### One-time BIOS setup (UEFI mode)

```bash
curl -k $AUTH -X PATCH -H "Content-Type: application/json" \
  -d '{"Boot":{"BootSourceOverrideTarget":"BiosSetup","BootSourceOverrideEnabled":"Once","BootSourceOverrideMode":"UEFI"}}' \
  ${BMC}/redfish/v1/Systems/1/
```

#### Clear boot override

```bash
curl -k $AUTH -X PATCH -H "Content-Type: application/json" \
  -d '{"Boot":{"BootSourceOverrideTarget":"None","BootSourceOverrideEnabled":"Disabled"}}' \
  ${BMC}/redfish/v1/Systems/1/
```

Common target values: `None`, `Pxe`, `Hdd`, `Cd`, `Usb`, `BiosSetup`, `UefiShell`, `UefiHttp`, `RemoteDrive`.

### Reading event logs

```bash
# List available log services
curl -k $AUTH ${BMC}/redfish/v1/Systems/1/LogServices/

# Get SEL entries
curl -k $AUTH ${BMC}/redfish/v1/Systems/1/LogServices/Sel/Entries/

# Get Manager (BMC) log
curl -k $AUTH ${BMC}/redfish/v1/Managers/1/LogServices/Log1/Entries/

# Clear SEL
curl -k $AUTH -X POST -H "Content-Type: application/json" -d '{}' \
  ${BMC}/redfish/v1/Systems/1/LogServices/Sel/Actions/LogService.ClearLog
```

Each log entry has: `Id`, `Created` (ISO 8601), `Severity` (`OK`/`Warning`/`Critical`), `Message`, `MessageId`, `SensorType`, `EntryType`.

### Sensor data

Sensor data lives under Chassis, not Systems:

```bash
# Temperatures and fans
curl -k $AUTH ${BMC}/redfish/v1/Chassis/1/Thermal/

# Power supplies and input power
curl -k $AUTH ${BMC}/redfish/v1/Chassis/1/Power/
```

`Temperatures[]`: `ReadingCelsius`, `UpperThresholdCritical`, `UpperThresholdNonCritical`, `Status.Health`.
`Fans[]`: `Reading` (RPM or %), `ReadingUnits`, `Status.Health`.
`PowerSupplies[]`: `LineInputVoltage`, `PowerOutputWatts`, `Status.Health`.
`PowerControl[0].PowerConsumedWatts`: total system power draw.

### Identification LED

Turn on the physical UID LED to locate a server in a rack:

```bash
# Blink the UID LED
curl -k $AUTH -X PATCH -H "Content-Type: application/json" \
  -d '{"IndicatorLED":"Blinking"}' \
  ${BMC}/redfish/v1/Systems/1/

# Turn it off
curl -k $AUTH -X PATCH -H "Content-Type: application/json" \
  -d '{"IndicatorLED":"Off"}' \
  ${BMC}/redfish/v1/Systems/1/
```

Valid values: `Lit`, `Blinking`, `Off`. The chassis also has an IndicatorLED at `/Chassis/1/`.

### Event subscriptions

Redfish can push events to a webhook when hardware state changes:

```bash
# Subscribe
curl -k $AUTH -X POST -H "Content-Type: application/json" \
  -d '{
    "Destination": "https://your-collector.example.com/redfish-events",
    "Protocol": "Redfish",
    "EventTypes": ["Alert", "ResourceUpdated", "StatusChange"],
    "Context": "dgx-superpod-rack-A"
  }' \
  ${BMC}/redfish/v1/EventService/Subscriptions/

# List subscriptions
curl -k $AUTH ${BMC}/redfish/v1/EventService/Subscriptions/

# Delete a subscription
curl -k $AUTH -X DELETE ${BMC}/redfish/v1/EventService/Subscriptions/1
```

[↑ Back to Top](#table-of-contents)

---

## Scripting Patterns

### Poll for power state after a reset (SDK)

```python
import time
from pykesys_redfish import RedfishClient

def wait_for_power_state(rf, target: str, timeout: int = 300) -> bool:
    deadline = time.time() + timeout
    system = rf.system()
    while time.time() < deadline:
        system.refresh()
        state = system.power_state
        print(f"  PowerState: {state}")
        if state == target:
            return True
        time.sleep(10)
    return False

with RedfishClient("https://192.168.1.100", "admin", "password") as rf:
    rf.system().graceful_shutdown()
    if wait_for_power_state(rf, "Off"):
        print("Server is off")
    else:
        print("Timeout waiting for shutdown — trying ForceOff")
        rf.system().power_off()
```

### Fleet health check before maintenance

```python
from pykesys_redfish.fleet import FleetManager

fm = FleetManager(
    hosts=[f"bmc-dgx-{i:02d}.mgmt" for i in range(1, 11)],
    username="admin",
    password="password",
)
summary = fm.health_summary()

if summary["health_critical"] > 0 or summary["errors"] > 0:
    print("⚠  Fleet not healthy — do not proceed with maintenance")
    for host in summary["error_hosts"]:
        print(f"  ERROR: {host}")
else:
    print(f"✓  Fleet healthy ({summary['total']} nodes, {summary['health_ok']} OK)")
```

### Collect and export inventory

```python
from pykesys_redfish.fleet import FleetManager

fm = FleetManager(hosts=[...], username="admin", password="password")
results = fm.collect_inventory()
fm.export_csv(results, "inventory.csv")
fm.export_json(results, "inventory.json")

failed = [r for r in results if "error" in r]
if failed:
    print(f"{len(failed)} hosts failed:")
    for r in failed:
        print(f"  {r['host']}: {r['error']}")
```

### Poll for power state after a reset (curl / bash)

```bash
BMC="https://192.168.1.100"
AUTH="-u admin:password"

# Send graceful shutdown
curl -sk $AUTH -X POST -H "Content-Type: application/json" \
  -d '{"ResetType":"GracefulShutdown"}' \
  ${BMC}/redfish/v1/Systems/1/Actions/ComputerSystem.Reset

# Poll until Off
for i in $(seq 1 30); do
    STATE=$(curl -sk $AUTH ${BMC}/redfish/v1/Systems/1/ | python3 -c "import sys,json; print(json.load(sys.stdin)['PowerState'])")
    echo "  PowerState: $STATE"
    [ "$STATE" = "Off" ] && echo "Server is off" && break
    sleep 10
done
```

### Register a host in the web app and trigger a poll

```bash
# Add the host
HOST_ID=$(curl -s -X POST http://localhost:8000/api/hosts/ \
  -H "Content-Type: application/json" \
  -d '{
    "host": "bmc-dgx-01.mgmt",
    "display_name": "DGX Node 01",
    "username": "admin",
    "password": "secret",
    "poll_interval": 60,
    "verify_ssl": false
  }' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo "Created host ID: $HOST_ID"

# Trigger immediate poll
curl -s -X POST "http://localhost:8000/api/hosts/${HOST_ID}/poll/"
```

[↑ Back to Top](#table-of-contents)

---

## Troubleshooting

### 401 Unauthorized

- Verify username and password.
- Account lockout: too many failed attempts may lock the account temporarily.
- Check that the account has sufficient privileges for the requested operation.

### 403 Forbidden

- The account exists but its role does not permit this operation.
- `Operator` accounts cannot perform account management.
- `ReadOnly` accounts cannot perform any write operations.

### 404 Not Found

- URI formats vary between vendors. Retrieve the service root and traverse `@odata.id` links rather than guessing URIs.
- The resource may not exist on this specific BMC implementation.

### SSL/TLS errors

- BMCs use self-signed certificates by default. Use `--cacert` with the exported BMC CA cert, or `-k` during development only.
- Clock skew causes certificate validation failures. Verify NTP is configured correctly.
- For the SDK: pass `verify_ssl=False` only in development environments.

### RedfishTimeoutError

- The BMC may be busy, booting, or running a firmware update.
- Increase the timeout: `RedfishClient(..., timeout=60.0)`.
- The BMC management processor can be slow to respond during POST or under heavy polling.

### RedfishConflictError (409)

- Attempting to power on a system that is already `On`, or power off a system that is already `Off`.
- Attempting to create an account that already exists.
- Catch this exception and treat it as a no-op for idempotent scripts.

### 500 / 503

- BMC may be temporarily overloaded. Wait 30–60 seconds and retry.
- A BMC reset may be in progress.
- Check the Manager log for BMC-side error details.

### Web app shows "last_error" for a host

- Click the host in the dashboard and check `last_error`.
- Common causes: BMC unreachable (network issue), wrong credentials, SSL certificate error.
- Use `./run-dashboard.sh dev` + check Django server logs, or trigger `POST /api/hosts/{id}/poll/` and inspect the response.

### Slow CLI / SDK responses

- BMC management processors are resource-constrained. Add a short delay between sequential requests in loops.
- Avoid parallel requests to the same BMC — most BMCs serialize concurrent Redfish requests internally.
- Session auth is lighter than Basic Auth for repeated requests.

[↑ Back to Top](#table-of-contents)
