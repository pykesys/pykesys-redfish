# NVIDIA DGX BMC — Images, Firmware, and Overlays

Comprehensive technical reference for the NVIDIA DGX BMC firmware architecture: how images are built and signed, how the filesystem is layered, how updates propagate from Redfish through to NOR flash, and how the ERoT/MCTP security chain governs every firmware change.

**Applies to:** DGX A100, H100, H200 (B200 notes where behavior differs or is uncertain).
**Confidence notation:** Claims that differ between NVIDIA-specific behavior and upstream OpenBMC behavior, or that are inferred rather than documented, are flagged inline.

## Table of Contents

- [BMC Hardware](#bmc-hardware)
  - [SoC](#soc)
  - [NOR flash layout](#nor-flash-layout)
  - [Memory map](#memory-map)
- [Filesystem Architecture](#filesystem-architecture)
  - [SquashFS ROFS — read-only root](#squashfs-rofs--read-only-root)
  - [UBIFS RWFS — read-write overlay store](#ubifs-rwfs--read-write-overlay-store)
  - [OverlayFS composition](#overlayfs-composition)
  - [Persistent vs. ephemeral paths](#persistent-vs-ephemeral-paths)
- [Boot Sequence](#boot-sequence)
- [Firmware Image Format](#firmware-image-format)
  - [Tarball contents](#tarball-contents)
  - [MANIFEST file](#manifest-file)
  - [Image types](#image-types)
  - [Image signing](#image-signing)
- [A/B Dual-Bank Update Mechanism](#ab-dual-bank-update-mechanism)
  - [U-Boot environment variables](#u-boot-environment-variables)
  - [obmc-flash-bmc](#obmc-flash-bmc)
  - [phosphor-software-manager state machine](#phosphor-software-manager-state-machine)
- [Redfish Firmware Update Flow](#redfish-firmware-update-flow)
  - [SimpleUpdate](#simpleupdate)
  - [Multipart direct upload](#multipart-direct-upload)
  - [Task lifecycle and states](#task-lifecycle-and-states)
  - [ApplyTime — deferred activation](#applytime--deferred-activation)
- [ERoT — Endpoint Root of Trust](#erot--endpoint-root-of-trust)
  - [Architecture and scope](#architecture-and-scope)
  - [MCTP topology on DGX](#mctp-topology-on-dgx)
  - [SPDM attestation](#spdm-attestation)
- [PLDM Firmware Update — Component Level](#pldm-firmware-update--component-level)
  - [PLDM Type 5 protocol flow](#pldm-type-5-protocol-flow)
  - [pldmd and pldmtool](#pldmd-and-pldmtool)
  - [Component firmware inventory](#component-firmware-inventory)
- [Component Firmware Details](#component-firmware-details)
  - [GPU VBIOS](#gpu-vbios)
  - [ConnectX NIC firmware](#connectx-nic-firmware)
  - [NVSwitch / NVLink Switch firmware](#nvswitch--nvlink-switch-firmware)
  - [HMC — Host Management Controller](#hmc--host-management-controller)
  - [ERoT firmware itself](#erot-firmware-itself)
- [Filesystem Overlays and Hot-Patching](#filesystem-overlays-and-hot-patching)
  - [What the overlay enables](#what-the-overlay-enables)
  - [Why hot-patching firmware is not supported](#why-hot-patching-firmware-is-not-supported)
  - [Effective overlay techniques](#effective-overlay-techniques)
- [DGX SuperPod Fleet Firmware Coordination](#dgx-superpod-fleet-firmware-coordination)
  - [Component inventory per node](#component-inventory-per-node)
  - [Coordinated update sequence](#coordinated-update-sequence)
  - [NVIDIA fleet tools](#nvidia-fleet-tools)
- [Factory Reset and Overlay Management](#factory-reset-and-overlay-management)
  - [ResetToDefaults types](#resettodefaults-types)
  - [What is preserved vs wiped](#what-is-preserved-vs-wiped)
  - [Manual RWFS clear from BMC shell](#manual-rwfs-clear-from-bmc-shell)
- [Security and Secure Boot Chain](#security-and-secure-boot-chain)
  - [AST2600 hardware root of trust](#ast2600-hardware-root-of-trust)
  - [Full verification chain](#full-verification-chain)
  - [Unsigned image rejection](#unsigned-image-rejection)
  - [RWFS is not verified](#rwfs-is-not-verified)
- [Working with BMC Images via Redfish](#working-with-bmc-images-via-redfish)
  - [Checking firmware inventory](#checking-firmware-inventory)
  - [Triggering updates via pykesys_redfish](#triggering-updates-via-pykesys_redfish)
  - [Monitoring update tasks](#monitoring-update-tasks)
  - [Polling until BMC recovers](#polling-until-bmc-recovers)
- [Troubleshooting](#troubleshooting)

---

## BMC Hardware

### SoC

The DGX BMC runs on an **ASPEED AST2600** — a dual-core ARM Cortex-A7 (up to 1.2 GHz), purpose-built for server management. It is used across the DGX A100, H100, and H200 product generations.

Key AST2600 capabilities relevant to firmware management:

| Feature | Detail |
|---------|--------|
| CPU | 2× ARM Cortex-A7 @ ~800 MHz |
| RAM | External LPDDR4, typically 512 MB–1 GB |
| SPI NOR controller | Quad-SPI, up to 128 MiB addressable per CS |
| Hardware crypto | SHA-1/256/512, RSA-2048/4096, ECDSA — used for secure boot and image signing |
| MCTP | Via I2C/SMBus controllers (for ERoT communication) |
| PCIe | 2.0 x1 (used for PCIe-VDM MCTP to GPU ERoTs) |

The BMC runs **OpenBMC** — NVIDIA ships a downstream fork with proprietary extensions for GPU telemetry, NVLink monitoring, and ERoT integration.

> **B200 note:** The Blackwell-generation DGX may use an updated BMC SoC (ASPEED AST2700 or a custom NVIDIA BMC ASIC). NVIDIA has not publicly confirmed this as of mid-2025; assume AST2600 behavior unless the B200 system guide states otherwise.

### NOR flash layout

The BMC NOR flash is typically **128–256 MiB**. It is divided into named MTD (Memory Technology Device) partitions, defined in the platform device tree and managed by the `aspeed-smc` kernel driver. MTD devices appear in Linux as `/dev/mtd0`, `/dev/mtd1`, etc.

A representative layout (illustrative offsets — exact values are platform-specific):

```
Offset        Partition        Size      Description
------------  ---------------  --------  ---------------------------------------------
0x00000000    u-boot           512 KiB   Primary bootloader (ASPEED-signed)
0x00080000    u-boot-env       256 KiB   U-Boot environment block (key=value store)
0x000C0000    u-boot-env-r     256 KiB   Redundant env copy
0x00100000    kernel-a         8 MiB     Bank A: FIT image (kernel + DTB)
0x00900000    rofs-a           40 MiB    Bank A: SquashFS read-only rootfs
0x03100000    kernel-b         8 MiB     Bank B: FIT image (kernel + DTB)
0x03900000    rofs-b           40 MiB    Bank B: SquashFS read-only rootfs
0x06100000    rwfs             16 MiB    Read-write overlay store (UBIFS/JFFS2)
0x07100000    id               64 KiB    Board identity / FRU VPD
```

Both banks hold a complete, bootable kernel + rootfs. At any point, one bank is *active* (running), the other is *inactive* (safe to overwrite during updates).

### Memory map

The AST2600 maps the SPI NOR into its address space at `0x20000000`. The running BMC Linux kernel sees the partitions as MTD block devices and can read/write them directly with `flashcp`, `nanddump`, or `mtd_debug` if operating with BMC shell access (typically via SOL or SSH with admin privileges).

[↑ Back to Top](#table-of-contents)

---

## Filesystem Architecture

### SquashFS ROFS — read-only root

`image-rofs` is a **SquashFS** image stored in the active bank's `rofs-*` MTD partition. SquashFS is a compressed, read-only filesystem — the BMC mounts it directly from NOR flash using the kernel's `mtdblock` or `squashfs` MTD driver.

It contains the entire BMC operating system:
- systemd units and service definitions
- `bmcweb` — the Redfish and web server daemon
- `phosphor-*` management daemons
- `pldmd`, `mctpd`, `spdmd` — PLDM/MCTP/SPDM protocol daemons
- Python 3 runtime and OpenBMC D-Bus infrastructure
- `dropbear` SSH server
- NVIDIA-specific: GPU telemetry agents, ERoT integration daemons, NVLink monitor

Because SquashFS is read-only, **nothing running on the BMC can modify the ROFS in-place**. Any change to a file that exists in ROFS must go through the RWFS overlay or require a full reflash.

### UBIFS RWFS — read-write overlay store

`image-rwfs` is a **UBIFS** (or **JFFS2** on older firmware releases) filesystem stored in the `rwfs` MTD partition. It is mounted read-write and serves as the upper layer of the OverlayFS.

UBIFS is preferred on DGX H100/H200 firmware because:
- Better wear leveling via UBI layer (`ubi0` → `ubi0_0` volume)
- Atomic writes — no corruption on sudden power loss
- Faster mount and recovery than JFFS2 on larger partitions
- Better suited to the 16 MiB partition size

The RWFS holds only the *delta* from the ROFS: new files, modified files, and deleted-file markers. A pristine BMC (post-factory-reset or first boot) has an essentially empty RWFS.

### OverlayFS composition

The kernel composes the root filesystem using **OverlayFS**:

```
Lower (read-only):   SquashFS mount of ROFS (active bank's rofs-* MTD)
Upper (read-write):  UBIFS/JFFS2 mount of RWFS MTD partition
Work:                tmpfs scratch (required by overlayfs)
                           │
                           ▼
         Unified root /   (overlayfs presents both layers as one)
```

When a process reads a file:
- If the file exists in the RWFS upper layer → serve from RWFS (modified version)
- If not → serve from ROFS lower layer (original version)

When a process writes to a file:
- A copy of the file is promoted to the RWFS upper layer (copy-on-write)
- Future reads serve the modified RWFS copy

This means that **modifying a file in `/etc/` writes to RWFS**, and the change persists across reboots. Deleting a ROFS file creates a "whiteout" entry in RWFS.

### Persistent vs. ephemeral paths

| Path | Layer | Persists across reboot? | Notes |
|------|-------|------------------------|-------|
| `/etc/` | RWFS upper | **Yes** | Network config, NTP, LDAP, SSH host keys |
| `/var/` | RWFS upper | **Yes** | Logs, phosphor-settings-manager state |
| `/home/` | RWFS upper | **Yes** | Local user home directories |
| `/conf/` | RWFS upper | **Yes** | OpenBMC phosphor-settings persistent store |
| `/tmp/` | tmpfs | **No** | Cleared at every reboot |
| `/run/` | tmpfs | **No** | Runtime sockets, PIDs, volatile state |
| `/sys/`, `/proc/` | kernel virtual | **No** | Live kernel/hardware views |
| ROFS-only paths | ROFS lower | **Yes** (immutable) | Daemons, libraries — can't be changed without reflash |

[↑ Back to Top](#table-of-contents)

---

## Boot Sequence

The full boot chain from power-on to Redfish available:

```
1. ASPEED AST2600 Boot ROM (on-chip, immutable)
       │  Reads U-Boot from NOR offset 0x00000000
       │  Verifies RSA/ECDSA signature against OTP public key hash
       │  HALT if verification fails (secure boot enabled)
       ▼
2. U-Boot
       │  Reads U-Boot env block (boot_side, upgrade_avail)
       │  Selects active bank (A or B) based on boot_side
       │  Loads FIT image (kernel + DTB) from active kernel-* partition
       │  Verifies FIT image signature
       │  Passes rootfs_mtd=mtdX on kernel cmdline
       ▼
3. Linux kernel (ARM, OpenBMC config)
       │  Mounts SquashFS ROFS from rootfs_mtd as lower layer
       │  Mounts UBIFS RWFS from rwfs MTD as upper layer
       │  Composes OverlayFS root
       │  Starts systemd (PID 1)
       ▼
4. systemd
       │  Starts phosphor daemons, bmcweb, mctpd, pldmd, spdmd
       │  MCTP endpoint discovery (assigns EIDs to ERoT chips)
       │  ERoT attestation queries (SPDM measurements)
       │  Redfish API becomes available (~60–90 sec after power-on)
       ▼
5. Redfish available at https://<bmc-ip>/redfish/v1/
```

Total boot time: approximately **90–120 seconds** from power-on to Redfish responding. After a BMC reset (not host reset), the cycle restarts from step 2 and takes the same duration.

[↑ Back to Top](#table-of-contents)

---

## Firmware Image Format

### Tarball contents

A DGX BMC firmware release is distributed as a `.tar` or `.tar.gz` archive. The standard OpenBMC contents:

```
dgx-bmc-<version>.tar
├── MANIFEST               Required — metadata key=value file
├── image-bmc              Full monolithic NOR image (for factory flash via flashcp)
├── image-kernel           FIT image: Linux kernel + device tree blob
├── image-rofs             SquashFS read-only rootfs
├── image-rwfs             UBIFS/JFFS2 read-write store (omitted in OTA updates)
├── publickey              RSA/ECDSA public key (if image signing is used)
├── image-bmc.sig          Detached signature over image-bmc
├── image-kernel.sig       Detached signature over image-kernel
└── image-rofs.sig         Detached signature over image-rofs
```

For routine OTA updates, `image-rwfs` is **omitted** — only `image-kernel` and `image-rofs` are written to the inactive bank. This preserves the RWFS contents (network config, user accounts, certificates).

For factory provisioning or destructive reflash (e.g., after RWFS corruption), `image-bmc` is flashed directly and `image-rwfs` provides a clean RWFS.

### MANIFEST file

```
PURPOSE=xyz.openbmc_project.Software.Version.VersionPurpose.BMC
VERSION=24.01.03
EXTENDED_VERSION=dgx-h100-bmc-24.01.03-2024-01-15
MACHINE=dgx-h100
COMPATIBLE=dgx-h100,dgx-h200
```

| Key | Meaning |
|-----|---------|
| `PURPOSE` | Tells `phosphor-bmc-code-mgmt` this is a BMC image. Host BIOS images use `VersionPurpose.Host`. |
| `VERSION` | Semantic version — compared against current version to detect downgrades |
| `EXTENDED_VERSION` | Human-readable build string; appears in Redfish `FirmwareVersion` field |
| `MACHINE` | Target platform; used to reject images built for a different DGX model |
| `COMPATIBLE` | Additional compatible platform strings |

`phosphor-bmc-code-mgmt` parses the MANIFEST immediately after receiving the tarball. A missing or malformed MANIFEST causes immediate rejection before any flash operation.

### Image types

| Image | Format | Flashed to | Used for |
|-------|--------|-----------|---------|
| `image-bmc` | Raw binary (concatenated partition images) | Full NOR via `flashcp /dev/mtd0` | Factory programming |
| `image-kernel` | U-Boot FIT image (zImage + DTB) | Active bank's `kernel-*` MTD | OTA bank-swap update |
| `image-rofs` | SquashFS | Active bank's `rofs-*` MTD | OTA bank-swap update |
| `image-rwfs` | UBIFS/JFFS2 | `rwfs` MTD | Factory reset / destructive update |

### Image signing

NVIDIA uses **RSA-4096** (or ECDSA-384 depending on platform) signatures over each image component:

1. NVIDIA's build system signs `image-kernel`, `image-rofs`, and `image-bmc` with NVIDIA's BMC signing private key.
2. The corresponding public key is embedded in `publickey` in the tarball and also stored in `/etc/activationdata/` on the ROFS (the trusted, read-only location that establishes the trust anchor).
3. `phosphor-bmc-code-mgmt` verifies each image before flashing:
   ```bash
   openssl dgst -sha256 -verify /etc/activationdata/publickey \
     -signature image-kernel.sig image-kernel
   ```
4. If any signature fails → activation is rejected, BMC remains on current firmware.

On production DGX systems with secure boot enabled, **only NVIDIA-signed images are accepted**. Custom or community-built OpenBMC images will be rejected at two points: the Redfish layer (signing check) and U-Boot (boot-time signature verification of the kernel FIT image).

[↑ Back to Top](#table-of-contents)

---

## A/B Dual-Bank Update Mechanism

### U-Boot environment variables

U-Boot reads its environment block from the `u-boot-env` MTD partition. The key variables controlling which bank boots:

| Variable | Values | Meaning |
|----------|--------|---------|
| `boot_side` | `0` or `1` | Active bank (0 = Bank A, 1 = Bank B) |
| `upgrade_avail` | `0` or `1` | `1` signals a new image has been written to the inactive bank; triggers bank switch on next boot |
| `bootfile` | MTD device path | Kernel partition for the active bank |
| `rootfs_mtd` | MTD device number | ROFS partition passed to kernel cmdline |

These are modified from Linux (running BMC) using:
```bash
fw_setenv boot_side 1        # switch to Bank B
fw_printenv boot_side        # read current value
```

The `fw_setenv` / `fw_printenv` tools (from U-Boot's `tools/` build) operate directly on the `u-boot-env` MTD partition using a CRC-protected env block format.

### obmc-flash-bmc

`obmc-flash-bmc` is the shell script that executes the actual flash write. Its sequence:

```bash
# 1. Determine inactive bank
CURRENT=$(fw_printenv boot_side | cut -d= -f2)
INACTIVE=$([ "$CURRENT" = "0" ] && echo "1" || echo "0")

# 2. Map to MTD devices (exact names are platform-defined in DTS)
KERNEL_MTD=$([ "$INACTIVE" = "0" ] && echo "/dev/mtd-kernel-a" || echo "/dev/mtd-kernel-b")
ROFS_MTD=$([ "$INACTIVE" = "0" ] && echo "/dev/mtd-rofs-a" || echo "/dev/mtd-rofs-b")

# 3. Write kernel to inactive bank
flashcp -v image-kernel "$KERNEL_MTD"

# 4. Write ROFS to inactive bank
flashcp -v image-rofs "$ROFS_MTD"

# 5. Optionally write RWFS (destructive — omitted for OTA)
# flashcp -v image-rwfs /dev/mtd-rwfs

# 6. Mark the new image for activation
fw_setenv upgrade_avail 1
fw_setenv boot_side "$INACTIVE"
```

`flashcp` reads the MTD erase block size from the device, erases in blocks, then writes and verifies. For a 40 MiB ROFS and 8 MiB kernel, this typically takes **3–6 minutes** depending on NOR flash erase/write speed.

### phosphor-software-manager state machine

`phosphor-bmc-code-mgmt` (D-Bus service `xyz.openbmc_project.Software.BMC.Updater`) drives the update state machine. States as they appear in Redfish (`SoftwareInventory.Status`):

```
NotReady        Image received, parsing MANIFEST
    │
    ▼
Ready           MANIFEST valid, version parsed, purpose confirmed
    │           (user or Redfish triggers activation)
    ▼
Activating      obmc-flash-bmc executing (kernel + ROFS being written)
    │    │
    │    └─→ Failed     Signature error, write error, or MTD I/O failure
    ▼
Active          Flash complete, U-Boot env updated
    │           BMC triggers reboot (systemd reboot or obmc-flash-bmc direct call)
    ▼
[BMC reboots — ~90–120 sec until Redfish available again]
```

The `Activating → Active` transition fires a Redfish event, then the BMC system reboots. The Redfish Task associated with the update transitions to `TaskState: "Completed"` just before the reboot.

[↑ Back to Top](#table-of-contents)

---

## Redfish Firmware Update Flow

### SimpleUpdate

The primary mechanism for BMC firmware updates via Redfish:

```bash
BMC="https://192.168.1.100"

curl -k -u admin:password -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "ImageURI": "http://firmware-server.example.com/dgx-bmc-24.01.tar",
    "TransferProtocol": "HTTP",
    "Targets": ["/redfish/v1/Managers/bmc"]
  }' \
  ${BMC}/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate
```

The response is HTTP `202 Accepted` with a `Location` header pointing to the created Task:

```
HTTP/1.1 202 Accepted
Location: /redfish/v1/TaskService/Tasks/1
```

`Targets` is optional on DGX BMC — if omitted, the BMC infers from `PURPOSE=VersionPurpose.BMC` in the MANIFEST. Specifying the Manager URI makes intent explicit and is recommended.

### Multipart direct upload

When no HTTP file server is available, push the tarball directly:

```bash
curl -k -u admin:password -X POST \
  -H "Content-Type: multipart/form-data" \
  -F "UpdateFile=@./dgx-bmc-24.01.tar;type=application/octet-stream" \
  ${BMC}/redfish/v1/UpdateService
```

bmcweb writes the upload to `/tmp/images/<uuid>/` on the BMC's tmpfs, then hands off to `phosphor-bmc-code-mgmt`.

Note: `/tmp/` is on tmpfs (in RAM). The BMC typically has 512 MB–1 GB RAM, so a 50–80 MB tarball fits comfortably, but do not upload while RAM is already under pressure.

### Task lifecycle and states

After posting an update, poll the task:

```bash
curl -k -u admin:password \
  ${BMC}/redfish/v1/TaskService/Tasks/1
```

Full progression:

| `TaskState` | `TaskStatus` | `PercentComplete` | What is happening |
|-------------|-------------|-------------------|-------------------|
| `"Starting"` | `"OK"` | 0 | bmcweb writing tarball to tmpfs |
| `"Running"` | `"OK"` | 0–5 | MANIFEST parsing + signature verification |
| `"Running"` | `"OK"` | 5–95 | `obmc-flash-bmc` writing kernel + ROFS (3–6 min) |
| `"Running"` | `"OK"` | 95–100 | U-Boot env updated, reboot triggered |
| `"Completed"` | `"OK"` | 100 | Flash complete — **BMC is rebooting now** |
| `"Exception"` | `"Critical"` | — | Signature failure, I/O error, or version mismatch |

After `TaskState: "Completed"`, the BMC **automatically reboots**. Your connection will drop. The BMC takes ~90–120 seconds to restart and become reachable again. Poll `GET /redfish/v1/` until it responds.

The `Messages` array in the Task resource contains structured Redfish messages. On failure, look for `MessageId` values like:
- `Base.1.0.FirmwareVerificationFailed` — signing check failed
- `Update.1.0.TransferFailed` — could not fetch image URI
- `Update.1.0.ActivationFailed` — obmc-flash-bmc error

### ApplyTime — deferred activation

DGX BMC supports `ApplyTime` in the `UpdateService` resource to control when the new firmware activates:

```bash
# Stage now, activate immediately (default)
curl -k -u admin:password -X PATCH -H "Content-Type: application/json" \
  -d '{"HttpPushUriOptions": {"HttpPushUriApplyTime": {"ApplyTime": "Immediate"}}}' \
  ${BMC}/redfish/v1/UpdateService

# Stage now, activate only when explicitly reset
curl -k -u admin:password -X PATCH -H "Content-Type: application/json" \
  -d '{"HttpPushUriOptions": {"HttpPushUriApplyTime": {"ApplyTime": "OnReset"}}}' \
  ${BMC}/redfish/v1/UpdateService
```

With `OnReset`, the firmware is written to the inactive bank and U-Boot env is prepared, but the BMC does not reboot until you explicitly trigger `POST /redfish/v1/Managers/bmc/Actions/Manager.Reset`. This is useful for maintenance window scheduling.

[↑ Back to Top](#table-of-contents)

---

## ERoT — Endpoint Root of Trust

### Architecture and scope

NVIDIA's **ERoT** (Endpoint Root of Trust) is a dedicated security co-processor attached to each major system component. It is based on Microsoft's **Cerberus** protocol architecture (contributed to the DMTF). Each ERoT:

- Has its own ROM, OTP key store, and internal flash for the component's firmware staging area
- Boots before the component it protects (GPU, NIC, NVSwitch, BMC)
- Cryptographically verifies the component firmware signature before de-asserting the component's reset
- Maintains firmware measurements accessible via SPDM attestation
- Can recover a component from corrupted firmware using a protected backup copy

On DGX H100/H200, ERoT protection covers:

| Component | ERoT location |
|-----------|--------------|
| BMC itself | Discrete ERoT chip on the management board |
| Each H100/H200 GPU | ERoT integrated into or co-located with each GPU module |
| ConnectX-7 NIC | ERoT within the NIC ASIC security subsystem |
| NVLink Switch ASIC | ERoT within each NVSwitch |
| Host platform controller | ERoT for BIOS/UEFI chain |

> **B200 note:** The Blackwell architecture reportedly integrates the ERoT function more tightly with the GPU die, potentially eliminating discrete ERoT chips. Treat B200 ERoT topology as unconfirmed until consulting the B200 system guide.

### MCTP topology on DGX

MCTP (Management Component Transport Protocol, DMTF DSP0236) is the transport for all ERoT communication. On DGX, two physical bindings are used:

**MCTP over SMBus (DSP0237):**
```
BMC (AST2600)
├── I2C bus 0 → ERoT[BMC]         (BMC's own ERoT)
├── I2C bus 1 → ERoT[GPU0..GPU7]  (8 GPU ERoTs on H100)
├── I2C bus 2 → ERoT[NIC0..NIC1]  (ConnectX-7 NIC ERoTs)
└── I2C bus 3 → ERoT[NVSwitch0..] (NVSwitch ERoTs, if present)
```

**MCTP over PCIe VDM (DSP0238):**
```
BMC (AST2600) ──── PCIe x1 ──── PCIe root complex ──── GPU ERoTs
```

PCIe VDM provides higher bandwidth for firmware data streaming (PLDM Type 5 update payload). SMBus is used for control-plane messages (SPDM attestation, PLDM platform monitoring).

The BMC's `mctpd` daemon manages:
- MCTP endpoint discovery (broadcasting MCTP `Set Endpoint ID` to each bus)
- EID assignment (each ERoT gets a unique Endpoint ID, e.g., GPU0=12, GPU1=13…)
- Routing between transport bindings (bridging SMBus and PCIe VDM messages)

### SPDM attestation

SPDM (Security Protocol and Data Model, DMTF DSP0274) runs over MCTP. After boot, the BMC performs SPDM attestation against each ERoT:

```
BMC (Requester)                    ERoT (Responder)
      │                                  │
      │── GET_VERSION ──────────────────>│
      │<─ VERSION ────────────────────── │
      │── GET_CAPABILITIES ─────────────>│
      │<─ CAPABILITIES ─────────────────│
      │── NEGOTIATE_ALGORITHMS ─────────>│
      │<─ ALGORITHMS ────────────────────│
      │── GET_DIGESTS ──────────────────>│
      │<─ DIGESTS (cert chain hash) ─────│
      │── GET_CERTIFICATE ──────────────>│
      │<─ CERTIFICATE ───────────────────│  (verify ERoT identity)
      │── GET_MEASUREMENTS ─────────────>│
      │<─ MEASUREMENTS (signed) ─────────│  (firmware component hashes)
```

The `MEASUREMENTS` response contains PCR-like registers recording the cryptographic hash of each firmware component the ERoT has measured (GPU VBIOS, NIC firmware, etc.). These are exposed in Redfish under:

```
GET /redfish/v1/ComponentIntegrity/{id}
```

where each ERoT appears as a `ComponentIntegrity` resource with `SPDM.MeasurementSet.Measurements[]` listing the measured firmware hashes.

[↑ Back to Top](#table-of-contents)

---

## PLDM Firmware Update — Component Level

### PLDM Type 5 protocol flow

PLDM for Firmware Update (DMTF DSP0267, Type 5) is the mechanism for updating GPU VBIOS, NIC firmware, NVSwitch firmware, and ERoT firmware itself — everything except the BMC OS. It runs over MCTP.

The BMC's PLDM Update Agent (UA) communicates with each component's PLDM Firmware Device (FD / ERoT):

```
Phase 1 — Discovery
  UA: QueryDeviceIdentifiers    → FD returns component descriptors (vendor/device IDs)
  UA: GetFirmwareParameters     → FD returns component list + current versions

Phase 2 — Initiation
  UA: RequestUpdate             → Initiate update session (includes UA capabilities)
  FD: RequestUpdateResponse     → FD accepts, returns max transfer size

Phase 3 — Component table
  UA: PassComponentTable        → List of components UA intends to update
  FD: UpdateComponent (repeat)  → Per-component accept/reject decision

Phase 4 — Firmware transfer (per accepted component)
  UA: RequestFirmwareData       → FD requests next chunk (pull model)
  UA: [send chunk] ──────────>  → UA sends firmware data in blocks (256B–4KB typical)
  [repeat until full image transferred]

Phase 5 — Verification and activation
  UA: VerifyComplete            → FD verifies integrity + signature
  FD: TransferComplete          → ACK
  UA: ApplyComplete             → FD applies firmware (may reset component)
  UA: ActivateFirmware          → Request component activation
  FD: ActivateFirmwareResponse  → Returns estimated time until component reset completes
```

The ERoT validates the firmware payload cryptographically (the component vendor's private key is the signing authority, not the BMC's key). VBIOS must be NVIDIA-signed; NIC firmware must be NVIDIA/Mellanox-signed.

### pldmd and pldmtool

`pldmd` runs on the BMC as a systemd service. `pldmtool` is the companion CLI for direct PLDM operations from the BMC shell (requires root access to BMC, e.g., via SSH or SOL):

```bash
# Discover MCTP endpoints
pldmtool discovery GetTID -m 12     # Query EID 12 for its TID

# Firmware update operations
pldmtool fw_update GetFirmwareParameters -m 12
# Returns: component list, current versions, capabilities

pldmtool fw_update QueryDeviceIdentifiers -m 12
# Returns: vendor descriptor (0x0A3E = NVIDIA), device identifiers

# Trigger a component update (initiates the PLDM Type 5 flow)
pldmtool fw_update UpdateComponent -m 12 -c 0 -f /tmp/vbios-94.02.bin
```

### Component firmware inventory

Redfish exposes each updatable component in `FirmwareInventory`:

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/UpdateService/FirmwareInventory/
```

A DGX H100 node will list:

| `Id` | `Name` | `Updateable` | Updated via |
|------|--------|-------------|-------------|
| `BMC` | DGX BMC | `true` | Redfish `SimpleUpdate` → obmc-flash-bmc |
| `BIOS` | System BIOS/UEFI | `true` | Redfish → HMC → host power cycle |
| `GPU0-VBIOS`…`GPU7-VBIOS` | H100 VBIOS (×8) | `true` | Redfish → PLDM/ERoT → host power cycle |
| `NIC0-FW`…`NIC1-FW` | ConnectX-7 NIC (×2) | `true` | Redfish → PLDM/ERoT → link reset |
| `BMC-ERoT` | BMC Endpoint Root of Trust | `true` | Redfish → PLDM (self-update) |
| `GPU0-ERoT`…`GPU7-ERoT` | GPU ERoT (×8) | `true` | Redfish → PLDM/ERoT chain |
| `Retimer` | PCIe retimer | `true` | Redfish → PLDM/I2C |

[↑ Back to Top](#table-of-contents)

---

## Component Firmware Details

### GPU VBIOS

The GPU VBIOS is stored in dedicated VBIOS flash on the GPU module (not on the BMC NOR). The update path:

```
Redfish POST → UpdateService (target: /Systems/1/Processors/GPU0)
    │
    ▼
bmcweb → NVIDIA firmware update daemon
    │
    ▼
PLDM Type 5 over MCTP/PCIe-VDM → GPU ERoT
    │
    ▼
ERoT verifies NVIDIA signature → programs VBIOS flash
    │
    ▼
Activation requires host power cycle (GPU reset de-asserts after ERoT unlocks)
```

**Activation timing:** VBIOS updates take effect only after the host is powered off and back on. A simple `GracefulRestart` of the OS is not sufficient — the GPU ERoT needs a cold power cycle to re-verify and load the new VBIOS.

**nvflash in managed environments:** `nvflash` (NVIDIA's direct PCIe VBIOS flash tool) bypasses the ERoT pipeline. In production DGX deployments with secure boot enabled, using `nvflash` directly from the OS is not supported — the ERoT will re-verify on next power cycle and may reject firmware that was not staged through the proper chain. Use the Redfish path.

### ConnectX NIC firmware

ConnectX-7 (CX7) NIC firmware updates:

```
Redfish POST → UpdateService (target: /Systems/1/NetworkAdapters/NIC0)
    │
    ▼
PLDM Type 5 over MCTP/SMBus → NIC ERoT
    │
    ▼
ERoT verifies Mellanox/NVIDIA signature → programs NIC flash
    │
    ▼
Activation requires link reset or host PCIe reset
```

Firmware version is visible in Redfish at:
```
GET /redfish/v1/Systems/1/NetworkAdapters/NIC0/Ports/
```
and via `mlxfwmanager` on the host OS.

### NVSwitch / NVLink Switch firmware

NVSwitch firmware on DGX H100 resides in NVLink Switch Systems (separate from the compute nodes). They have their own management interface, updated via:

- **NVIDIA UFM** (Unified Fabric Manager) — the primary orchestrator for NVLink Switch firmware
- PLDM Type 5 over MCTP via the switch's BMC or management port
- Requires NVLink fabric to be quiesced during update (no active NVLink traffic)

### HMC — Host Management Controller

Some DGX variants include an **HMC** (distinct from the BMC) that manages the host CPU platform controller, BIOS power sequencing, and dual-BIOS fail-safe logic. HMC firmware:

```
Redfish POST → UpdateService (target: /Managers/hmc)
    │
    ▼
phosphor-bmc-code-mgmt (PURPOSE=VersionPurpose.HMC or similar)
    │
    ▼
PLDM Type 5 → HMC
```

Activation requires a host power cycle (HMC controls platform power).

### ERoT firmware itself

ERoT firmware can be updated via PLDM Type 5. The ERoT implements a self-update mechanism where the PLDM Update Agent (the BMC's `pldmd`) streams the new ERoT firmware to the ERoT, which verifies and applies it.

ERoT updates are generally rare — performed only for security patches or new feature support. An ERoT update does not require a host power cycle; the ERoT self-resets after applying the new firmware (typically within a few seconds). However, during the ERoT reset, the protected component (GPU, NIC) may become temporarily inaccessible.

[↑ Back to Top](#table-of-contents)

---

## Filesystem Overlays and Hot-Patching

### What the overlay enables

Because the OverlayFS upper layer (RWFS) can shadow any path from the ROFS, it is possible to:

1. **Persist configuration changes** — write to `/etc/network/`, `/etc/ntp.conf`, etc., and the change survives reboots.
2. **Shadow a ROFS file** — write a modified copy of any ROFS file to the same path; the RWFS copy takes precedence on subsequent boots.
3. **Add new files** — place new scripts or configs at any path; they appear in the unified filesystem.

**Example: shadow a BMC configuration file**
```bash
# On the BMC shell (requires root / BMC SSH access)
# Suppose you want to modify /etc/bmc-config.json (hypothetical)
# The ROFS copy is read-only, but:
cp /etc/bmc-config.json /etc/bmc-config.json.bak
cat > /etc/bmc-config.json << 'EOF'
{ "poll_interval": 30 }
EOF
# This writes to RWFS; the ROFS copy is unchanged but shadowed
systemctl restart phosphor-config-manager   # restart the daemon to pick up the change
```

The shadow survives reboots. To remove it (revert to ROFS default), delete the file — the RWFS whiteout entry is itself removed, and the ROFS version becomes visible again.

### Why hot-patching firmware is not supported

**"Hot-patching" in the sense of modifying running BMC daemons without a reboot is not supported on DGX BMC.** The reasons are architectural:

1. **SquashFS is immutable** — the running filesystem's lower layer cannot be modified. Writing to a ROFS path creates an RWFS overlay entry, but the running daemon is already loaded from the ROFS version in memory. A daemon restart is required to pick up the RWFS-shadowed version.

2. **Secure boot chain measurement** — the ERoT and SPDM attestation measure firmware at boot time. A hot-patched daemon that differs from the measured ROFS would cause attestation mismatches; remote parties would detect the discrepancy.

3. **Kernel and bootloader** — the running Linux kernel and U-Boot are in NOR flash, not in the OverlayFS. They cannot be replaced without a full reflash + reboot cycle.

4. **NVIDIA design intent** — the BMC firmware is treated as a versioned unit. NVIDIA validates and signs complete firmware images; partial or runtime-patched states are not a supported configuration.

**What this means in practice:** Any change to the BMC's `bmcweb`, `pldmd`, `mctpd`, or other daemons requires a full firmware update (via Redfish UpdateService → A/B bank swap → BMC reboot). Plan for ~5–10 minutes of BMC downtime per update.

### Effective overlay techniques

While firmware hot-patching is not supported, the overlay filesystem does enable legitimate runtime operations:

| Use case | Technique | Persists? |
|----------|-----------|-----------|
| Update network config | Write to `/etc/systemd/network/` | Yes (RWFS) |
| Add SSH authorized key | Write to `/home/<user>/.ssh/authorized_keys` | Yes (RWFS) |
| Install a CA certificate | Write to `/etc/ssl/certs/` | Yes (RWFS) |
| Adjust a config file | Shadow the ROFS file in-place | Yes (RWFS) |
| Temporary debug script | Write to `/tmp/` | No (tmpfs) |
| Test a config change | Shadow to `/etc/`, restart service | Yes (RWFS) — revert with `rm` |
| Wipe all customization | Factory reset (wipes RWFS) | n/a — see below |

[↑ Back to Top](#table-of-contents)

---

## DGX SuperPod Fleet Firmware Coordination

### Component inventory per node

A DGX H100 node has the following firmware-managed components (indicative, varies by DGX SKU):

| Component | Count | Update method | Requires |
|-----------|-------|--------------|---------|
| BMC | 1 | Redfish SimpleUpdate | BMC reboot (~2 min) |
| System BIOS/UEFI | 1 | Redfish → HMC | Host power cycle |
| GPU VBIOS (H100) | 8 | Redfish → PLDM/ERoT | Host power cycle |
| ConnectX-7 NIC | 2–4 | Redfish → PLDM/ERoT | Link reset |
| PCIe retimer | 1–2 | Redfish → PLDM/I2C | Host power cycle |
| GPU ERoT | 8 | Redfish → PLDM self-update | ERoT self-reset |
| BMC ERoT | 1 | Redfish → PLDM self-update | ERoT self-reset |
| NIC ERoT | 2–4 | Redfish → PLDM self-update | ERoT self-reset |

A full firmware refresh of one DGX H100 node (all components) requires approximately:
- 1 BMC reboot (~2 min)
- 1–2 host power cycles (~10 min including OS boot validation)
- Total per-node time: **15–25 minutes** including health validation

### Coordinated update sequence

For a DGX SuperPod, NVIDIA recommends this sequence to minimize disruption:

```
Phase 0 — Pre-update health check
  nvsm show health                     # verify all nodes healthy before starting
  GET /redfish/v1/ on all BMCs         # confirm Redfish reachable

Phase 1 — NVLink Switch firmware (via UFM)
  ufm firmware upgrade --target nvswitch --version <ver>
  # NVLink fabric goes offline during switch firmware update
  # Compute workloads must be quiesced

Phase 2 — InfiniBand switch firmware (via UFM)
  ufm firmware upgrade --target ib-switch --version <ver>

Phase 3 — Per DGX node (serial or small batch):
  a. BMC firmware
     POST /redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate
     → wait for BMC reboot (~2 min)
     → verify new BMC version

  b. GPU VBIOS (while host is running — but activation deferred)
     POST to each GPU target with ApplyTime=OnReset
     → flash staged, no GPU disruption yet

  c. NIC firmware (with ApplyTime=OnReset)
     POST to each NIC target
     → flash staged, no disruption yet

  d. BIOS firmware (with ApplyTime=OnReset)
     POST to system BIOS target

  e. Single host power cycle
     → All staged updates activate simultaneously (GPU VBIOS, NIC, BIOS)
     → One reboot handles all component firmware changes

  f. Post-update validation
     nvidia-smi --query-gpu=vbios_version
     GET /redfish/v1/UpdateService/FirmwareInventory/ → verify all versions
     nvsm show health

Phase 4 — Next node (proceed only if previous node passes health check)
```

This approach minimizes the number of host reboots: one per node for all component firmware, plus one separate BMC reboot.

### NVIDIA fleet tools

| Tool | Runs on | Purpose |
|------|---------|---------|
| `nvsm` | DGX OS (host) | System health aggregation, `nvsm update firmware` orchestrates Redfish calls |
| `nvbmcutil` | Management node | Direct Redfish CLI wrapper for BMC operations |
| `dgx-fw-update` | Management node | Multi-node firmware update orchestration, staged rollout |
| `ufm` | UFM server | InfiniBand and NVLink fabric management, switch firmware |
| `mlxfwmanager` | DGX OS (host) | NIC firmware inventory and update (host-side alternative to Redfish) |
| Base Command Manager | Management server | Full pod lifecycle — provisioning, health, firmware |

```bash
# nvsm (on DGX OS)
nvsm show health
nvsm show gpus
nvsm update firmware --component bmc --version 24.01

# dgx-fw-update (on management node, targeting multiple BMCs)
dgx-fw-update --component bmc --version 24.01 \
  --hosts bmc-dgx-01.mgmt,bmc-dgx-02.mgmt,bmc-dgx-03.mgmt

# nvbmcutil (single BMC)
nvbmcutil --host 192.168.1.100 --user admin --password secret info
nvbmcutil --host 192.168.1.100 firmware update --file dgx-bmc-24.01.tar
```

[↑ Back to Top](#table-of-contents)

---

## Factory Reset and Overlay Management

### ResetToDefaults types

```bash
curl -k -u admin:password -X POST -H "Content-Type: application/json" \
  -d '{"ResetToDefaultsType": "ResetAll"}' \
  https://192.168.1.100/redfish/v1/Managers/bmc/Actions/Manager.ResetToDefaults
```

| `ResetToDefaultsType` | What happens |
|----------------------|-------------|
| `"ResetAll"` | RWFS is erased (UBIFS formatted or JFFS2 blanked). All configuration, user accounts, certificates, SSH keys reset to ROFS defaults. BMC reboots. |
| `"PreserveNetworkAndUsers"` | RWFS erased, but network interface configuration and local user accounts are re-applied before reboot. |
| `"PreserveNetwork"` | RWFS erased, network config preserved, user accounts reset. |

> **Note:** `ResetToDefaults` does **not** affect firmware (ROFS, kernel, U-Boot). The installed firmware version is unchanged. Only the RWFS configuration overlay is affected.

SDK equivalent:

```python
with RedfishClient("https://192.168.1.100", "admin", "password") as rf:
    rf.manager().reset_to_defaults("ResetAll")
    # BMC will reboot — connection drops ~90 sec
```

### What is preserved vs. wiped

| Item | After `ResetAll` | After `PreserveNetworkAndUsers` |
|------|-----------------|--------------------------------|
| Network IP/VLAN | Reset to ROFS default (DHCP) | **Preserved** |
| Local user accounts | Reset (only ROFS default accounts) | **Preserved** |
| Passwords | Reset to ROFS defaults | **Preserved** |
| SSH host keys | Regenerated | Regenerated |
| TLS server certificate | Reset to self-signed | Reset |
| Custom CA certificates | Wiped | Wiped |
| LDAP/AD configuration | Wiped | Wiped |
| NTP server config | Reset to ROFS defaults | **Preserved** (via network config) |
| SEL event log | Wiped (stored in RWFS) | Wiped |
| phosphor-settings state | Wiped | Wiped |
| GPU/component firmware | **Unchanged** (in NOR/component flash) | **Unchanged** |
| BMC firmware (ROFS) | **Unchanged** | **Unchanged** |
| U-Boot + bootloader | **Unchanged** | **Unchanged** |

### Manual RWFS clear from BMC shell

If the RWFS is corrupted and the BMC cannot boot cleanly enough to serve Redfish:

```bash
# On BMC shell (via SOL: ipmitool -I lanplus -H <bmc-ip> -U admin -P <pw> sol activate)
# or physical UART console

# Find the rwfs MTD device
cat /proc/mtd | grep rwfs
# Example output: mtd8: 01000000 00010000 "rwfs"

# For JFFS2 RWFS: erase and reformat
flash_erase /dev/mtd8 0 0
# Reboot — JFFS2 is empty, mounts cleanly

# For UBIFS RWFS: detach UBI, format, reboot
ubidetach -p /dev/mtd8
ubiformat /dev/mtd8 -y
# Reboot — UBIFS starts fresh
```

[↑ Back to Top](#table-of-contents)

---

## Security and Secure Boot Chain

### AST2600 hardware root of trust

The ASPEED AST2600 includes a secure boot subsystem anchored in immutable on-chip ROM and **OTP (One-Time Programmable) fuses**:

- The OTP stores the SHA-256 hash of the U-Boot public key (RSA-4096 or ECDSA-384)
- A separate OTP fuse enables secure boot enforcement
- The on-chip Boot ROM reads U-Boot from NOR flash, computes its hash, verifies against the OTP-stored key hash, and only jumps to U-Boot if verification passes
- If verification fails and secure boot is enabled: the Boot ROM halts (or signals a failure LED) — it does not fall through to an unverified image

The OTP fuses are **physically irreversible** — once the secure-boot enable fuse is blown (which NVIDIA does during manufacturing), it cannot be reversed.

### Full verification chain

```
┌─ HARDWARE BOUNDARY ───────────────────────────────────────────────┐
│  AST2600 Boot ROM (on-chip ROM, immutable)                        │
│      Verifies: U-Boot  via OTP RSA/ECDSA key hash                 │
└───────────────────────────────────────────────────────────────────┘
           │ PASS
           ▼
┌─ U-BOOT ──────────────────────────────────────────────────────────┐
│      Verifies: FIT image (kernel + DTB)  via embedded public key  │
│      Passes:   rootfs_mtd=mtdX to kernel cmdline                  │
└───────────────────────────────────────────────────────────────────┘
           │ PASS
           ▼
┌─ LINUX KERNEL ────────────────────────────────────────────────────┐
│      Mounts: SquashFS ROFS (read-only, integrity via dm-verity)   │
│      Mounts: UBIFS RWFS (read-write, NOT cryptographically        │
│              verified — trust boundary stops at ROFS)             │
└───────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─ RUNNING BMC OS ──────────────────────────────────────────────────┐
│      phosphor-bmc-code-mgmt                                       │
│          Verifies: new firmware image RSA signature               │
│          before writing to NOR flash                              │
└───────────────────────────────────────────────────────────────────┘
```

Parallel to the BMC chain, each component's ERoT runs its own verification:

```
┌─ ERoT (per GPU, NIC, NVSwitch) ───────────────────────────────────┐
│  ERoT ROM → verifies ERoT firmware → measures component firmware  │
│  PLDM firmware update → ERoT verifies payload before application  │
│  SPDM attestation → BMC can query measurements                    │
└───────────────────────────────────────────────────────────────────┘
```

### Unsigned image rejection

When `phosphor-bmc-code-mgmt` receives a firmware tarball:

1. Extracts `MANIFEST` — parses `PURPOSE`, `VERSION`, `MACHINE`
2. Locates `publickey` in the tarball
3. Compares `publickey` against the trusted key in `/etc/activationdata/` (ROFS — read-only, part of the secure chain)
4. If keys do not match → reject immediately; D-Bus Activation = `Failed`
5. If keys match → verifies `image-kernel.sig` and `image-rofs.sig` with `openssl dgst -verify`
6. If any signature fails → reject; D-Bus Activation = `Failed`
7. Only if all checks pass → proceeds to `obmc-flash-bmc`

On signature failure, the Redfish Task shows:
```json
{
  "TaskState": "Exception",
  "TaskStatus": "Critical",
  "Messages": [
    {
      "MessageId": "Update.1.0.ActivationFailed",
      "Message": "Firmware image signature verification failed."
    }
  ]
}
```

The BMC does **not reboot** on failure. It continues serving Redfish on the existing firmware.

### RWFS is not verified

The RWFS overlay upper layer is intentionally outside the cryptographic verification chain. This means:

- A sufficiently privileged attacker with BMC shell access could shadow `/etc/` files to alter BMC behavior
- The SPDM measurements (taken at boot from the ROFS) would not reflect RWFS modifications
- **Mitigation:** Restrict BMC shell access (SSH, SOL). Never expose the BMC management port to untrusted networks. Monitor SPDM measurements from an external attestation server.

This is a fundamental property of the OpenBMC OverlayFS design, not a NVIDIA-specific gap. Production DGX deployments mitigate it through network isolation and access control rather than cryptographic enforcement of RWFS content.

[↑ Back to Top](#table-of-contents)

---

## Working with BMC Images via Redfish

### Checking firmware inventory

```bash
BMC="https://192.168.1.100"
AUTH="-u admin:password"

# Full firmware inventory
curl -k $AUTH ${BMC}/redfish/v1/UpdateService/FirmwareInventory/ | python3 -m json.tool

# Specific component
curl -k $AUTH ${BMC}/redfish/v1/UpdateService/FirmwareInventory/BMC
curl -k $AUTH ${BMC}/redfish/v1/UpdateService/FirmwareInventory/GPU0-VBIOS
```

### Triggering updates via pykesys_redfish

```python
import time
from pykesys_redfish import RedfishClient, RedfishTimeoutError

BMC = "https://192.168.1.100"
FIRMWARE_URI = "http://fw-server.mgmt/dgx-bmc-24.01.tar"

def update_bmc_firmware(host: str, firmware_uri: str) -> dict:
    with RedfishClient(host, "admin", "password") as rf:
        # Check current version
        mgr = rf.manager()
        current = mgr.firmware_version
        print(f"Current: {current}")

        # Trigger SimpleUpdate
        result = rf.post(
            "/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
            {
                "ImageURI": firmware_uri,
                "TransferProtocol": "HTTP",
                "Targets": [f"{rf._session.base_url}/redfish/v1/Managers/bmc"],
            },
        )

    # result is None (202 response has no body) or a dict with @odata.id
    print(f"Update triggered. BMC will reboot when flash completes.")
    return {"host": host, "previous_version": current}

update_bmc_firmware(BMC, FIRMWARE_URI)
```

### Monitoring update tasks

```python
import time
import httpx

def poll_task(bmc: str, task_uri: str, timeout: int = 600) -> dict:
    """Poll a Redfish Task until terminal state or timeout."""
    deadline = time.time() + timeout
    auth = ("admin", "password")

    while time.time() < deadline:
        try:
            r = httpx.get(
                f"https://{bmc}{task_uri}",
                auth=auth,
                verify=False,
                timeout=10,
            )
            if r.status_code == 200:
                task = r.json()
                state = task.get("TaskState")
                pct = task.get("PercentComplete", 0)
                print(f"  TaskState={state}  {pct}%")

                if state == "Completed":
                    return {"status": "ok", "task": task}
                if state == "Exception":
                    msgs = [m.get("Message") for m in task.get("Messages", [])]
                    return {"status": "failed", "messages": msgs}
        except httpx.ConnectError:
            # BMC is rebooting — expected after Completed
            print("  BMC connection dropped (rebooting...)")

        time.sleep(15)

    return {"status": "timeout"}
```

### Polling until BMC recovers

After a firmware update, the BMC reboots. Poll until Redfish responds again:

```python
def wait_for_bmc(host: str, timeout: int = 300) -> bool:
    """Wait for BMC to come back online after a reboot."""
    import httpx
    deadline = time.time() + timeout
    auth = ("admin", "password")

    print(f"Waiting for BMC at {host} to recover...")
    while time.time() < deadline:
        try:
            r = httpx.get(
                f"https://{host}/redfish/v1/",
                auth=auth,
                verify=False,
                timeout=5,
            )
            if r.status_code == 200:
                data = r.json()
                print(f"BMC online. Redfish version: {data.get('RedfishVersion')}")
                return True
        except Exception:
            pass
        time.sleep(10)

    print("Timeout waiting for BMC recovery")
    return False

# Full update + verify flow
with RedfishClient(BMC, "admin", "password") as rf:
    old_version = rf.manager().firmware_version

rf.post("/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate", {...})
time.sleep(30)   # give the BMC time to start flashing

if wait_for_bmc("192.168.1.100", timeout=300):
    with RedfishClient(BMC, "admin", "password") as rf:
        new_version = rf.manager().firmware_version
    print(f"Update complete: {old_version} → {new_version}")
```

[↑ Back to Top](#table-of-contents)

---

## Troubleshooting

### Firmware update task stuck at 0% / `TaskState: Starting`

- The BMC is still downloading the image or writing to tmpfs. Check if `ImageURI` is reachable from the BMC's management network.
- For multipart upload, the connection may have timed out mid-transfer. Retry the upload.
- Check BMC journal via SOL: `journalctl -u phosphor-download-manager -f`

### `TaskState: Exception` — signature verification failed

- The firmware tarball was not signed with NVIDIA's BMC key for this platform.
- Verify you have the correct firmware for the DGX generation (H100 firmware will not install on A100 BMC — `MACHINE` mismatch in MANIFEST).
- Verify the download was not corrupted: `sha256sum dgx-bmc-24.01.tar` and compare against NVIDIA's published checksum.

### BMC does not come back after update

- Wait at least 3 minutes before diagnosing. AST2600 boot with UBIFS mount can take up to 2 minutes.
- If still unreachable: connect via SOL (`ipmitool -I lanplus sol activate`) to see boot messages.
- Check U-Boot output for `upgrade_avail=1` bank switch. If the new bank fails to boot, U-Boot may fall back to the old bank (platform-dependent).
- **Last resort:** If both banks are corrupted or U-Boot fails, the AST2600 has a low-level UART recovery mode. Consult the NVIDIA DGX Hardware Maintenance Guide for the platform-specific recovery procedure.

### PLDM update fails / component firmware not updating

- Check that `mctpd` is running: `systemctl status mctpd`
- Verify the ERoT is reachable: `pldmtool discovery GetTID -m <eid>`
- Check MCTP bus connectivity via dmesg for I2C errors
- Ensure the host is powered on (MCTP/PCIe-VDM to GPU ERoTs requires PCIe link to be active)
- For GPU VBIOS: confirm the host OS is not holding an exclusive PCIe lock on the GPU

### ResetToDefaults wipes network config and BMC becomes unreachable

If you ran `ResetAll` and the BMC defaulted to DHCP (or a different IP):
- Use the console: SOL via IPMI KCS interface from the host, or physical UART serial
- Or use the host-side IPMI over LAN with the old IP while it remains valid: `ipmitool -I lan -H <old-ip> -U admin -P <pw> raw 0x3a ...`
- Use DHCP lease tables to find the new IP, or assign a static IP at BIOS/BMC setup level before the next reset

### SPDM attestation shows unexpected measurements

- If `ComponentIntegrity` measurements for a GPU do not match the expected values for the installed VBIOS version: the GPU VBIOS was updated via a path that bypassed the ERoT chain (e.g., `nvflash` from the OS), or the VBIOS flash is corrupted.
- Run `nvidia-smi --query-gpu=vbios_version` to cross-check the current GPU-reported VBIOS version.
- If measurements are inconsistent, initiate a VBIOS update via the Redfish path to restore a known-good signed image and re-establish measurement consistency.

[↑ Back to Top](#table-of-contents)
