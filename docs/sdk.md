# SDK Reference — pykesys_redfish

The `pykesys_redfish` library provides a typed Python interface to the Redfish BMC management API. It handles session management, HTTP transport, error mapping, and resource traversal so you can focus on automation logic.

See [redfish.md](redfish.md) for protocol background and [guide-users.md](guide-users.md) for curl-based examples.

---

## Installation

```bash
uv add pykesys-redfish
# or
pip install pykesys-redfish
```

---

## Quick Start

```python
from pykesys_redfish import RedfishClient

with RedfishClient("https://192.168.1.100", "admin", "password") as rf:
    system = rf.system()
    print(system.power_state)   # "On"
    print(system.health)        # "OK"
    print(system.bios_version)  # "2.1.0"
    system.graceful_restart()
```

`RedfishClient` is a context manager. On `__enter__` it creates a Redfish session (POST to `/redfish/v1/SessionService/Sessions/`); on `__exit__` it deletes the session.

---

## RedfishClient

```python
RedfishClient(
    base_url: str,
    username: str,
    password: str,
    verify_ssl: bool = True,     # set False for self-signed certs (dev only)
    timeout: float = 30.0,
    auth: str = "session",       # "session" | "basic"
)
```

### Class Methods

| Method | Description |
|--------|-------------|
| `RedfishClient.from_env()` | Construct from `RF_HOST`, `RF_USER`, `RF_PASS` env vars |

### Resource Accessors

| Method | Returns |
|--------|---------|
| `rf.system(index=0)` | `ComputerSystem` for the nth system in `/redfish/v1/Systems/` |
| `rf.chassis(index=0)` | `Chassis` for the nth chassis |
| `rf.manager(index=0)` | `Manager` (BMC) for the nth manager |
| `rf.account_service()` | `AccountService` |

### Raw HTTP (advanced)

| Method | Description |
|--------|-------------|
| `rf.get(uri)` | GET a Redfish URI, returns dict |
| `rf.post(uri, body)` | POST with JSON body, returns dict or None |
| `rf.patch(uri, body)` | PATCH with JSON body, returns dict or None |
| `rf.delete(uri)` | DELETE a URI |

---

## Resource Classes

All resource objects cache the fetched JSON on first property access. Call `.refresh()` to invalidate the cache and re-fetch on the next access.

### ComputerSystem

Returned by `rf.system()`.

**Properties**

| Property | Type | Description |
|----------|------|-------------|
| `id` | `str` | Resource ID |
| `hostname` | `str` | OS-reported hostname |
| `serial_number` | `str` | Chassis serial |
| `model` | `str` | Server model string |
| `manufacturer` | `str` | OEM |
| `sku` | `str` | Vendor SKU |
| `bios_version` | `str` | Running BIOS version |
| `power_state` | `str` | `On`, `Off`, `PoweringOn`, `PoweringOff` |
| `health` | `str` | `OK`, `Warning`, `Critical` |
| `state` | `str` | `Enabled`, `Absent`, `Disabled` |
| `total_memory_gib` | `float` | Installed RAM in GiB |
| `processor_count` | `int` | Number of CPU sockets |
| `processor_model` | `str` | CPU model string |
| `boot_source_override_target` | `str` | Current override target |
| `boot_source_override_enabled` | `str` | `Disabled`, `Once`, `Continuous` |
| `boot_allowable_values` | `list[str]` | Supported boot targets |
| `indicator_led` | `str` | `Off`, `Lit`, `Blinking` |

**Power Methods**

| Method | Effect |
|--------|--------|
| `power_on()` | `ResetType=On` |
| `power_off()` | `ResetType=ForceOff` |
| `graceful_shutdown()` | `ResetType=GracefulShutdown` |
| `graceful_restart()` | `ResetType=GracefulRestart` |
| `force_restart()` | `ResetType=ForceRestart` |
| `nmi()` | `ResetType=Nmi` |
| `reset(reset_type)` | Send any arbitrary ResetType |

**Boot Methods**

| Method | Effect |
|--------|--------|
| `set_boot_once(target, mode=None)` | One-time boot override |
| `clear_boot_override()` | Reset to normal boot |

**Other Methods**

| Method | Effect |
|--------|--------|
| `identify(state="Blinking")` | Set UID LED |
| `identify_off()` | Turn UID LED off |
| `processors()` | `list[dict]` — raw processor inventory |
| `memory()` | `list[dict]` — raw DIMM inventory |
| `storage()` | `list[Storage]` — storage controller objects |
| `log_entries(log_service="Sel")` | `list[dict]` — SEL entries |
| `clear_log(log_service="Sel")` | Clear the event log |
| `summary()` | `dict` — flat summary (used by CLI and fleet) |

---

### Chassis

Returned by `rf.chassis()`.

**Properties:** `id`, `chassis_type`, `manufacturer`, `model`, `serial_number`, `health`, `indicator_led`

**Methods**

| Method | Returns |
|--------|---------|
| `temperatures()` | `list[dict]` — temperature probes |
| `fans()` | `list[dict]` — fan readings |
| `power_supplies()` | `list[dict]` — PSU data |
| `power_consumed_watts()` | `float` — current draw |
| `identify(state)` / `identify_off()` | Set chassis UID LED |

---

### Manager

Returned by `rf.manager()`.

**Properties:** `id`, `firmware_version`, `manager_type`, `model`, `health`

**Methods**

| Method | Effect |
|--------|--------|
| `network_protocols()` | `dict` — protocol enable/disable state |
| `set_protocol_enabled(name, enabled)` | Enable or disable a protocol |
| `set_ntp_servers(servers)` | Configure NTP |
| `ethernet_interfaces()` | `list[dict]` — BMC NIC configs |
| `reset(reset_type="GracefulRestart")` | Reboot the BMC |
| `reset_to_defaults(reset_type="ResetAll")` | Factory reset the BMC |
| `log_entries(log_service="Log1")` | `list[dict]` — BMC log entries |

---

### Storage / Drive

`Storage` objects returned from `system.storage()`.
`Drive` objects returned from `storage.drives()`.

**Storage Properties:** `id`, `name`, `health`
**Storage Methods:** `drives()` → `list[Drive]`, `volumes()` → `list[dict]`

**Drive Properties:** `id`, `name`, `health`, `capacity_bytes`, `capacity_gib`, `protocol`, `media_type`, `model`, `serial_number`, `predicted_life_left_pct`

---

### AccountService

Returned by `rf.account_service()`.

**Properties:** `min_password_length`, `lockout_threshold`, `lockout_duration`

**Methods**

| Method | Effect |
|--------|--------|
| `accounts()` | `list[dict]` — all user accounts |
| `create_account(username, password, role)` | Create a new account |
| `delete_account(account_uri)` | Delete by Redfish URI |
| `set_password(account_uri, new_password)` | Change password |
| `set_enabled(account_uri, enabled)` | Enable/disable account |
| `set_lockout_policy(threshold, duration, reset_after)` | Configure lockout |

---

## Exceptions

All exceptions inherit from `RedfishError`.

```python
from pykesys_redfish import (
    RedfishError,
    RedfishAuthError,       # 401 / 403
    RedfishNotFoundError,   # 404
    RedfishConflictError,   # 409
    RedfishServerError,     # 500 / 503
    RedfishTimeoutError,
)
```

Every exception carries `.status_code` (int | None) and `.url` (str | None).

```python
try:
    system.power_on()
except RedfishAuthError as e:
    print(f"Auth failed: {e} (HTTP {e.status_code})")
except RedfishConflictError:
    print("System may already be in the requested state")
except RedfishError as e:
    print(f"Redfish error: {e}")
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RF_HOST` | — | BMC base URL (used by `from_env()` and CLI) |
| `RF_USER` | — | Username |
| `RF_PASS` | — | Password |
| `RF_VERIFY_SSL` | `true` | Set `false` to skip TLS verification |

---

## Full Usage Example

```python
import csv
from pykesys_redfish import RedfishClient, RedfishError

hosts = ["bmc-a1.mgmt.example.com", "bmc-a2.mgmt.example.com"]

with open("inventory.csv", "w", newline="") as fh:
    writer = csv.DictWriter(fh, fieldnames=["host", "model", "bios", "health", "power"])
    writer.writeheader()
    for host in hosts:
        try:
            with RedfishClient(f"https://{host}", "admin", "password") as rf:
                s = rf.system()
                writer.writerow({
                    "host": host,
                    "model": s.model,
                    "bios": s.bios_version,
                    "health": s.health,
                    "power": s.power_state,
                })
        except RedfishError as e:
            writer.writerow({"host": host, "model": str(e)})
```
