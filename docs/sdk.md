# SDK Reference — pykesys_redfish

`pykesys_redfish` is a typed Python library for the DMTF Redfish BMC management API. It handles session lifecycle, HTTP transport, error mapping, lazy resource caching, and concurrent fleet operations.

See [redfish.md](redfish.md) for Redfish protocol background and [fleet.md](fleet.md) for FleetManager deep-dive.

## Table of Contents

- [Installation](#installation)
- [Architecture](#architecture)
- [Session Lifecycle](#session-lifecycle)
- [RedfishClient](#redfishclient)
  - [Constructor](#constructor)
  - [from_env()](#from_env)
  - [Context manager](#context-manager)
  - [Resource accessors](#resource-accessors)
  - [Raw HTTP](#raw-http)
- [Resource Classes](#resource-classes)
  - [RedfishResource (base)](#redfishresource-base)
  - [ComputerSystem](#computersystem)
  - [Chassis](#chassis)
  - [Manager](#manager)
  - [Storage and Drive](#storage-and-drive)
  - [AccountService](#accountservice)
- [FleetManager](#fleetmanager)
  - [Constructor](#fleetmanager-constructor)
  - [Built-in operations](#built-in-operations)
  - [Custom operations](#custom-operations)
  - [Reporting and export](#reporting-and-export)
- [Exceptions](#exceptions)
- [Environment Variables](#environment-variables)
- [Authentication Modes](#authentication-modes)
- [Path-Prefix URLs](#path-prefix-urls)
- [Error Handling Patterns](#error-handling-patterns)
- [Concurrency and Thread Safety](#concurrency-and-thread-safety)
- [Recipes](#recipes)

---

## Installation

```bash
# With uv (recommended)
uv add pykesys-redfish

# With pip
pip install pykesys-redfish
```

Requires Python 3.10+. Runtime dependencies: `httpx`, `typer`, `rich`.

[↑ Back to Top](#table-of-contents)

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Your code / CLI / FleetManager                     │  ← automation layer
├─────────────────────────────────────────────────────┤
│  RedfishClient                                      │  ← entry point / resource factory
├─────────────────────────────────────────────────────┤
│  ComputerSystem │ Chassis │ Manager │ AccountService │  ← typed resource wrappers
│  Storage │ Drive                                    │
├─────────────────────────────────────────────────────┤
│  RedfishResource (base)  — lazy cache + refresh()   │  ← cache layer
├─────────────────────────────────────────────────────┤
│  RedfishSession           — HTTP + auth             │  ← transport layer
│    ↳ httpx.Client                                   │
└─────────────────────────────────────────────────────┘
```

**Key design decisions:**

- `RedfishClient` is a context manager. The httpx transport and Redfish session are both created on `__enter__` and cleaned up on `__exit__`, even if an exception occurs during connect.
- Resource objects are lazy. No HTTP request fires until you first access a property. The fetched JSON is cached in `_data`; call `.refresh()` to invalidate.
- All methods that mutate state (`power_on`, `set_boot_once`, etc.) call `.refresh()` after the mutating request so the next property read reflects the new state.
- `FleetManager` spawns one `RedfishClient` per host in a `ThreadPoolExecutor`. Workers are isolated — no shared state between threads.

[↑ Back to Top](#table-of-contents)

---

## Session Lifecycle

When you enter a `RedfishClient` context:

1. `httpx.Client` is created with the configured `base_url`, `verify`, and `timeout`.
2. A Redfish session is created: `POST /redfish/v1/SessionService/Sessions/` with `{"UserName": ..., "Password": ...}`.
3. The response `X-Auth-Token` header is stored and sent on every subsequent request.
4. The `Location` header (or `@odata.id` in the body) is stored as the session URI.

When you exit the context (normally or via exception):

1. `DELETE` is sent to the session URI with the stored token. Errors are silently suppressed — a failed logout does not raise.
2. `httpx.Client.close()` is called unconditionally.

If `_create_session()` fails (e.g. wrong credentials), the httpx transport is still cleaned up — no resource leak.

With `auth="basic"`, step 2–4 are skipped; credentials are sent as HTTP Basic on every request instead.

[↑ Back to Top](#table-of-contents)

---

## RedfishClient

### Constructor

```python
RedfishClient(
    base_url: str,
    username: str,
    password: str,
    verify_ssl: bool = True,
    timeout: float = 30.0,
    auth: str = "session",   # "session" | "basic"
)
```

| Parameter | Description |
|-----------|-------------|
| `base_url` | BMC base URL. For standard BMCs: `"https://192.168.1.100"`. For the emulator: `"http://localhost:8888/bmc/1"`. See [Path-Prefix URLs](#path-prefix-urls). |
| `username` | Redfish account username |
| `password` | Redfish account password |
| `verify_ssl` | `False` disables TLS certificate verification. Use only in development. |
| `timeout` | Per-request timeout in seconds. Applies to connect and read. |
| `auth` | `"session"` (default) — creates a Redfish session token. `"basic"` — sends HTTP Basic credentials on every request. |

### from_env()

```python
rf = RedfishClient.from_env()
```

Reads `RF_HOST`, `RF_USER`, `RF_PASS` from the environment. `RF_VERIFY_SSL=false` disables TLS verification. Raises `KeyError` if any required variable is missing.

```bash
export RF_HOST=https://bmc.example.com
export RF_USER=admin
export RF_PASS=supersecret

python -c "
from pykesys_redfish import RedfishClient
with RedfishClient.from_env() as rf:
    print(rf.system().summary())
"
```

### Context manager

Always use `RedfishClient` as a context manager:

```python
# Correct — session created and destroyed automatically
with RedfishClient("https://bmc", "admin", "pass") as rf:
    system = rf.system()
    print(system.power_state)

# Also valid — manual lifecycle
rf = RedfishClient("https://bmc", "admin", "pass")
rf.connect()
try:
    system = rf.system()
finally:
    rf.close()
```

### Resource accessors

Each accessor queries the corresponding Redfish collection and returns a typed wrapper for the nth member (0-indexed).

```python
rf.system(index=0)          # → ComputerSystem
rf.chassis(index=0)         # → Chassis
rf.manager(index=0)         # → Manager
rf.account_service()        # → AccountService
```

`index` is rarely needed — most single-socket servers expose exactly one system, one chassis, and one manager. For multi-node chassis use a higher index:

```python
system_a = rf.system(0)
system_b = rf.system(1)
```

If `index` is out of range or the collection is empty, `RedfishNotFoundError` is raised with a descriptive message.

### Raw HTTP

For endpoints not covered by a resource class:

```python
# GET — returns dict
data = rf.get("/redfish/v1/UpdateService/FirmwareInventory/")

# POST — returns dict or None (None on 204)
result = rf.post(
    "/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
    {"TransferProtocol": "HTTPS", "ImageURI": "https://firmware.example.com/bios-2.0.bin"},
)

# PATCH — returns dict or None
rf.patch("/redfish/v1/Systems/1/", {"AssetTag": "rack-5-slot-3"})

# DELETE
rf.delete("/redfish/v1/AccountService/Accounts/3/")
```

All four methods raise the appropriate `RedfishError` subclass on HTTP 4xx/5xx and `RedfishTimeoutError` on network timeout.

[↑ Back to Top](#table-of-contents)

---

## Resource Classes

### RedfishResource (base)

All resource classes inherit from `RedfishResource`. You rarely interact with it directly, but its contract matters:

```python
resource.uri        # str — the Redfish URI this object represents
resource.refresh()  # invalidate cache; next property access re-fetches
```

The `_fetch()` method fires a `GET` to `uri` on first access and stores the result in `_data`. Subsequent property accesses read from `_data` without any HTTP request. After a mutating call (PATCH, POST action), the resource calls `refresh()` so the next read reflects the updated server state.

---

### ComputerSystem

Returned by `rf.system()`. Wraps a `#ComputerSystem.v1_x_x.ComputerSystem` Redfish resource.

#### Properties

| Property | Type | Redfish field |
|----------|------|--------------|
| `id` | `str \| None` | `Id` |
| `hostname` | `str \| None` | `HostName` |
| `serial_number` | `str \| None` | `SerialNumber` |
| `model` | `str \| None` | `Model` |
| `sku` | `str \| None` | `SKU` |
| `manufacturer` | `str \| None` | `Manufacturer` |
| `bios_version` | `str \| None` | `BiosVersion` |
| `power_state` | `str \| None` | `PowerState` (`On`, `Off`, `PoweringOn`, `PoweringOff`) |
| `health` | `str \| None` | `Status.Health` (`OK`, `Warning`, `Critical`) |
| `state` | `str \| None` | `Status.State` (`Enabled`, `Absent`, `Disabled`) |
| `total_memory_gib` | `float \| None` | `MemorySummary.TotalSystemMemoryGiB` |
| `processor_count` | `int \| None` | `ProcessorSummary.Count` |
| `processor_model` | `str \| None` | `ProcessorSummary.Model` |
| `boot_source_override_target` | `str \| None` | `Boot.BootSourceOverrideTarget` |
| `boot_source_override_enabled` | `str \| None` | `Boot.BootSourceOverrideEnabled` |
| `boot_allowable_values` | `list[str]` | `Boot.BootSourceOverrideTarget@Redfish.AllowableValues` |
| `indicator_led` | `str \| None` | `IndicatorLED` (`Off`, `Lit`, `Blinking`) |

#### Power actions

All power methods POST to `Actions/ComputerSystem.Reset`. If the `target` URI is present in the `Actions` dict it is used; otherwise the method falls back to `<system_uri>/Actions/ComputerSystem.Reset`.

```python
system = rf.system()

system.power_on()           # ResetType=On
system.power_off()          # ResetType=ForceOff    (immediate — no OS shutdown)
system.graceful_shutdown()  # ResetType=GracefulShutdown
system.graceful_restart()   # ResetType=GracefulRestart
system.force_restart()      # ResetType=ForceRestart
system.nmi()                # ResetType=Nmi  (triggers crash dump)

# Arbitrary reset type
system.reset("PushPowerButton")
```

`RedfishConflictError` (409) is raised if the BMC rejects the request because the system is already in the requested state. For example, calling `power_on()` on a system that is already `On` will raise 409 on most BMC implementations.

#### Boot override

```python
# One-time PXE boot
system.set_boot_once("Pxe")

# One-time BIOS setup with explicit mode
system.set_boot_once("BiosSetup", mode="UEFI")

# Available targets (BMC-reported)
print(system.boot_allowable_values)
# ['None', 'Pxe', 'Hdd', 'Cd', 'Usb', 'BiosSetup', 'UefiShell']

# Clear override — revert to normal boot order
system.clear_boot_override()
```

`set_boot_once` always sets `BootSourceOverrideEnabled: "Once"`. For `"Continuous"` override, use the raw `rf.patch()` method.

#### Identification LED

```python
system.identify()            # "Blinking" (default)
system.identify("Lit")       # solid on
system.identify_off()        # off
```

#### Hardware sub-collections

These methods each fire one HTTP request per member in the collection.

```python
# Raw processor dicts from /redfish/v1/Systems/1/Processors/
for cpu in system.processors():
    print(cpu["Model"], cpu["TotalCores"])

# Raw DIMM dicts from /redfish/v1/Systems/1/Memory/
for dimm in system.memory():
    print(dimm["Name"], dimm.get("CapacityMiB"), "MiB")

# Storage controller objects (typed)
for controller in system.storage():
    print(controller.id, controller.health)
    for drive in controller.drives():
        print(f"  {drive.model} {drive.capacity_gib:.0f} GiB {drive.health}")
```

#### SEL log

```python
# Default log service is "Sel"; some BMCs use "System" or "Manager"
entries = system.log_entries()       # list[dict]
entries = system.log_entries("System")

for e in entries:
    print(e["Created"], e["Severity"], e["Message"])

# Clear the log
system.clear_log()
system.clear_log("System")
```

#### summary()

Returns a flat dict suitable for CSV/JSON export and fleet reporting:

```python
{
    "id": "1",
    "hostname": "server01.example.com",
    "serial_number": "ABC123",
    "model": "PowerEdge R750",
    "manufacturer": "Dell",
    "bios_version": "2.1.0",
    "power_state": "On",
    "health": "OK",
    "total_memory_gib": 256.0,
    "processor_count": 2,
    "processor_model": "Intel Xeon Gold 6338",
}
```

---

### Chassis

Returned by `rf.chassis()`. Wraps a `#Chassis.v1_x_x.Chassis` resource — the physical enclosure.

#### Properties

| Property | Type | Redfish field |
|----------|------|--------------|
| `id` | `str \| None` | `Id` |
| `chassis_type` | `str \| None` | `ChassisType` (e.g. `RackMount`, `Blade`) |
| `manufacturer` | `str \| None` | `Manufacturer` |
| `model` | `str \| None` | `Model` |
| `serial_number` | `str \| None` | `SerialNumber` |
| `health` | `str \| None` | `Status.Health` |
| `indicator_led` | `str \| None` | `IndicatorLED` |

#### Thermal

Both methods GET `/Thermal/` on the chassis URI. They share the same request; if you need both, call them together to avoid a double fetch — or use the raw `rf.get()` and parse yourself.

```python
for temp in chassis.temperatures():
    name = temp["Name"]
    reading = temp.get("ReadingCelsius")
    upper = temp.get("UpperThresholdCritical")
    health = temp.get("Status", {}).get("Health")
    print(f"{name}: {reading}°C  (critical: {upper}°C)  [{health}]")

for fan in chassis.fans():
    print(fan["Name"], fan.get("Reading"), fan.get("ReadingUnits"), fan.get("Status", {}).get("Health"))
```

#### Power

```python
for psu in chassis.power_supplies():
    print(psu["Name"], psu.get("PowerOutputWatts"), "W", psu.get("Status", {}).get("Health"))

watts = chassis.power_consumed_watts()  # float | None
print(f"Total draw: {watts} W")
```

#### LED

```python
chassis.identify()         # "Blinking"
chassis.identify("Lit")
chassis.identify_off()
```

---

### Manager

Returned by `rf.manager()`. Wraps a `#Manager.v1_x_x.Manager` resource — the BMC itself.

#### Properties

| Property | Type | Redfish field |
|----------|------|--------------|
| `id` | `str \| None` | `Id` |
| `manager_type` | `str \| None` | `ManagerType` (e.g. `BMC`) |
| `model` | `str \| None` | `Model` |
| `firmware_version` | `str \| None` | `FirmwareVersion` |
| `health` | `str \| None` | `Status.Health` |

#### Network protocols

```python
protos = manager.network_protocols()   # dict — full NetworkProtocol resource

# Enable/disable a protocol by name
manager.set_protocol_enabled("SSH", True)
manager.set_protocol_enabled("Telnet", False)

# Configure NTP
manager.set_ntp_servers(["ntp1.corp.example.com", "ntp2.corp.example.com"])
```

#### Network interfaces

```python
for iface in manager.ethernet_interfaces():
    print(iface["Id"], iface.get("IPv4Addresses"))
```

#### BMC reset

```python
manager.reset()                      # GracefulRestart (default)
manager.reset("ForceRestart")
manager.reset_to_defaults()          # ResetAll (default)
manager.reset_to_defaults("PreserveNetworkAndUsers")
```

**Warning:** `reset_to_defaults()` erases BMC configuration. Use with caution.

#### BMC log

```python
for entry in manager.log_entries():          # Log1 (default)
    print(entry["Created"], entry["Severity"], entry["Message"])

for entry in manager.log_entries("AuditLog"):
    print(entry)
```

---

### Storage and Drive

`Storage` objects come from `system.storage()`; `Drive` objects from `storage.drives()`.

#### Storage properties and methods

| Member | Type | Description |
|--------|------|-------------|
| `id` | `str \| None` | Controller ID |
| `name` | `str \| None` | Controller name |
| `health` | `str \| None` | Controller health |
| `drives()` | `list[Drive]` | All attached drives |
| `volumes()` | `list[dict]` | Logical volume dicts |
| `summary()` | `dict` | `{id, name, health, drive_count}` |

#### Drive properties

| Property | Type | Description |
|----------|------|-------------|
| `id` | `str \| None` | Drive ID |
| `name` | `str \| None` | Drive name |
| `health` | `str \| None` | `OK`, `Warning`, `Critical` |
| `capacity_bytes` | `int \| None` | Raw capacity in bytes |
| `capacity_gib` | `float \| None` | Capacity rounded to 1 decimal GiB |
| `protocol` | `str \| None` | `SAS`, `SATA`, `NVMe`, `FC`, etc. |
| `media_type` | `str \| None` | `HDD`, `SSD`, `SMR` |
| `model` | `str \| None` | Drive model string |
| `serial_number` | `str \| None` | Drive serial |
| `predicted_life_left_pct` | `int \| None` | SSD wear indicator (0-100) |

```python
for controller in rf.system().storage():
    print(f"Controller: {controller.id}  health={controller.health}")
    for drive in controller.drives():
        print(f"  {drive.model}  {drive.capacity_gib:.1f} GiB  "
              f"{drive.protocol}/{drive.media_type}  {drive.health}"
              + (f"  wear={drive.predicted_life_left_pct}%" if drive.predicted_life_left_pct is not None else ""))
```

---

### AccountService

Returned by `rf.account_service()`. Wraps `/redfish/v1/AccountService/`.

#### Properties

| Property | Type | Redfish field |
|----------|------|-------------|
| `min_password_length` | `int \| None` | `MinPasswordLength` |
| `lockout_threshold` | `int \| None` | `AccountLockoutThreshold` |
| `lockout_duration` | `int \| None` | `AccountLockoutDuration` (seconds) |

#### Account management

```python
svc = rf.account_service()

# List all accounts (returns list of raw dicts)
for acct in svc.accounts():
    print(acct["Id"], acct["UserName"], acct["RoleId"], acct["Enabled"])

# Create account — returns the created account dict (or {} if BMC returns 204)
new_acct = svc.create_account("operator1", "Secure!Pass1", role="Operator")
# role values are BMC-defined — common: "Administrator", "Operator", "ReadOnly"

# Change password by account URI
svc.set_password("/redfish/v1/AccountService/Accounts/3/", "NewSecure!Pass2")

# Enable / disable
svc.set_enabled("/redfish/v1/AccountService/Accounts/3/", False)

# Delete
svc.delete_account("/redfish/v1/AccountService/Accounts/3/")
```

#### Lockout policy

```python
svc.set_lockout_policy(
    threshold=5,       # failed attempts before lockout
    duration=300,      # seconds locked out
    reset_after=60,    # optional: seconds before counter resets
)
```

[↑ Back to Top](#table-of-contents)

---

## FleetManager

`FleetManager` fans out operations across multiple BMCs concurrently using `ThreadPoolExecutor`. Each worker gets its own `RedfishClient` instance — no shared state between threads.

```python
from pykesys_redfish.fleet import FleetManager
```

### FleetManager Constructor

```python
FleetManager(
    hosts: list[str],
    username: str,
    password: str,
    verify_ssl: bool = True,
    timeout: float = 30.0,
    max_workers: int = 16,
    base_url_scheme: str = "https",
)
```

| Parameter | Description |
|-----------|-------------|
| `hosts` | List of BMC hostnames or full URLs. Bare hostnames are prefixed with `base_url_scheme://`. |
| `username` | Credential used for all hosts |
| `password` | Credential used for all hosts |
| `max_workers` | Thread pool cap. Actual workers = `min(max_workers, len(hosts))`. |
| `base_url_scheme` | Scheme prepended to bare hostnames (`"https"` or `"http"`) |

```python
# Bare hostnames — HTTPS assumed
fm = FleetManager(
    hosts=["bmc-a1.mgmt", "bmc-a2.mgmt", "bmc-a3.mgmt"],
    username="admin",
    password="password",
)

# Full URLs (emulator, mixed schemes)
fm = FleetManager(
    hosts=[f"http://localhost:8888/bmc/{i}" for i in range(1, 11)],
    username="admin",
    password="redfish",
    verify_ssl=False,
)
```

### Built-in operations

#### collect_inventory()

Polls `system().summary()` on every host concurrently. Returns `list[dict]` — one dict per host. Failed hosts include an `"error"` key instead of system fields.

```python
results = fm.collect_inventory()
# [
#   {"host": "bmc-a1.mgmt", "model": "PowerEdge R750", "health": "OK", ...},
#   {"host": "bmc-a2.mgmt", "error": "Connection refused"},
#   ...
# ]
```

#### power_all(reset_type)

Sends a power reset to every host concurrently.

```python
fm.power_all("GracefulShutdown")
fm.power_all("On")
fm.power_all("ForceRestart")
```

Returns `list[dict]` — one result per host. A successful result contains `{"host": ..., "action": "reset", "reset_type": ..., "status": "sent"}`. A failed host returns `{"host": ..., "error": ...}`.

#### health_summary()

Calls `collect_inventory()` then aggregates health across the fleet:

```python
summary = fm.health_summary()
# {
#   "total": 10,
#   "errors": 1,
#   "health_ok": 7,
#   "health_warning": 2,
#   "health_critical": 0,
#   "power_states": {"On": 9, "Off": 0},
#   "error_hosts": ["bmc-a9.mgmt"],
# }
```

### Custom operations

`run(fn)` executes any callable `fn(client: RedfishClient, host: str) -> dict` concurrently across all hosts.

```python
def set_ntp(rf: RedfishClient, host: str) -> dict:
    rf.manager().set_ntp_servers(["ntp1.corp.com", "ntp2.corp.com"])
    return {"host": host, "status": "ntp configured"}

results = fm.run(set_ntp)
```

Failed hosts are caught inside `run()` — the exception message appears in the `"error"` key and no exception propagates to the caller.

```python
def boot_pxe_if_off(rf: RedfishClient, host: str) -> dict:
    system = rf.system()
    if system.power_state == "Off":
        system.set_boot_once("Pxe")
        system.power_on()
        return {"host": host, "action": "boot_pxe"}
    return {"host": host, "action": "skipped", "reason": f"already {system.power_state}"}

results = fm.run(boot_pxe_if_off)
for r in results:
    print(r["host"], r.get("action"), r.get("error", ""))
```

### Reporting and export

```python
# CSV — writes inventory fields to path
fm.export_csv(results, "inventory.csv")

# JSON — writes full results list to path
fm.export_json(results, "inventory.json")
```

The CSV writer uses `extrasaction="ignore"` — extra keys in result dicts are silently dropped. The fixed column order is:

```
host, id, hostname, manufacturer, model, serial_number, bios_version,
power_state, health, total_memory_gib, processor_count, processor_model, error
```

[↑ Back to Top](#table-of-contents)

---

## Exceptions

All exceptions inherit from `RedfishError` and carry two extra attributes:

| Attribute | Type | Description |
|-----------|------|-------------|
| `status_code` | `int \| None` | HTTP status code (None for timeout) |
| `url` | `str \| None` | Request URL |

```python
from pykesys_redfish import (
    RedfishError,         # base — catch-all
    RedfishAuthError,     # 401 or 403
    RedfishNotFoundError, # 404 (also raised by empty collection / out-of-range index)
    RedfishConflictError, # 409 (state conflict — already on/off, duplicate account, etc.)
    RedfishServerError,   # 500 or 503
    RedfishTimeoutError,  # network timeout (httpx.TimeoutException)
)
```

The `error.message` field from the Redfish `{"error": {"message": "..."}}` response body is used as the exception message when present; the raw response text is used otherwise.

See [Error Handling Patterns](#error-handling-patterns) for usage examples.

[↑ Back to Top](#table-of-contents)

---

## Environment Variables

| Variable | Default | Used by |
|----------|---------|---------|
| `RF_HOST` | — | `RedfishClient.from_env()`, `rf` CLI |
| `RF_USER` | — | `RedfishClient.from_env()`, `rf` CLI |
| `RF_PASS` | — | `RedfishClient.from_env()`, `rf` CLI |
| `RF_VERIFY_SSL` | `"true"` | `RedfishClient.from_env()` — set `"false"` to skip TLS |

[↑ Back to Top](#table-of-contents)

---

## Authentication Modes

### Session token (default)

`auth="session"` (default). Creates a Redfish session on connect, stores the `X-Auth-Token`, and deletes the session on close. Preferred — it is lower overhead (one auth round-trip) and allows the BMC to track active sessions.

```python
RedfishClient("https://bmc", "admin", "pass")                   # session (default)
RedfishClient("https://bmc", "admin", "pass", auth="session")   # explicit
```

### HTTP Basic

`auth="basic"`. Sends credentials in the `Authorization: Basic` header on every request. Useful when the BMC's session service is misconfigured or unavailable.

```python
RedfishClient("https://bmc", "admin", "pass", auth="basic")
```

[↑ Back to Top](#table-of-contents)

---

## Path-Prefix URLs

Some environments serve multiple BMC nodes under path prefixes — most notably the built-in emulator:

```
http://localhost:8888/bmc/1/redfish/v1/Systems/
http://localhost:8888/bmc/2/redfish/v1/Systems/
```

Pass the full path-prefixed base URL to `RedfishClient`. The session layer (`RedfishSession`) automatically extracts the path component (`/bmc/1`) using `urllib.parse.urlparse` and prepends it to every request URI:

```python
# Works transparently — no special configuration needed
with RedfishClient("http://localhost:8888/bmc/3", "admin", "redfish", verify_ssl=False) as rf:
    print(rf.system().hostname)   # "sim-node-03.bmc.local"
```

Standard BMCs with no path prefix work identically:

```python
with RedfishClient("https://192.168.1.100", "admin", "pass") as rf:
    print(rf.system().hostname)
```

[↑ Back to Top](#table-of-contents)

---

## Error Handling Patterns

### Basic exception hierarchy

```python
from pykesys_redfish import RedfishClient, RedfishError, RedfishAuthError, RedfishConflictError

with RedfishClient("https://bmc", "admin", "pass") as rf:
    try:
        rf.system().power_on()
    except RedfishAuthError as e:
        print(f"Credentials rejected: {e}  (HTTP {e.status_code})")
    except RedfishConflictError:
        print("System already powered on")
    except RedfishTimeoutError:
        print("BMC did not respond in time")
    except RedfishError as e:
        print(f"Unexpected Redfish error {e.status_code}: {e}")
```

### Ignoring expected conflicts

```python
from pykesys_redfish import RedfishConflictError

def safe_power_on(system):
    try:
        system.power_on()
    except RedfishConflictError:
        pass   # already on — that's fine
```

### Fleet error handling

`FleetManager.run()` catches all exceptions internally. Check for the `"error"` key in results:

```python
results = fm.collect_inventory()
ok = [r for r in results if "error" not in r]
failed = [r for r in results if "error" in r]

for r in failed:
    print(f"FAILED {r['host']}: {r['error']}")
```

### SSL errors in development

```python
# Against the emulator or self-signed BMC certs
with RedfishClient("http://localhost:8888/bmc/1", "admin", "redfish", verify_ssl=False) as rf:
    ...
```

[↑ Back to Top](#table-of-contents)

---

## Concurrency and Thread Safety

- `RedfishClient` and `RedfishSession` are **not thread-safe**. Do not share a single client across threads.
- `FleetManager` creates one independent `RedfishClient` per host per operation. Workers never share a client instance.
- The `ThreadPoolExecutor` is created fresh for each `run()` call and torn down (with all sessions closed) before `run()` returns.
- Resource objects (`ComputerSystem`, etc.) are bound to a specific client. They are safe to use from the thread that owns that client, but should not be passed between threads.

[↑ Back to Top](#table-of-contents)

---

## Recipes

### Check all DGX SuperPod nodes before a maintenance window

```python
from pykesys_redfish.fleet import FleetManager

# 10 DGX nodes, BMCs at bmc-dgx-{01..10}.mgmt
hosts = [f"bmc-dgx-{i:02d}.mgmt" for i in range(1, 11)]
fm = FleetManager(hosts=hosts, username="admin", password="secret")

summary = fm.health_summary()
print(f"Fleet: {summary['total']} nodes  |  "
      f"OK={summary['health_ok']}  "
      f"Warning={summary['health_warning']}  "
      f"Critical={summary['health_critical']}  "
      f"Errors={summary['errors']}")

if summary["health_critical"] > 0 or summary["errors"] > 0:
    print("⚠ Fleet not ready for maintenance")
else:
    print("✓ Fleet healthy — safe to proceed")
```

### Rolling firmware inventory audit

```python
def firmware_audit(rf, host):
    data = rf.get("/redfish/v1/UpdateService/FirmwareInventory/")
    components = [rf.get(m["@odata.id"]) for m in data.get("Members", [])]
    return {
        "host": host,
        "firmware": {c["Id"]: c["Version"] for c in components},
    }

results = fm.run(firmware_audit)
for r in results:
    if "error" not in r:
        print(f"{r['host']}: {r['firmware']}")
```

### Bulk PXE boot for OS imaging

```python
def pxe_boot(rf, host):
    system = rf.system()
    system.set_boot_once("Pxe")
    system.power_on() if system.power_state == "Off" else system.graceful_restart()
    return {"host": host, "status": "pxe boot triggered"}

fm.run(pxe_boot)
```

### Rotate BMC passwords across the fleet

```python
NEW_PASS = "NewSecure!Pass2026"

def rotate_admin_password(rf, host):
    svc = rf.account_service()
    for acct in svc.accounts():
        if acct["UserName"] == "admin":
            svc.set_password(acct["@odata.id"], NEW_PASS)
            return {"host": host, "status": "rotated"}
    return {"host": host, "status": "admin account not found"}

results = fm.run(rotate_admin_password)
```

### Monitor thermal headroom across a chassis group

```python
CRITICAL_THRESHOLD_C = 80.0

with RedfishClient("https://bmc.example.com", "admin", "pass") as rf:
    chassis = rf.chassis()
    for temp in chassis.temperatures():
        reading = temp.get("ReadingCelsius", 0)
        upper = temp.get("UpperThresholdCritical", CRITICAL_THRESHOLD_C)
        headroom = upper - reading
        status = temp.get("Status", {}).get("Health", "?")
        print(f"{temp['Name']:30s}  {reading:5.1f}°C  headroom={headroom:.1f}°C  [{status}]")
```

### Export full fleet inventory to JSON

```python
fm = FleetManager(hosts=[...], username="admin", password="pass")
results = fm.collect_inventory()
fm.export_json(results, "dgx-superpod-inventory.json")
fm.export_csv(results, "dgx-superpod-inventory.csv")
print(f"Exported {len(results)} hosts ({sum(1 for r in results if 'error' not in r)} succeeded)")
```

[↑ Back to Top](#table-of-contents)
