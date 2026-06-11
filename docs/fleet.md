# Fleet Automation Guide

The `pykesys_redfish.fleet` module extends the single-BMC SDK to operate across a fleet of BMCs concurrently. It is designed for datacenter automation tasks: inventory collection, bulk power operations, health monitoring, and reporting.

See [sdk.md](sdk.md) for single-BMC usage and [guide-admin.md](guide-admin.md) for operator context.

---

## FleetManager

```python
from pykesys_redfish.fleet import FleetManager

fm = FleetManager(
    hosts=["bmc-a1.mgmt.example.com", "bmc-a2.mgmt.example.com"],
    username="admin",
    password="password",
    verify_ssl=True,          # False for self-signed certs
    timeout=30.0,             # per-request timeout
    max_workers=16,           # concurrent BMC connections
    base_url_scheme="https",  # prepended when host has no scheme
)
```

Each worker gets its own `RedfishClient` instance with its own session. Failed hosts do not block others — errors are captured in the result dict under the `"error"` key.

### Constructor Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `hosts` | required | List of BMC hostnames or full `https://` URLs |
| `username` | required | Username for all hosts |
| `password` | required | Password for all hosts |
| `verify_ssl` | `True` | TLS verification |
| `timeout` | `30.0` | Per-request timeout in seconds |
| `max_workers` | `16` | Maximum concurrent BMC connections |
| `base_url_scheme` | `"https"` | Scheme prepended to bare hostnames |

---

## Methods

### `collect_inventory() → list[dict]`

Fetch a system summary from every host concurrently. Returns one dict per host.

```python
inventory = fm.collect_inventory()
for host_data in inventory:
    if host_data.get("error"):
        print(f"ERROR {host_data['host']}: {host_data['error']}")
    else:
        print(f"{host_data['host']}: {host_data['power_state']} / {host_data['health']}")
```

**Returned dict fields per host:**

| Field | Description |
|-------|-------------|
| `host` | The host as passed to FleetManager |
| `id` | Redfish system ID |
| `hostname` | OS-reported hostname |
| `manufacturer` | OEM |
| `model` | Server model |
| `serial_number` | Chassis serial |
| `bios_version` | BIOS version |
| `power_state` | `On`, `Off`, etc. |
| `health` | `OK`, `Warning`, `Critical` |
| `total_memory_gib` | RAM in GiB |
| `processor_count` | CPU socket count |
| `processor_model` | CPU model string |
| `error` | Error message if the host failed (key absent on success) |

---

### `power_all(reset_type: str) → list[dict]`

Send a power reset to every host concurrently.

```python
# Graceful shutdown across the fleet
results = fm.power_all("GracefulShutdown")

# Force restart everything
results = fm.power_all("ForceRestart")
```

Returns a list of `{"host": ..., "action": "reset", "reset_type": ..., "status": "sent"}` dicts, with `"error"` instead of `"status"` on failure.

---

### `health_summary() → dict`

Collect inventory and return an aggregate health rollup.

```python
summary = fm.health_summary()
print(summary)
# {
#     "total": 50,
#     "errors": 2,
#     "health_ok": 44,
#     "health_warning": 3,
#     "health_critical": 1,
#     "power_states": {"On": 48, "Off": 2},
#     "error_hosts": ["bmc-x1.mgmt", "bmc-x2.mgmt"]
# }
```

---

### `export_csv(results, path: str)`

Write inventory results to a CSV file.

```python
inventory = fm.collect_inventory()
fm.export_csv(inventory, "/tmp/datacenter-inventory.csv")
```

Column order: `host`, `id`, `hostname`, `manufacturer`, `model`, `serial_number`, `bios_version`, `power_state`, `health`, `total_memory_gib`, `processor_count`, `processor_model`, `error`

---

### `export_json(results, path: str)`

Write results to a JSON file.

```python
fm.export_json(inventory, "/tmp/datacenter-inventory.json")
```

---

### `run(fn: Callable[[RedfishClient, str], dict]) → list[dict]`

Execute a custom function across the fleet. Use this for operations not covered by built-in methods.

```python
def set_pxe_boot(rf, host):
    rf.system().set_boot_once("Pxe")
    return {"host": host, "status": "boot-override-set"}

results = fm.run(set_pxe_boot)
```

The function receives a connected `RedfishClient` and the host string. It must return a dict. Any exception is caught and returned as `{"host": ..., "error": "<message>"}`.

---

## Standalone Functions

These are also importable directly if you want to use them outside of `FleetManager`:

```python
from pykesys_redfish.fleet import (
    collect_system_inventory,   # (rf, host) → dict
    power_reset,                # (rf, host, reset_type) → dict
    summarize_health,           # (results) → dict
    export_csv,                 # (results, path) → None
    export_json,                # (results, path) → None
)
```

---

## Full Example: Nightly Inventory Report

```python
from pykesys_redfish.fleet import FleetManager
from datetime import date

hosts = open("/etc/bmc-hosts.txt").read().splitlines()

fm = FleetManager(
    hosts=hosts,
    username="svc-redfish",
    password="s3cr3t",
    max_workers=32,
)

inventory = fm.collect_inventory()
summary = fm.health_summary()

date_str = date.today().isoformat()
fm.export_csv(inventory, f"/reports/inventory-{date_str}.csv")
fm.export_json(inventory, f"/reports/inventory-{date_str}.json")

print(f"Fleet: {summary['total']} hosts")
print(f"  OK:       {summary['health_ok']}")
print(f"  Warning:  {summary['health_warning']}")
print(f"  Critical: {summary['health_critical']}")
print(f"  Errors:   {summary['errors']}")
if summary["error_hosts"]:
    print(f"  Failed:   {', '.join(summary['error_hosts'])}")
```

---

## Example: Mass PXE Boot + Reset

```python
from pykesys_redfish.fleet import FleetManager
from pykesys_redfish import RedfishClient

staging_hosts = [
    "bmc-staging-01.mgmt",
    "bmc-staging-02.mgmt",
    "bmc-staging-03.mgmt",
]

fm = FleetManager(staging_hosts, username="admin", password="password")

def pxe_and_reset(rf: RedfishClient, host: str) -> dict:
    system = rf.system()
    system.set_boot_once("Pxe")
    system.graceful_restart()
    return {"host": host, "status": "pxe-restart-sent"}

results = fm.run(pxe_and_reset)
for r in results:
    status = r.get("error", r.get("status", "unknown"))
    print(f"{r['host']}: {status}")
```

---

## Example: Health Alert Integration

```python
from pykesys_redfish.fleet import FleetManager
import requests  # for posting to Slack / PagerDuty webhook

fm = FleetManager(all_hosts, username="admin", password="password")
summary = fm.health_summary()
inventory = fm.collect_inventory()

critical = [r for r in inventory if r.get("health") == "Critical"]
for host_data in critical:
    requests.post(
        SLACK_WEBHOOK,
        json={"text": f":red_circle: CRITICAL: {host_data['host']} ({host_data['hostname']}) — {host_data['model']}"},
    )
```

---

## Performance Notes

- Each worker maintains one HTTPS connection per BMC for the lifetime of the operation
- BMCs are resource-constrained; keep `max_workers` ≤ the number of unique hosts
- For very large fleets (500+), batch hosts into groups of 200–300 and run sequentially between batches to avoid overwhelming the network
- Add retry logic at the `fm.run()` call level for transient failures — the fleet module surfaces errors rather than retrying internally
