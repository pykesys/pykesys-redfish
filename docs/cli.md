# CLI Reference — `rf`

The `rf` command provides interactive and scriptable access to Redfish BMCs from the terminal. Output is formatted with Rich tables and color-coded health/power states.

See [sdk.md](sdk.md) for programmatic access and [guide-users.md](guide-users.md) for curl-based examples.

---

## Installation

```bash
uv sync        # after cloning the repo
uv run rf --help
```

Or after installing the package:

```bash
pip install pykesys-redfish
rf --help
```

---

## Global Options

Every command accepts these options. Set them as environment variables to avoid typing them every time.

| Option | Env Var | Description |
|--------|---------|-------------|
| `--host` / `-H` | `RF_HOST` | BMC hostname or IP with scheme, e.g. `https://192.168.1.100` |
| `--user` / `-u` | `RF_USER` | Username |
| `--pass` / `-p` | `RF_PASS` | Password |
| `--no-verify` | `RF_VERIFY_SSL=false` | Skip TLS certificate verification |

**Example with env vars:**

```bash
export RF_HOST=https://192.168.1.100
export RF_USER=admin
export RF_PASS=password

rf info
rf power status
```

---

## Commands

### `rf info`

Show a Rich table summarising the system managed by this BMC.

```bash
rf info --host https://192.168.1.100 -u admin -p password
```

**Output:**

```
╭─ System ─────────────────────────────────────╮
│ ID           │ 1                              │
│ Hostname     │ server01.example.com           │
│ Manufacturer │ Dell                           │
│ Model        │ PowerEdge R750                 │
│ Serial       │ ABC123                         │
│ BIOS         │ 2.1.0                          │
│ Power        │ On                             │
│ Health       │ OK                             │
│ RAM (GiB)    │ 256                            │
│ CPUs         │ 2                              │
│ CPU Model    │ Intel Xeon Gold 6338           │
╰───────────────────────────────────────────────╯
```

---

### `rf power`

Power management subcommands.

#### `rf power status`

Show current power state.

```bash
rf power status -H https://192.168.1.100 -u admin -p password
# Power state: On
```

#### `rf power on`

Power on the system.

```bash
rf power on -H https://192.168.1.100 -u admin -p password
```

#### `rf power off`

Graceful shutdown (ACPI signal to OS). Add `--force` for immediate power cut.

```bash
rf power off -H https://192.168.1.100 -u admin -p password
rf power off -H https://192.168.1.100 -u admin -p password --force
```

#### `rf power reset`

Reset the system. Defaults to `GracefulRestart`. Use `--type` to override.

```bash
rf power reset -H https://192.168.1.100 -u admin -p password
rf power reset -H https://192.168.1.100 -u admin -p password --type ForceRestart
rf power reset -H https://192.168.1.100 -u admin -p password --type Nmi
```

Valid `--type` values: `On`, `ForceOff`, `GracefulShutdown`, `GracefulRestart`, `ForceRestart`, `Nmi`, `PushPowerButton`

#### `rf power nmi`

Inject a Non-Maskable Interrupt (triggers kernel crash dump).

```bash
rf power nmi -H https://192.168.1.100 -u admin -p password
```

---

### `rf boot`

Boot source override subcommands.

#### `rf boot status`

Show current boot override settings and allowed values.

```bash
rf boot status -H https://192.168.1.100 -u admin -p password
# Target:  None
# Enabled: Disabled
# Allowed: None, Pxe, Hdd, Cd, Usb, BiosSetup
```

#### `rf boot once <target>`

Set a one-time boot override for the next boot.

```bash
rf boot once Pxe -H https://192.168.1.100 -u admin -p password
rf boot once BiosSetup -H https://192.168.1.100 -u admin -p password
rf boot once UefiShell -H https://192.168.1.100 -u admin -p password --mode UEFI
```

Common targets: `Pxe`, `Usb`, `Hdd`, `Cd`, `BiosSetup`, `UefiShell`, `UefiHttp`

| Option | Description |
|--------|-------------|
| `--mode UEFI` | Force UEFI boot mode (default: Legacy) |

#### `rf boot clear`

Clear the boot override — revert to the normal boot order.

```bash
rf boot clear -H https://192.168.1.100 -u admin -p password
```

---

### `rf logs`

System event log subcommands.

#### `rf logs list`

List SEL entries in a Rich table, newest last.

```bash
rf logs list -H https://192.168.1.100 -u admin -p password
rf logs list -H https://192.168.1.100 -u admin -p password --limit 20
rf logs list -H https://192.168.1.100 -u admin -p password --service Log1
```

| Option | Default | Description |
|--------|---------|-------------|
| `--limit` / `-n` | 50 | Maximum entries to display |
| `--service` / `-s` | `Sel` | Log service name |

#### `rf logs clear`

Clear the event log. Prompts for confirmation unless `--yes` is passed.

```bash
rf logs clear -H https://192.168.1.100 -u admin -p password
rf logs clear -H https://192.168.1.100 -u admin -p password --yes
```

---

### `rf firmware`

Firmware inventory and update subcommands.

#### `rf firmware list`

List all installed firmware components (BIOS, BMC, NICs, HBAs, PSUs, CPLDs).

```bash
rf firmware list -H https://192.168.1.100 -u admin -p password
```

#### `rf firmware update <image-uri>`

Trigger a SimpleUpdate from a remote HTTPS image URI.

```bash
rf firmware update https://firmware.example.com/bios-2.2.0.bin \
  -H https://192.168.1.100 -u admin -p password

rf firmware update https://firmware.example.com/bmc-6.11.bin \
  --target /redfish/v1/UpdateService/FirmwareInventory/BMC \
  -H https://192.168.1.100 -u admin -p password
```

| Option | Description |
|--------|-------------|
| `--target` / `-t` | FirmwareInventory URI to restrict the update to one component |

---

### `rf accounts`

User account management subcommands.

#### `rf accounts list`

List all user accounts.

```bash
rf accounts list -H https://192.168.1.100 -u admin -p password
```

#### `rf accounts create <username>`

Create a new account. Prompts for the new password interactively.

```bash
rf accounts create operator1 \
  -H https://192.168.1.100 -u admin -p password

rf accounts create svcuser \
  --role ReadOnly \
  -H https://192.168.1.100 -u admin -p password
```

| Option | Default | Description |
|--------|---------|-------------|
| `--role` / `-r` | `Operator` | `Administrator`, `Operator`, `ReadOnly` |

#### `rf accounts delete <account-uri>`

Delete an account by its Redfish URI. Prompts for confirmation unless `--yes`.

```bash
rf accounts delete /redfish/v1/AccountService/Accounts/3 \
  -H https://192.168.1.100 -u admin -p password --yes
```

---

## Scripting Tips

### Use env vars for clean one-liners

```bash
export RF_HOST=https://192.168.1.100 RF_USER=admin RF_PASS=password

rf power status
rf info
rf logs list --limit 10
```

### Chain with jq via raw HTTP (advanced)

For resources not yet covered by a subcommand, use the SDK or curl. The CLI always exits 0 on success and non-zero on error, so standard shell scripting patterns work:

```bash
rf power on && echo "Power-on sent" || echo "Power-on failed"
```

### Scripted PXE boot + power cycle

```bash
rf boot once Pxe
rf power reset --type GracefulRestart
```
