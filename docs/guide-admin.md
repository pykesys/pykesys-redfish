# Redfish Admin Guide

This guide covers the operational, security, and configuration responsibilities of administrators who deploy and manage Redfish-enabled systems. It assumes you are responsible for BMC configuration, user management, firmware lifecycle, and automation infrastructure.

See [redfish.md](redfish.md) for protocol background and [guide-users.md](guide-users.md) for day-to-day user operations.

---

## Initial BMC Setup

Before a server can be managed via Redfish, the BMC requires initial configuration. This is typically done via physical console (BIOS setup), vendor-specific tools, or a pre-provisioning script run from the OS side.

### Required Initial Steps

1. Assign a static IP or configure DHCP reservation for the BMC NIC
2. Set a strong admin password (vendor default passwords are well-known — change them immediately)
3. Enable HTTPS, disable HTTP redirect if not needed
4. Disable unused protocols (IPMI-over-LAN, SNMP, Telnet, KVMIP) unless explicitly needed
5. Import or generate a trusted TLS certificate
6. Configure NTP for accurate timestamps in logs

---

## Network Configuration

BMC network settings live under the Manager resource.

### View BMC Network Interfaces

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Managers/1/EthernetInterfaces/
```

### View Specific Interface

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Managers/1/EthernetInterfaces/NIC1/
```

Key fields: `IPv4Addresses`, `IPv6Addresses`, `MACAddress`, `DHCPv4.DHCPEnabled`, `VLANs`, `FQDN`.

### Set a Static IP Address

```bash
curl -k -u admin:password \
  -X PATCH \
  -H "Content-Type: application/json" \
  -d '{
    "DHCPv4": {"DHCPEnabled": false},
    "IPv4StaticAddresses": [{
      "Address": "192.168.1.100",
      "SubnetMask": "255.255.255.0",
      "Gateway": "192.168.1.1"
    }]
  }' \
  https://192.168.1.100/redfish/v1/Managers/1/EthernetInterfaces/NIC1/
```

Network changes may require a BMC reset to take effect (`Managers/1/Actions/Manager.Reset`).

### Configure DNS

```bash
curl -k -u admin:password \
  -X PATCH \
  -H "Content-Type: application/json" \
  -d '{
    "NameServers": ["10.0.0.53", "10.0.0.54"],
    "FQDN": "bmc-hostname.example.com"
  }' \
  https://192.168.1.100/redfish/v1/Managers/1/EthernetInterfaces/NIC1/
```

---

## Protocol Management

Enable and disable network protocols exposed by the BMC.

### View Protocol Settings

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Managers/1/NetworkProtocol/
```

### Disable IPMI-over-LAN

IPMI-over-LAN is a legacy protocol with known security issues (RAKP vulnerability, weak authentication). Disable it unless required by legacy tooling.

```bash
curl -k -u admin:password \
  -X PATCH \
  -H "Content-Type: application/json" \
  -d '{"IPMI": {"ProtocolEnabled": false}}' \
  https://192.168.1.100/redfish/v1/Managers/1/NetworkProtocol/
```

### Disable SNMP

```bash
curl -k -u admin:password \
  -X PATCH \
  -H "Content-Type: application/json" \
  -d '{"SNMP": {"ProtocolEnabled": false}}' \
  https://192.168.1.100/redfish/v1/Managers/1/NetworkProtocol/
```

### Enforce HTTPS Only

```bash
curl -k -u admin:password \
  -X PATCH \
  -H "Content-Type: application/json" \
  -d '{"HTTP": {"ProtocolEnabled": false}, "HTTPS": {"ProtocolEnabled": true, "Port": 443}}' \
  https://192.168.1.100/redfish/v1/Managers/1/NetworkProtocol/
```

### Configure NTP

```bash
curl -k -u admin:password \
  -X PATCH \
  -H "Content-Type: application/json" \
  -d '{
    "NTP": {
      "ProtocolEnabled": true,
      "NTPServers": ["ntp1.example.com", "ntp2.example.com"]
    }
  }' \
  https://192.168.1.100/redfish/v1/Managers/1/NetworkProtocol/
```

---

## Account and Role Management

Redfish enforces role-based access control (RBAC). Accounts are managed under `AccountService`.

### View Account Service Configuration

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/AccountService/
```

Key settings: `MinPasswordLength`, `MaxPasswordLength`, `AccountLockoutThreshold`, `AccountLockoutDuration`, `AuthFailureLoggingThreshold`.

### List Accounts

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/AccountService/Accounts/
```

### Create a User Account

```bash
curl -k -u admin:password \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "UserName": "operator1",
    "Password": "SecureP@ss123!",
    "RoleId": "Operator",
    "Enabled": true
  }' \
  https://192.168.1.100/redfish/v1/AccountService/Accounts/
```

### Built-in Redfish Roles

| RoleId | Privileges |
|--------|-----------|
| `Administrator` | Full read/write, account management, config changes |
| `Operator` | Power operations, boot config, log access; no account management |
| `ReadOnly` | Read-only access to all resources; no write operations |

### Modify an Existing Account

Change password:

```bash
curl -k -u admin:password \
  -X PATCH \
  -H "Content-Type: application/json" \
  -d '{"Password": "NewSecureP@ss456!"}' \
  https://192.168.1.100/redfish/v1/AccountService/Accounts/2
```

Disable an account without deleting it:

```bash
curl -k -u admin:password \
  -X PATCH \
  -H "Content-Type: application/json" \
  -d '{"Enabled": false}' \
  https://192.168.1.100/redfish/v1/AccountService/Accounts/2
```

### Delete a User Account

```bash
curl -k -u admin:password \
  -X DELETE \
  https://192.168.1.100/redfish/v1/AccountService/Accounts/2
```

### Configure Account Lockout Policy

```bash
curl -k -u admin:password \
  -X PATCH \
  -H "Content-Type: application/json" \
  -d '{
    "AccountLockoutThreshold": 5,
    "AccountLockoutDuration": 300,
    "AccountLockoutCounterResetAfter": 120
  }' \
  https://192.168.1.100/redfish/v1/AccountService/
```

This locks an account for 300 seconds after 5 failed attempts, with the failure counter resetting after 120 seconds of no attempts.

---

## TLS Certificate Management

### View Current Certificate

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Managers/1/NetworkProtocol/HTTPS/Certificates/
```

### Replace the Self-Signed Certificate

1. Generate a CSR via the BMC (vendor-specific; some support `CertificateService.GenerateCSR`)
2. Sign the CSR with your internal CA
3. Import the signed certificate

**Import a PEM certificate:**

```bash
curl -k -u admin:password \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "CertificateType": "PEM",
    "CertificateString": "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----\n-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
  }' \
  https://192.168.1.100/redfish/v1/Managers/1/NetworkProtocol/HTTPS/Certificates/
```

### Import a CA Certificate (for client certificate auth or trust anchors)

```bash
curl -k -u admin:password \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "CertificateType": "PEM",
    "CertificateString": "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----"
  }' \
  https://192.168.1.100/redfish/v1/AccountService/LDAP/Certificates/
```

---

## Firmware and BIOS Updates

Firmware updates are managed via `UpdateService`. The process differs slightly between vendors but follows the same Redfish pattern.

### Check Current Firmware Inventory

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/UpdateService/FirmwareInventory/
```

Lists all firmware components: BMC, BIOS, NIC, HBA, PSU, CPLD. Each entry shows `Version` and `Updateable`.

### Simple HTTP(S) Push Update

For vendors that support `SimpleUpdate` with an HTTP URI:

```bash
curl -k -u admin:password \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "TransferProtocol": "HTTPS",
    "ImageURI": "https://firmware-server.example.com/bios-2.1.0.bin",
    "Targets": ["/redfish/v1/UpdateService/FirmwareInventory/BIOS"]
  }' \
  https://192.168.1.100/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate
```

### Multipart Push Update (Direct Upload)

For direct binary upload (when HTTP source is not available):

```bash
curl -k -u admin:password \
  -X POST \
  -H "Content-Type: multipart/form-data" \
  -F "UpdateParameters={\"Targets\":[\"/redfish/v1/UpdateService/FirmwareInventory/BMC\"]};type=application/json" \
  -F "UpdateFile=@/tmp/bmc-firmware-4.5.0.bin;type=application/octet-stream" \
  https://192.168.1.100/redfish/v1/UpdateService/
```

### Monitor Update Progress via Task

Firmware updates are long-running operations that return a Task URI via the `Location` header:

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/TaskService/Tasks/1/
```

Poll this until `TaskState` is `Completed` or `Exception`. Key fields: `TaskState`, `TaskStatus`, `PercentComplete`, `Messages`.

### BIOS Settings

Read BIOS attributes:

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Systems/1/Bios/
```

Stage BIOS attribute changes (applied on next reboot):

```bash
curl -k -u admin:password \
  -X PATCH \
  -H "Content-Type: application/json" \
  -d '{"Attributes": {"ProcHyperthreading": "Disabled", "SriovGlobalEnable": "Enabled"}}' \
  https://192.168.1.100/redfish/v1/Systems/1/Bios/Settings/
```

Reset BIOS to factory defaults:

```bash
curl -k -u admin:password \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{}' \
  https://192.168.1.100/redfish/v1/Systems/1/Bios/Actions/Bios.ResetBios
```

---

## BMC Reset and Factory Reset

### Reset the BMC (Graceful)

Reboots the BMC firmware without affecting the host OS. Required after some network configuration changes.

```bash
curl -k -u admin:password \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"ResetType": "GracefulRestart"}' \
  https://192.168.1.100/redfish/v1/Managers/1/Actions/Manager.Reset
```

### Factory Reset the BMC

Erases all BMC configuration and returns it to factory defaults. Use only when decommissioning or re-provisioning.

```bash
curl -k -u admin:password \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"ResetToDefaultsType": "ResetAll"}' \
  https://192.168.1.100/redfish/v1/Managers/1/Actions/Manager.ResetToDefaults
```

---

## Virtual Media

Virtual media allows mounting ISO images or USB images from a remote HTTP/HTTPS server, enabling OS installation or recovery without physical media.

### Mount a Remote ISO

```bash
curl -k -u admin:password \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "Image": "https://os-server.example.com/images/rhel9.iso",
    "MediaTypes": ["DVD"],
    "TransferMethod": "Stream",
    "Inserted": true,
    "WriteProtected": true
  }' \
  https://192.168.1.100/redfish/v1/Managers/1/VirtualMedia/CD1/Actions/VirtualMedia.InsertMedia
```

### Unmount Virtual Media

```bash
curl -k -u admin:password \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{}' \
  https://192.168.1.100/redfish/v1/Managers/1/VirtualMedia/CD1/Actions/VirtualMedia.EjectMedia
```

### Boot to Virtual Media (One-Time)

Combine with boot override:

```bash
curl -k -u admin:password \
  -X PATCH \
  -H "Content-Type: application/json" \
  -d '{"Boot":{"BootSourceOverrideTarget":"Cd","BootSourceOverrideEnabled":"Once"}}' \
  https://192.168.1.100/redfish/v1/Systems/1/
```

Then reset the system.

---

## LDAP / Active Directory Integration

Centralizing authentication via LDAP eliminates local account sprawl and ties BMC access to your existing identity management.

### Configure LDAP

```bash
curl -k -u admin:password \
  -X PATCH \
  -H "Content-Type: application/json" \
  -d '{
    "LDAP": {
      "ServiceEnabled": true,
      "ServiceAddresses": ["ldap://dc1.example.com", "ldap://dc2.example.com"],
      "Authentication": {
        "AuthenticationType": "UsernameAndPassword",
        "Username": "cn=redfish-bind,ou=service,dc=example,dc=com",
        "Password": "bindpassword"
      },
      "LDAPService": {
        "SearchSettings": {
          "BaseDistinguishedNames": ["ou=users,dc=example,dc=com"],
          "UsernameAttribute": "sAMAccountName",
          "GroupsAttribute": "memberOf"
        }
      },
      "RemoteRoleMapping": [
        {
          "LocalRole": "Administrator",
          "RemoteGroup": "CN=bmc-admins,OU=Groups,DC=example,DC=com"
        },
        {
          "LocalRole": "Operator",
          "RemoteGroup": "CN=bmc-operators,OU=Groups,DC=example,DC=com"
        },
        {
          "LocalRole": "ReadOnly",
          "RemoteGroup": "CN=bmc-readonly,OU=Groups,DC=example,DC=com"
        }
      ]
    }
  }' \
  https://192.168.1.100/redfish/v1/AccountService/
```

---

## Automation and Fleet Management

### Discovering BMCs via DNS or DHCP

BMCs in a datacenter are typically reachable via predictable naming conventions:

```
bmc-<rack>-<unit>.mgmt.example.com
```

Or by querying a DHCP server for a specific vendor class or client ID. Build your host inventory from IPAM/CMDB records rather than scanning.

### Python Fleet Management Script Structure

```python
import redfish
import concurrent.futures
import csv

BMC_HOSTS = ["bmc-a1.mgmt.example.com", "bmc-a2.mgmt.example.com"]
CREDS = {"username": "admin", "password": "password"}

def collect(host):
    try:
        c = redfish.redfish_client(base_url=f"https://{host}", **CREDS)
        c.login(auth="session")
        s = c.get("/redfish/v1/Systems/1/").dict
        result = {
            "host": host,
            "serial": s.get("SerialNumber"),
            "model": s.get("Model"),
            "bios": s.get("BiosVersion"),
            "health": s.get("Status", {}).get("Health"),
            "power": s.get("PowerState"),
        }
        c.logout()
        return result
    except Exception as exc:
        return {"host": host, "error": str(exc)}

with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
    results = list(pool.map(collect, BMC_HOSTS))

writer = csv.DictWriter(open("inventory.csv", "w"), fieldnames=["host","serial","model","bios","health","power","error"])
writer.writeheader()
writer.writerows(results)
```

### Idempotent Configuration Checks

Before applying a configuration change, check whether it's already correct to avoid unnecessary BMC restarts:

```python
def ensure_protocol_disabled(client, protocol_name):
    protocols = client.get("/redfish/v1/Managers/1/NetworkProtocol/").dict
    if protocols.get(protocol_name, {}).get("ProtocolEnabled", False):
        client.patch(
            "/redfish/v1/Managers/1/NetworkProtocol/",
            body={protocol_name: {"ProtocolEnabled": False}}
        )
        print(f"Disabled {protocol_name}")
    else:
        print(f"{protocol_name} already disabled")
```

---

## Security Hardening Checklist

Apply these controls to every BMC before putting it into production.

### Authentication and Accounts

- [ ] Change all vendor default passwords immediately (especially `admin`, `ADMIN`, `root`, `Administrator`)
- [ ] Delete or disable unused built-in accounts
- [ ] Set `MinPasswordLength` to 12 or more
- [ ] Enable account lockout (`AccountLockoutThreshold` ≤ 10)
- [ ] Enable LDAP/AD integration and use local accounts only as break-glass
- [ ] Rotate service account passwords on a schedule (or use vault integration)

### Network

- [ ] Place BMC on a dedicated out-of-band management network, isolated from production
- [ ] Apply ACLs / firewall rules: only authorized management hosts can reach BMC port 443
- [ ] Disable IPMI-over-LAN (UDP 623) unless required by legacy tools
- [ ] Disable SNMP unless actively used (and use SNMPv3 with auth+priv if enabled)
- [ ] Disable Telnet, rlogin, and plaintext HTTP
- [ ] Assign a static IP or a DHCP reservation; avoid DHCP without reservation (IP churn)

### TLS / Certificates

- [ ] Replace self-signed certificates with CA-signed certificates before production
- [ ] Enforce TLS 1.2+ (disable TLS 1.0, 1.1, SSL 3.0)
- [ ] Distribute the internal CA bundle to all management hosts and automation tooling
- [ ] Set certificate expiry alerts (certificates commonly expire silently on BMCs)

### Firmware

- [ ] Update BMC firmware to the latest stable release before provisioning
- [ ] Update BIOS/UEFI to the latest stable release
- [ ] Subscribe to vendor security advisories for BMC CVEs
- [ ] Establish a firmware patching cadence (quarterly minimum)

### Logging and Auditing

- [ ] Forward BMC system event logs to a central syslog / SIEM
- [ ] Enable audit logging if supported by the vendor
- [ ] Set up Redfish event subscriptions to forward critical alerts to your monitoring stack
- [ ] Retain BMC logs for at least 90 days

### Physical Security

- [ ] Ensure BMC NIC port is patched into the OOB management switch, not a general-purpose switch
- [ ] Disable BMC access from the host OS side-channel (IPMI KCS/SSIF) if not needed
- [ ] Enable Secure Boot on the host if the workload supports it

---

## Monitoring Integration

### Prometheus / Alertmanager Integration

Run a Redfish exporter (e.g., `redfish_exporter`) as a sidecar or central scrape target:

```yaml
# prometheus.yml snippet
scrape_configs:
  - job_name: 'redfish'
    static_configs:
      - targets:
          - bmc-a1.mgmt.example.com
          - bmc-a2.mgmt.example.com
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - target_label: __address__
        replacement: redfish-exporter:9610
```

### Webhook Event Receiver (Python Flask Example)

```python
from flask import Flask, request, jsonify
import logging

app = Flask(__name__)

@app.route("/redfish-events", methods=["POST"])
def receive_event():
    payload = request.get_json()
    for event in payload.get("Events", []):
        severity = event.get("Severity", "Unknown")
        message = event.get("Message", "")
        origin = event.get("OriginOfCondition", {}).get("@odata.id", "unknown")
        logging.warning(f"[{severity}] {origin}: {message}")
        # Forward to PagerDuty, Slack, etc.
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=443, ssl_context=("cert.pem", "key.pem"))
```

---

## Troubleshooting BMC Issues

### BMC is Unresponsive Over Network

1. Verify physical connectivity to the OOB management port
2. Confirm correct VLAN tagging on the management switch port
3. Ping the BMC IP from a known-good host on the same management VLAN
4. If unreachable, try connecting via the host OS IPMI interface:
   ```bash
   ipmitool -I open bmc info   # from the host OS
   ```
5. As a last resort, perform a BMC reset via the physical jumper (vendor-specific; see hardware manual)

### BMC Firmware Upgrade Stuck / Failed

1. Do NOT power off the host during a BMC update
2. Check the Task resource for error messages
3. BMC will typically auto-recover from a failed update (dual-bank firmware)
4. If the BMC is unresponsive after a failed update, consult the vendor's recovery procedure (often involves a USB flash drive with recovery firmware)

### Redfish Returns 503 Service Unavailable

The BMC may be busy initializing after a reset or under high load. Wait 2–5 minutes and retry. Check whether another management session or heavy polling is consuming all BMC resources.

### Time Sync Issues (Log Timestamps Wrong)

```bash
# Check current NTP config
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Managers/1/NetworkProtocol/ | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['NTP'])"

# Reconfigure NTP
curl -k -u admin:password \
  -X PATCH \
  -H "Content-Type: application/json" \
  -d '{"NTP": {"ProtocolEnabled": true, "NTPServers": ["pool.ntp.org"]}}' \
  https://192.168.1.100/redfish/v1/Managers/1/NetworkProtocol/
```

### Certificate Errors in Automation

Distribute the internal CA to the automation host:

```bash
# Add CA to system trust store (RHEL/CentOS)
cp internal-ca.pem /etc/pki/ca-trust/source/anchors/
update-ca-trust

# Add CA to system trust store (Debian/Ubuntu)
cp internal-ca.pem /usr/local/share/ca-certificates/internal-ca.crt
update-ca-certificates

# Use with Python requests
import requests
response = requests.get("https://bmc-host/redfish/v1/", verify="/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem")
```

---

## Vendor-Specific Notes

### Dell iDRAC

- iDRAC 9 firmware 3.00+ provides comprehensive Redfish v1.x support
- Redfish is the preferred management path; WSMAN is legacy
- Dell's `python-redfish-library` extensions provide iDRAC-specific capabilities
- iDRAC Group Manager can manage up to 100 iDRAC instances from a single pane

### HPE iLO 5 / iLO 6

- iLO 5 introduced full Redfish; iLO RESTful API is built on Redfish
- HPE's `python-ilorest-library` wraps the standard Redfish client with iLO extensions
- iLO Amplifier Pack provides fleet Redfish management for HPE estates

### OpenBMC

- Used by hyperscale operators (Meta, Google) and increasingly by ODM server vendors
- Full open-source; Redfish implementation is `phosphor-bmc-code-mgmt` + `bmcweb`
- Firmware images are provided per-platform; no universal update mechanism
- API keys are the preferred authentication method in many OpenBMC deployments

### Supermicro

- Redfish support quality varies by BMC generation (X11 vs X12 vs H12)
- Some older X11 systems have incomplete Redfish; fall back to IPMI for those
- Use `sum` (Supermicro Update Manager) for firmware updates on older platforms

---

## Reference: Common HTTP Status Codes

| Code | Meaning in Redfish Context |
|------|---------------------------|
| 200 OK | Successful GET; response body contains the resource |
| 201 Created | Successful POST that created a new resource; `Location` header has the URI |
| 202 Accepted | Async operation started; `Location` header points to a Task |
| 204 No Content | Successful PATCH/DELETE with no response body |
| 400 Bad Request | Malformed JSON or invalid property values |
| 401 Unauthorized | Missing or invalid credentials |
| 403 Forbidden | Authenticated but insufficient privilege |
| 404 Not Found | URI does not exist on this implementation |
| 405 Method Not Allowed | HTTP verb not supported on this resource |
| 409 Conflict | State conflict (e.g., trying to power on an already-on system) |
| 500 Internal Server Error | BMC-side error; retry after a delay |
| 501 Not Implemented | Feature exists in the spec but not in this implementation |
| 503 Service Unavailable | BMC temporarily busy or overloaded |
