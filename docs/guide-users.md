# Redfish User Guide

This guide covers how to interact with a Redfish service — querying hardware state, performing power and boot operations, reading logs, and automating tasks with scripts or SDKs. No prior Redfish experience is assumed, but familiarity with REST APIs and JSON will help.

See [redfish.md](redfish.md) for background on what Redfish is and how it is structured.

---

## Connecting to a Redfish Service

The Redfish service root is always at:

```
https://<bmc-hostname-or-ip>/redfish/v1/
```

All URIs in this guide are relative to that base. The BMC IP is typically on a dedicated management network (IPMI LAN / OOB network), separate from the server's production interfaces.

### Verify Connectivity

```bash
curl -k https://192.168.1.100/redfish/v1/ | python3 -m json.tool
```

The `-k` flag skips TLS verification. In production, replace it with `--cacert /path/to/bmc-ca.pem`.

A successful response returns the service root including `RedfishVersion` and links to top-level collections:

```json
{
    "@odata.type": "#ServiceRoot.v1_15_0.ServiceRoot",
    "@odata.id": "/redfish/v1/",
    "Id": "RootService",
    "Name": "Root Service",
    "RedfishVersion": "1.15.0",
    "Systems": { "@odata.id": "/redfish/v1/Systems/" },
    "Chassis": { "@odata.id": "/redfish/v1/Chassis/" },
    "Managers": { "@odata.id": "/redfish/v1/Managers/" },
    "AccountService": { "@odata.id": "/redfish/v1/AccountService/" },
    "SessionService": { "@odata.id": "/redfish/v1/SessionService/" },
    "EventService": { "@odata.id": "/redfish/v1/EventService/" },
    "UpdateService": { "@odata.id": "/redfish/v1/UpdateService/" }
}
```

---

## Authentication

### Option 1: HTTP Basic Auth (simplest)

Pass credentials on every request. Suitable for one-off queries and scripts.

```bash
curl -k -u admin:password https://192.168.1.100/redfish/v1/Systems/1/
```

### Option 2: Session Token (preferred for multi-request workflows)

Create a session, capture the `X-Auth-Token`, use it for all subsequent requests, then delete the session when done.

**Create session:**

```bash
curl -k -X POST \
  -H "Content-Type: application/json" \
  -d '{"UserName":"admin","Password":"password"}' \
  https://192.168.1.100/redfish/v1/SessionService/Sessions/ \
  -D - \
  -o /dev/null
```

Look for `X-Auth-Token` in the response headers and `Location` for the session URI.

**Use the token:**

```bash
curl -k \
  -H "X-Auth-Token: abc123tokenvalue" \
  https://192.168.1.100/redfish/v1/Systems/1/
```

**Delete session when done:**

```bash
curl -k -X DELETE \
  -H "X-Auth-Token: abc123tokenvalue" \
  https://192.168.1.100/redfish/v1/SessionService/Sessions/1
```

---

## Querying System Information

### List All Systems

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Systems/
```

Response includes a `Members` array. Each member has an `@odata.id` pointing to a specific system.

### Get System Summary

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Systems/1/
```

Key fields to look at:

| Field | What It Tells You |
|-------|------------------|
| `PowerState` | Whether the server is on/off |
| `Status.Health` | Aggregate health rollup |
| `Status.State` | `Enabled`, `Absent`, `Disabled` |
| `BiosVersion` | Installed BIOS version |
| `MemorySummary.TotalSystemMemoryGiB` | Total RAM |
| `ProcessorSummary.Count` | Number of sockets |
| `ProcessorSummary.Model` | CPU model string |
| `HostName` | OS-reported hostname |
| `SerialNumber` | Chassis serial |
| `SKU` | Vendor SKU/part number |

### Get CPU Details

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Systems/1/Processors/
```

Then drill into a specific processor:

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Systems/1/Processors/CPU1/
```

Fields include `TotalCores`, `TotalThreads`, `MaxSpeedMHz`, `ProcessorArchitecture`.

### Get Memory Details

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Systems/1/Memory/
```

Each DIMM entry reports `CapacityMiB`, `MemoryType` (DDR4/DDR5), `OperatingSpeedMhz`, `Manufacturer`, `PartNumber`, and `Status.Health`.

### Get Storage Information

```bash
# Storage controllers
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Systems/1/Storage/

# Drives attached to a controller
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Systems/1/Storage/RAID1/Drives/

# Individual drive
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Systems/1/Storage/RAID1/Drives/Drive1/
```

Drive fields: `CapacityBytes`, `RotationSpeedRPM`, `Protocol` (SAS/SATA/NVMe), `MediaType` (HDD/SSD), `PredictedMediaLifeLeftPercent`, `Status.Health`.

### Get Sensor Data (Temperature, Fans, Power)

Sensor data lives under Chassis, not Systems:

```bash
# Thermal sensors (temperatures + fans)
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Chassis/1/Thermal/

# Power supplies and input power
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Chassis/1/Power/
```

The `Temperatures` array includes each probe's `ReadingCelsius`, `UpperThresholdCritical`, and `Status`. The `Fans` array includes `Reading` (RPM or percent) and `Status`. The `PowerSupplies` array includes `LineInputVoltage`, `PowerOutputWatts`, and `Status.Health`.

### Get Network Interface Info

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Systems/1/EthernetInterfaces/
```

---

## Power Operations

Power actions are sent via HTTP POST to the `Actions` sub-resource of a System.

### Check Current Power State

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Systems/1/ | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['PowerState'])"
```

### Power On

```bash
curl -k -u admin:password \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"ResetType":"On"}' \
  https://192.168.1.100/redfish/v1/Systems/1/Actions/ComputerSystem.Reset
```

### Graceful Shutdown

Sends an ACPI shutdown signal to the OS. The OS performs a clean shutdown.

```bash
curl -k -u admin:password \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"ResetType":"GracefulShutdown"}' \
  https://192.168.1.100/redfish/v1/Systems/1/Actions/ComputerSystem.Reset
```

### Force Power Off (Hard Power Cut)

Immediately cuts power — equivalent to holding the physical power button.

```bash
curl -k -u admin:password \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"ResetType":"ForceOff"}' \
  https://192.168.1.100/redfish/v1/Systems/1/Actions/ComputerSystem.Reset
```

### Graceful Restart

```bash
curl -k -u admin:password \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"ResetType":"GracefulRestart"}' \
  https://192.168.1.100/redfish/v1/Systems/1/Actions/ComputerSystem.Reset
```

### Force Restart (Hard Reset)

```bash
curl -k -u admin:password \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"ResetType":"ForceRestart"}' \
  https://192.168.1.100/redfish/v1/Systems/1/Actions/ComputerSystem.Reset
```

### NMI (Non-Maskable Interrupt)

Triggers an NMI, used to generate crash dumps on hung systems.

```bash
curl -k -u admin:password \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"ResetType":"Nmi"}' \
  https://192.168.1.100/redfish/v1/Systems/1/Actions/ComputerSystem.Reset
```

### Valid ResetType Values

| ResetType | Effect |
|-----------|--------|
| `On` | Power on from off state |
| `ForceOff` | Immediate power cut |
| `GracefulShutdown` | ACPI shutdown signal |
| `GracefulRestart` | ACPI restart signal |
| `ForceRestart` | Hard reset (power cycle) |
| `Nmi` | Inject NMI |
| `ForceOn` | Force power on even if in error state |
| `PushPowerButton` | Simulate front-panel button press |

Not all values are supported by all implementations. Check `AllowableValues` in the action's `target` property.

---

## Boot Override

Boot override lets you direct the next boot (or all boots) to a specific source without changing persistent BIOS settings.

### View Current Boot Settings

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Systems/1/ | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d['Boot'], indent=2))"
```

Key fields:

| Field | Meaning |
|-------|---------|
| `BootSourceOverrideTarget` | Current override target |
| `BootSourceOverrideEnabled` | `Disabled`, `Once`, `Continuous` |
| `BootSourceOverrideMode` | `Legacy` (BIOS) or `UEFI` |
| `BootSourceOverrideTarget@Redfish.AllowableValues` | What this system supports |

### Set One-Time PXE Boot

```bash
curl -k -u admin:password \
  -X PATCH \
  -H "Content-Type: application/json" \
  -d '{"Boot":{"BootSourceOverrideTarget":"Pxe","BootSourceOverrideEnabled":"Once"}}' \
  https://192.168.1.100/redfish/v1/Systems/1/
```

### Set One-Time Boot from USB

```bash
curl -k -u admin:password \
  -X PATCH \
  -H "Content-Type: application/json" \
  -d '{"Boot":{"BootSourceOverrideTarget":"Usb","BootSourceOverrideEnabled":"Once"}}' \
  https://192.168.1.100/redfish/v1/Systems/1/
```

### Set One-Time UEFI Shell Boot

```bash
curl -k -u admin:password \
  -X PATCH \
  -H "Content-Type: application/json" \
  -d '{"Boot":{"BootSourceOverrideTarget":"UefiShell","BootSourceOverrideEnabled":"Once","BootSourceOverrideMode":"UEFI"}}' \
  https://192.168.1.100/redfish/v1/Systems/1/
```

### Clear Boot Override (revert to normal)

```bash
curl -k -u admin:password \
  -X PATCH \
  -H "Content-Type: application/json" \
  -d '{"Boot":{"BootSourceOverrideTarget":"None","BootSourceOverrideEnabled":"Disabled"}}' \
  https://192.168.1.100/redfish/v1/Systems/1/
```

### Common BootSourceOverrideTarget Values

`None`, `Pxe`, `Floppy`, `Cd`, `Usb`, `Hdd`, `BiosSetup`, `Utilities`, `Diags`, `UefiShell`, `UefiTarget`, `SDCard`, `UefiHttp`, `RemoteDrive`

---

## Reading System Event Logs

### List Log Services

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Systems/1/LogServices/
```

Common log services: `Sel` (System Event Log), `Log1`, `PostCodes`.

### Get Log Entries

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Systems/1/LogServices/Sel/Entries/
```

Each entry has:

| Field | Meaning |
|-------|---------|
| `Id` | Entry ID (monotonically increasing) |
| `Created` | ISO 8601 timestamp |
| `Severity` | `OK`, `Warning`, `Critical` |
| `Message` | Human-readable message |
| `MessageId` | Registry-qualified ID for machine parsing |
| `SensorType` | What type of sensor triggered the entry |
| `EntryType` | `Event`, `SEL`, `Oem` |

### Clear Log Entries

```bash
curl -k -u admin:password \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{}' \
  https://192.168.1.100/redfish/v1/Systems/1/LogServices/Sel/Actions/LogService.ClearLog
```

---

## Using the Python Redfish SDK

The DMTF maintains an official Python library: `python-redfish-library`.

```bash
pip install redfish
```

### Basic Example

```python
import redfish

# Connect
client = redfish.redfish_client(
    base_url="https://192.168.1.100",
    username="admin",
    password="password",
    cacheck=False  # set to True in production with valid certs
)
client.login(auth="session")

# Get system info
response = client.get("/redfish/v1/Systems/1/")
system = response.dict
print(f"Power: {system['PowerState']}")
print(f"Health: {system['Status']['Health']}")
print(f"BIOS: {system['BiosVersion']}")

# Power on
client.post(
    "/redfish/v1/Systems/1/Actions/ComputerSystem.Reset",
    body={"ResetType": "On"}
)

# Logout
client.logout()
```

### Iterate All Systems

```python
import redfish

client = redfish.redfish_client(base_url="https://192.168.1.100", username="admin", password="password")
client.login(auth="session")

systems = client.get("/redfish/v1/Systems/").dict
for member in systems["Members"]:
    system = client.get(member["@odata.id"]).dict
    print(f"{system['Id']}: {system['HostName']} — {system['PowerState']} — {system['Status']['Health']}")

client.logout()
```

---

## Subscribing to Events

Redfish can push events to your endpoint (webhook) when hardware state changes.

### Create an Event Subscription

```bash
curl -k -u admin:password \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "Destination": "https://your-collector.example.com/redfish-events",
    "Protocol": "Redfish",
    "EventTypes": ["Alert", "ResourceUpdated", "StatusChange"],
    "Context": "server-rack-A"
  }' \
  https://192.168.1.100/redfish/v1/EventService/Subscriptions/
```

The response `Location` header contains the subscription URI. Save it to delete the subscription later.

### List Subscriptions

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/EventService/Subscriptions/
```

### Delete a Subscription

```bash
curl -k -u admin:password \
  -X DELETE \
  https://192.168.1.100/redfish/v1/EventService/Subscriptions/1
```

---

## Identify/Locate a Server (UID LED)

Turn on the physical identification LED to locate a server in a rack:

```bash
curl -k -u admin:password \
  -X PATCH \
  -H "Content-Type: application/json" \
  -d '{"IndicatorLED": "Blinking"}' \
  https://192.168.1.100/redfish/v1/Systems/1/
```

Turn it off:

```bash
curl -k -u admin:password \
  -X PATCH \
  -H "Content-Type: application/json" \
  -d '{"IndicatorLED": "Off"}' \
  https://192.168.1.100/redfish/v1/Systems/1/
```

Valid values: `Lit`, `Blinking`, `Off`.

---

## Scripting Patterns

### Poll for Power State After Reset

```python
import redfish, time

def wait_for_power_state(client, system_uri, target_state, timeout=300):
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = client.get(system_uri).dict.get("PowerState")
        print(f"  PowerState: {state}")
        if state == target_state:
            return True
        time.sleep(10)
    return False

client = redfish.redfish_client(base_url="https://192.168.1.100", username="admin", password="password")
client.login(auth="session")

client.post("/redfish/v1/Systems/1/Actions/ComputerSystem.Reset", body={"ResetType": "GracefulShutdown"})
if wait_for_power_state(client, "/redfish/v1/Systems/1/", "Off"):
    print("Server is off")
else:
    print("Timeout waiting for shutdown")

client.logout()
```

### Collect Inventory Across a Fleet

```python
import redfish, csv, sys

hosts = ["192.168.1.100", "192.168.1.101", "192.168.1.102"]
writer = csv.DictWriter(sys.stdout, fieldnames=["host", "serial", "bios", "ram_gib", "cpus", "health"])
writer.writeheader()

for host in hosts:
    try:
        c = redfish.redfish_client(base_url=f"https://{host}", username="admin", password="password")
        c.login(auth="session")
        s = c.get("/redfish/v1/Systems/1/").dict
        writer.writerow({
            "host": host,
            "serial": s.get("SerialNumber"),
            "bios": s.get("BiosVersion"),
            "ram_gib": s.get("MemorySummary", {}).get("TotalSystemMemoryGiB"),
            "cpus": s.get("ProcessorSummary", {}).get("Count"),
            "health": s.get("Status", {}).get("Health"),
        })
        c.logout()
    except Exception as e:
        print(f"ERROR {host}: {e}", file=sys.stderr)
```

---

## Troubleshooting

### 401 Unauthorized

- Verify username/password are correct.
- Check account lockout: too many failed attempts may lock the account temporarily.
- Confirm the account has sufficient privileges for the operation.

### 403 Forbidden

- The authenticated account exists but lacks permission for this resource or action.
- Check with an admin to confirm your role assignment.

### 404 Not Found

- The URI may differ between vendors. Retrieve the service root and traverse links rather than constructing URIs by hand.
- The resource (e.g., a specific Drive) may have been removed.

### SSL/TLS Errors

- BMC uses a self-signed certificate by default. Use `--cacert` with the exported BMC CA, or `-k` during development only.
- Verify the BMC's time is synchronized — certificate validation failures are often caused by clock skew.

### 500 Internal Server Error

- The BMC may be busy or in a transient error state.
- Wait 30–60 seconds and retry.
- Check the Manager log for BMC-side errors.

### Slow Responses

- Redfish on BMCs is resource-constrained. Avoid parallel requests to the same BMC.
- Add a short delay (0.5–1s) between sequential requests in scripts.
- Session auth is lighter than Basic Auth for repeated requests.
