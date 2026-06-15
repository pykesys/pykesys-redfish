# Admin Guide — pykesys-redfish

This guide covers deployment, configuration, and operational responsibilities for administrators of this stack: standing up the web app, managing BMC hosts and alert rules, securing the environment, and operating the underlying BMC infrastructure.

See [guide-users.md](guide-users.md) for day-to-day user operations and [redfish.md](redfish.md) for Redfish protocol background.

## Table of Contents

- [Web App Deployment](#web-app-deployment)
  - [Environment variables](#environment-variables)
  - [Local development](#local-development)
  - [Production deployment](#production-deployment)
  - [Docker Compose deployment](#docker-compose-deployment)
- [Django Admin Interface](#django-admin-interface)
- [Managing BMC Hosts](#managing-bmc-hosts)
  - [Adding hosts](#adding-hosts)
  - [Poll interval configuration](#poll-interval-configuration)
  - [Enabling and disabling hosts](#enabling-and-disabling-hosts)
- [Alert Rules Configuration](#alert-rules-configuration)
  - [Creating rules](#creating-rules)
  - [Rule conditions](#rule-conditions)
  - [Slack notifications](#slack-notifications)
  - [Managing events](#managing-events)
- [APScheduler Polling](#apscheduler-polling)
  - [How polling works](#how-polling-works)
  - [Scheduler configuration](#scheduler-configuration)
  - [Manual poll trigger](#manual-poll-trigger)
- [Database Management](#database-management)
- [Initial BMC Setup](#initial-bmc-setup)
- [Network Configuration](#network-configuration)
- [Protocol Management](#protocol-management)
- [Account and Role Management](#account-and-role-management)
- [TLS Certificate Management](#tls-certificate-management)
- [Firmware and BIOS Updates](#firmware-and-bios-updates)
- [BMC Reset and Factory Reset](#bmc-reset-and-factory-reset)
- [Virtual Media](#virtual-media)
- [LDAP / Active Directory Integration](#ldap--active-directory-integration)
- [Fleet Automation with the SDK](#fleet-automation-with-the-sdk)
- [Security Hardening Checklist](#security-hardening-checklist)
- [Monitoring Integration](#monitoring-integration)
- [Troubleshooting](#troubleshooting)
- [Vendor-Specific Notes](#vendor-specific-notes)
- [HTTP Status Code Reference](#http-status-code-reference)

---

## Web App Deployment

The web observability layer consists of:

- **`redfish_web/`** — Django 4.x + Django REST Framework backend, APScheduler background polling, SQLite database
- **`frontend/`** — React 18 + Vite SPA (served as static files from Django in production)
- **`emulator/`** — Optional FastAPI emulator for development/testing

### Environment variables

| Variable | Default | Required in prod | Description |
|----------|---------|-----------------|-------------|
| `DJANGO_SECRET_KEY` | `dev-secret-key-change-in-production` | **Yes** | Django secret key — generate with `openssl rand -hex 50` |
| `DEBUG` | `true` | **Set to `false`** | Disables debug mode, enables production error handling |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | **Yes** | Comma-separated hostnames that Django will serve |
| `EMULATOR_URL` | *(none)* | No | If set, `init_emulator_hosts` registers emulator nodes on startup |
| `EMULATOR_NUM_NODES` | `10` | No | Number of emulator nodes to register on startup |
| `EMULATOR_ADMIN_USER` | `admin` | No | Emulator admin username |
| `EMULATOR_ADMIN_PASS` | `redfish` | No | Emulator admin password |

Set these before starting the application or via Docker Compose environment:

```bash
export DJANGO_SECRET_KEY="$(openssl rand -hex 50)"
export DEBUG=false
export ALLOWED_HOSTS="redfish-mgmt.example.com,10.0.0.50"
```

### Local development

```bash
# Option 1: interactive dashboard (recommended)
./run-dashboard.sh dev         # Django dev server on :8000
./run-dashboard.sh frontend    # Vite dev server on :5173 (proxy → :8000)
./run-dashboard.sh emulator    # Redfish emulator on :8888

# Option 2: all services in background
./run-dashboard.sh all

# Option 3: manual
cd redfish_web
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

The React dev server proxies `/api/` requests to Django. In development, the SPA is served by Vite at `:5173`; in production it is built and served as Django static files.

### Production deployment

```bash
# 1. Build the React SPA
cd frontend
npm install
npm run build
# Output lands in frontend/dist/

# 2. Copy the SPA bundle into Django's template/static directory
# (docker-compose.yml handles this automatically via build volumes)
cp -r frontend/dist/* redfish_web/staticfiles/  # adjust to your setup

# 3. Set environment variables (see above)
export DJANGO_SECRET_KEY="..."
export DEBUG=false
export ALLOWED_HOSTS="your-hostname"

# 4. Run migrations and collect static
cd redfish_web
python manage.py migrate --no-input
python manage.py collectstatic --no-input

# 5. Start gunicorn via run.sh
cd ..
./run.sh
```

`run.sh` runs migrations and static collection automatically before binding — see [run-sh.md](run-sh.md).

### Docker Compose deployment

```bash
# Full stack: emulator + Django web app
docker compose up

# Background
docker compose up -d

# Rebuild after code changes
docker compose up --build

# View logs
docker compose logs -f web
docker compose logs -f emulator

# Stop
docker compose down
```

The web app container runs at `http://localhost:8000`. The emulator runs at `http://localhost:8888`. On startup, the web app auto-registers 10 emulator nodes as `BMCHost` records (controlled by `EMULATOR_URL` and `EMULATOR_NUM_NODES`).

For CI with integration tests:

```bash
docker compose -f docker-compose.ci.yml up \
  --abort-on-container-exit \
  --exit-code-from tests
```

[↑ Back to Top](#table-of-contents)

---

## Django Admin Interface

Django's built-in admin is available at `/admin/`. Create a superuser to access it:

```bash
cd redfish_web
python manage.py createsuperuser
```

The admin provides full CRUD access to all models:

| Model | Admin path | Use for |
|-------|-----------|---------|
| `BMCHost` | `/admin/hosts/bmchost/` | Add, edit, enable/disable hosts; view last_error and last_seen |
| `InventorySnapshot` | `/admin/inventory/inventorysnapshot/` | Browse historical snapshots |
| `SensorReading` | `/admin/inventory/sensorreading/` | Browse raw sensor data |
| `LogEntry` | `/admin/inventory/logentry/` | Browse stored SEL entries |
| `AlertRule` | `/admin/alerts/alertrule/` | Create and manage alert rules |
| `AlertEvent` | `/admin/alerts/alertevent/` | View open and resolved events |
| `DjangoJobExecution` | `/admin/django_apscheduler/djangojobexecution/` | APScheduler job history |

[↑ Back to Top](#table-of-contents)

---

## Managing BMC Hosts

### Adding hosts

**Via REST API:**

```bash
curl -X POST http://localhost:8000/api/hosts/ \
  -H "Content-Type: application/json" \
  -d '{
    "host": "bmc-dgx-01.mgmt",
    "display_name": "DGX Node 01",
    "username": "admin",
    "password": "secret",
    "verify_ssl": false,
    "poll_interval": 60,
    "enabled": true,
    "tags": ["dgx", "rack-a", "gpu"]
  }'
```

`host` accepts either a bare hostname/IP (HTTPS is assumed: `https://bmc-dgx-01.mgmt`) or a full URL (including scheme and path prefix for emulator nodes: `http://localhost:8888/bmc/1`).

**Via Django admin:** Go to `/admin/hosts/bmchost/add/` and fill in the form.

**Bulk registration (SDK script):**

```python
import requests

hosts = [
    {"host": f"bmc-dgx-{i:02d}.mgmt", "display_name": f"DGX Node {i:02d}",
     "username": "admin", "password": "secret", "poll_interval": 60, "verify_ssl": False}
    for i in range(1, 11)
]

for h in hosts:
    r = requests.post("http://localhost:8000/api/hosts/", json=h)
    r.raise_for_status()
    print(f"Registered {h['host']} → id={r.json()['id']}")
```

### Poll interval configuration

`poll_interval` is per-host and measured in seconds. The scheduler runs every 30 seconds and polls any host whose `last_seen + poll_interval ≤ now`.

| Use case | Recommended interval |
|----------|---------------------|
| Active monitoring / alerting | 30–60 s |
| Standard inventory collection | 120–300 s |
| Power-state-only health check | 60 s |
| Low-priority / test nodes | 600 s |

Change the interval via PATCH:

```bash
curl -X PATCH http://localhost:8000/api/hosts/1/ \
  -H "Content-Type: application/json" \
  -d '{"poll_interval": 120}'
```

### Enabling and disabling hosts

The scheduler only polls hosts where `enabled=true`. Disabling a host stops polling without deleting its historical data.

```bash
# Disable
curl -X PATCH http://localhost:8000/api/hosts/1/ \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'

# Re-enable
curl -X PATCH http://localhost:8000/api/hosts/1/ \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

[↑ Back to Top](#table-of-contents)

---

## Alert Rules Configuration

Alert rules evaluate freshly stored `InventorySnapshot` values after each poll cycle. When a rule matches, an `AlertEvent` is created and an optional Slack notification is sent.

### Creating rules

**Via REST API:**

```bash
# Alert when health is Critical
curl -X POST http://localhost:8000/api/alerts/rules/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Critical Health",
    "field": "health",
    "operator": "eq",
    "value": "Critical",
    "severity": "critical",
    "enabled": true,
    "notify_slack_webhook": "https://hooks.slack.com/services/T.../B.../xxx"
  }'

# Alert when health is not OK
curl -X POST http://localhost:8000/api/alerts/rules/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Degraded Health",
    "field": "health",
    "operator": "neq",
    "value": "OK",
    "severity": "warning",
    "enabled": true
  }'

# Alert when power state is Off
curl -X POST http://localhost:8000/api/alerts/rules/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Node Powered Off",
    "field": "power_state",
    "operator": "eq",
    "value": "Off",
    "severity": "warning",
    "enabled": true,
    "notify_slack_webhook": "https://hooks.slack.com/services/..."
  }'
```

**Via Django admin:** Go to `/admin/alerts/alertrule/add/`.

### Rule conditions

| Field | `field` value | Evaluable values |
|-------|--------------|-----------------|
| Health status | `health` | `OK`, `Warning`, `Critical` |
| Power state | `power_state` | `On`, `Off`, `PoweringOn`, `PoweringOff` |

| Operator | `operator` value | Matches when |
|----------|-----------------|-------------|
| Equals | `eq` | snapshot field == rule value |
| Not equals | `neq` | snapshot field != rule value |

Rules evaluate to `False` (no alert) when the snapshot field is null or empty — a host that errors out during polling does not trigger health alerts.

### Slack notifications

Set `notify_slack_webhook` to a Slack Incoming Webhook URL. The webhook receives a message in this format:

```
[CRITICAL] Critical Health — bmc-dgx-03.mgmt: health is Critical (rule: health eq Critical)
```

Webhook calls are fire-and-forget. Failed calls log a warning but do not affect the alert event creation.

To test a webhook:

```bash
curl -X POST https://hooks.slack.com/services/T.../B.../xxx \
  -H "Content-Type: application/json" \
  -d '{"text": "Test alert from pykesys-redfish"}'
```

### Managing events

Open events auto-resolve when the rule condition is no longer true on the next poll. You can also resolve manually:

```bash
# List open events
curl "http://localhost:8000/api/alerts/events/?open=true"

# Resolve an event (sets resolved_at to now)
curl -X POST http://localhost:8000/api/alerts/events/7/resolve/

# Events for a specific host
curl "http://localhost:8000/api/alerts/events/?host=3"
```

[↑ Back to Top](#table-of-contents)

---

## APScheduler Polling

### How polling works

1. `SchedulerConfig.ready()` (in `scheduler/apps.py`) starts a `BackgroundScheduler` with a 30-second `IntervalTrigger` when Django starts.
2. Every 30 seconds, `run_poll_cycle()` queries all `enabled=True` BMCHost records.
3. For each host, it checks whether `last_seen + poll_interval ≤ now`. If so, it calls `poll_host(host)`.
4. `poll_host()` creates a `RedfishClient`, fetches the system summary, stores an `InventorySnapshot`, stores thermal sensors and SEL entries, then calls `evaluate_rules(snapshot)`.
5. On failure, `last_seen` is updated (with the error timestamp) so the host respects its `poll_interval` between retry attempts.
6. After each successful poll, `evaluate_rules()` checks all enabled `AlertRule` objects against the new snapshot.

### Scheduler configuration

| Django setting | Default | Description |
|----------------|---------|-------------|
| `SCHEDULER_AUTOSTART` | `True` | Start scheduler automatically on Django startup |
| `APSCHEDULER_DATETIME_FORMAT` | `"N j, Y, f:s a"` | Timestamp format in admin |
| `APSCHEDULER_RUN_NOW_TIMEOUT` | `25` | Seconds to wait for an immediate job run |

The scheduler only starts in the reloader process (guarded by `RUN_MAIN` in dev mode) to avoid double-start in Django's dev server auto-reloader.

To disable automatic polling (e.g., for a worker that only serves the API):

```python
# In settings.py or via environment
SCHEDULER_AUTOSTART = False
```

### Manual poll trigger

Trigger an immediate out-of-cycle poll via the REST API:

```bash
curl -X POST http://localhost:8000/api/hosts/1/poll/
# Response: {"status": "polled", "snapshot_id": 42}
# On error: {"error": "Connection refused"} with HTTP 502
```

[↑ Back to Top](#table-of-contents)

---

## Database Management

The web app uses SQLite by default (`redfish_web/db.sqlite3`). This is fine for a single-server deployment managing a SuperPod-scale fleet.

### Migrations

```bash
cd redfish_web
python manage.py migrate              # apply pending migrations
python manage.py showmigrations       # list migration state
```

### Backup

```bash
# SQLite backup (safe to copy while running)
cp redfish_web/db.sqlite3 backups/db-$(date +%Y%m%d-%H%M%S).sqlite3
```

### Trimming old snapshots

Snapshots accumulate over time. Consider a periodic cleanup:

```python
# In Django shell: delete snapshots older than 30 days
from django.utils import timezone
from datetime import timedelta
from inventory.models import InventorySnapshot

cutoff = timezone.now() - timedelta(days=30)
count, _ = InventorySnapshot.objects.filter(polled_at__lt=cutoff).delete()
print(f"Deleted {count} snapshots")
```

Or set up a management command to run this on a cron schedule.

[↑ Back to Top](#table-of-contents)

---

## Initial BMC Setup

Before a server can be managed via Redfish, the BMC requires initial configuration. This is typically done via physical console (BIOS setup), vendor-specific tools, or a pre-provisioning script run from the OS side.

### Required initial steps

1. Assign a static IP or configure DHCP reservation for the BMC NIC
2. Change the vendor default password immediately (defaults are well-known and publicly documented)
3. Enable HTTPS; disable plain HTTP
4. Disable unused protocols: IPMI-over-LAN, SNMP, Telnet unless explicitly required
5. Import or generate a trusted TLS certificate
6. Configure NTP for accurate log timestamps

[↑ Back to Top](#table-of-contents)

---

## Network Configuration

BMC network settings live under the Manager resource.

### View BMC network interfaces

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Managers/1/EthernetInterfaces/
```

### View a specific interface

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Managers/1/EthernetInterfaces/NIC1/
```

Key fields: `IPv4Addresses`, `MACAddress`, `DHCPv4.DHCPEnabled`, `FQDN`.

### Set a static IP address

```bash
curl -k -u admin:password -X PATCH -H "Content-Type: application/json" \
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

Network changes may require a BMC reset: `POST /redfish/v1/Managers/1/Actions/Manager.Reset` with `{"ResetType":"GracefulRestart"}`.

### Configure DNS

```bash
curl -k -u admin:password -X PATCH -H "Content-Type: application/json" \
  -d '{"NameServers": ["10.0.0.53","10.0.0.54"], "FQDN": "bmc-dgx-01.mgmt.example.com"}' \
  https://192.168.1.100/redfish/v1/Managers/1/EthernetInterfaces/NIC1/
```

[↑ Back to Top](#table-of-contents)

---

## Protocol Management

### View protocol settings

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Managers/1/NetworkProtocol/
```

### Disable IPMI-over-LAN

IPMI-over-LAN (UDP 623) has known security issues (RAKP vulnerability, weak authentication). Disable it unless required by legacy tooling.

```bash
curl -k -u admin:password -X PATCH -H "Content-Type: application/json" \
  -d '{"IPMI": {"ProtocolEnabled": false}}' \
  https://192.168.1.100/redfish/v1/Managers/1/NetworkProtocol/
```

### Disable SNMP

```bash
curl -k -u admin:password -X PATCH -H "Content-Type: application/json" \
  -d '{"SNMP": {"ProtocolEnabled": false}}' \
  https://192.168.1.100/redfish/v1/Managers/1/NetworkProtocol/
```

### Enforce HTTPS only

```bash
curl -k -u admin:password -X PATCH -H "Content-Type: application/json" \
  -d '{"HTTP": {"ProtocolEnabled": false}, "HTTPS": {"ProtocolEnabled": true, "Port": 443}}' \
  https://192.168.1.100/redfish/v1/Managers/1/NetworkProtocol/
```

### Configure NTP

```bash
curl -k -u admin:password -X PATCH -H "Content-Type: application/json" \
  -d '{"NTP": {"ProtocolEnabled": true, "NTPServers": ["ntp1.example.com","ntp2.example.com"]}}' \
  https://192.168.1.100/redfish/v1/Managers/1/NetworkProtocol/
```

Or via the SDK:

```python
with RedfishClient("https://bmc", "admin", "pass") as rf:
    rf.manager().set_ntp_servers(["ntp1.example.com", "ntp2.example.com"])
    rf.manager().set_protocol_enabled("IPMI", False)
    rf.manager().set_protocol_enabled("SNMP", False)
```

[↑ Back to Top](#table-of-contents)

---

## Account and Role Management

Redfish enforces role-based access control. Accounts are managed under `AccountService`.

### View account service settings

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/AccountService/
```

Key settings: `MinPasswordLength`, `AccountLockoutThreshold`, `AccountLockoutDuration`.

### List accounts

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/AccountService/Accounts/
```

### Create a user account

```bash
curl -k -u admin:password -X POST -H "Content-Type: application/json" \
  -d '{"UserName":"operator1","Password":"SecureP@ss123!","RoleId":"Operator","Enabled":true}' \
  https://192.168.1.100/redfish/v1/AccountService/Accounts/
```

### Built-in Redfish roles

| RoleId | Privileges |
|--------|-----------|
| `Administrator` | Full read/write, account management, configuration changes |
| `Operator` | Power, boot, log access; no account management |
| `ReadOnly` | Read-only access; no write operations |

### Modify an account

```bash
# Change password
curl -k -u admin:password -X PATCH -H "Content-Type: application/json" \
  -d '{"Password": "NewSecureP@ss456!"}' \
  https://192.168.1.100/redfish/v1/AccountService/Accounts/2

# Disable without deleting
curl -k -u admin:password -X PATCH -H "Content-Type: application/json" \
  -d '{"Enabled": false}' \
  https://192.168.1.100/redfish/v1/AccountService/Accounts/2

# Delete
curl -k -u admin:password -X DELETE \
  https://192.168.1.100/redfish/v1/AccountService/Accounts/2
```

### Configure lockout policy

```bash
curl -k -u admin:password -X PATCH -H "Content-Type: application/json" \
  -d '{
    "AccountLockoutThreshold": 5,
    "AccountLockoutDuration": 300,
    "AccountLockoutCounterResetAfter": 120
  }' \
  https://192.168.1.100/redfish/v1/AccountService/
```

Locks account for 300 seconds after 5 failed attempts; failure counter resets after 120 seconds of no attempts.

SDK equivalent:

```python
with RedfishClient("https://bmc", "admin", "pass") as rf:
    rf.account_service().set_lockout_policy(threshold=5, duration=300, reset_after=120)
```

[↑ Back to Top](#table-of-contents)

---

## TLS Certificate Management

### View current certificate

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Managers/1/NetworkProtocol/HTTPS/Certificates/
```

### Replace the self-signed certificate

1. Generate a CSR from the BMC (vendor-specific; some support `CertificateService.GenerateCSR`)
2. Sign with your internal CA
3. Import the signed certificate:

```bash
curl -k -u admin:password -X POST -H "Content-Type: application/json" \
  -d '{
    "CertificateType": "PEM",
    "CertificateString": "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----\n-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
  }' \
  https://192.168.1.100/redfish/v1/Managers/1/NetworkProtocol/HTTPS/Certificates/
```

Distribute the internal CA certificate to all management hosts and automation tooling:

```bash
# RHEL / CentOS
cp internal-ca.pem /etc/pki/ca-trust/source/anchors/
update-ca-trust

# Debian / Ubuntu
cp internal-ca.pem /usr/local/share/ca-certificates/internal-ca.crt
update-ca-certificates
```

[↑ Back to Top](#table-of-contents)

---

## Firmware and BIOS Updates

### Check firmware inventory

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/UpdateService/FirmwareInventory/
```

Lists all components: BMC, BIOS, NIC, HBA, PSU, CPLD. Each entry shows `Version` and `Updateable`.

### SimpleUpdate from HTTPS URI

```bash
curl -k -u admin:password -X POST -H "Content-Type: application/json" \
  -d '{
    "TransferProtocol": "HTTPS",
    "ImageURI": "https://firmware-server.example.com/bios-2.1.0.bin",
    "Targets": ["/redfish/v1/UpdateService/FirmwareInventory/BIOS"]
  }' \
  https://192.168.1.100/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate
```

Via CLI:

```bash
uv run rf firmware update https://firmware-server.example.com/bios-2.1.0.bin \
  --target /redfish/v1/UpdateService/FirmwareInventory/BIOS
```

### Multipart push update (direct binary upload)

```bash
curl -k -u admin:password -X POST \
  -H "Content-Type: multipart/form-data" \
  -F "UpdateParameters={\"Targets\":[\"/redfish/v1/UpdateService/FirmwareInventory/BMC\"]};type=application/json" \
  -F "UpdateFile=@/tmp/bmc-4.5.0.bin;type=application/octet-stream" \
  https://192.168.1.100/redfish/v1/UpdateService/
```

### Monitor update progress

Firmware updates return a task URI via the `Location` header:

```bash
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/TaskService/Tasks/1/
```

Poll until `TaskState` is `Completed` or `Exception`. Fields: `TaskState`, `TaskStatus`, `PercentComplete`, `Messages`.

### BIOS settings

```bash
# Read BIOS attributes
curl -k -u admin:password https://192.168.1.100/redfish/v1/Systems/1/Bios/

# Stage BIOS attribute changes (applied on next reboot)
curl -k -u admin:password -X PATCH -H "Content-Type: application/json" \
  -d '{"Attributes": {"ProcHyperthreading": "Disabled", "SriovGlobalEnable": "Enabled"}}' \
  https://192.168.1.100/redfish/v1/Systems/1/Bios/Settings/

# Reset BIOS to factory defaults
curl -k -u admin:password -X POST -H "Content-Type: application/json" -d '{}' \
  https://192.168.1.100/redfish/v1/Systems/1/Bios/Actions/Bios.ResetBios
```

[↑ Back to Top](#table-of-contents)

---

## BMC Reset and Factory Reset

### Graceful BMC reset

Reboots the BMC firmware without affecting the host OS. Required after some network configuration changes.

```bash
curl -k -u admin:password -X POST -H "Content-Type: application/json" \
  -d '{"ResetType": "GracefulRestart"}' \
  https://192.168.1.100/redfish/v1/Managers/1/Actions/Manager.Reset
```

SDK:

```python
rf.manager().reset()  # GracefulRestart default
```

### Factory reset

Erases all BMC configuration. **Use only when decommissioning or re-provisioning.**

```bash
curl -k -u admin:password -X POST -H "Content-Type: application/json" \
  -d '{"ResetToDefaultsType": "ResetAll"}' \
  https://192.168.1.100/redfish/v1/Managers/1/Actions/Manager.ResetToDefaults
```

[↑ Back to Top](#table-of-contents)

---

## Virtual Media

Mount ISO images from a remote HTTPS server for OS installation or recovery.

### Mount a remote ISO

```bash
curl -k -u admin:password -X POST -H "Content-Type: application/json" \
  -d '{
    "Image": "https://os-server.example.com/images/rhel9.iso",
    "MediaTypes": ["DVD"],
    "TransferMethod": "Stream",
    "Inserted": true,
    "WriteProtected": true
  }' \
  https://192.168.1.100/redfish/v1/Managers/1/VirtualMedia/CD1/Actions/VirtualMedia.InsertMedia
```

### Unmount virtual media

```bash
curl -k -u admin:password -X POST -H "Content-Type: application/json" -d '{}' \
  https://192.168.1.100/redfish/v1/Managers/1/VirtualMedia/CD1/Actions/VirtualMedia.EjectMedia
```

### Boot to virtual media (one-time)

```bash
# Set one-time CD boot
curl -k -u admin:password -X PATCH -H "Content-Type: application/json" \
  -d '{"Boot":{"BootSourceOverrideTarget":"Cd","BootSourceOverrideEnabled":"Once"}}' \
  https://192.168.1.100/redfish/v1/Systems/1/

# Then reset the system
curl -k -u admin:password -X POST -H "Content-Type: application/json" \
  -d '{"ResetType":"GracefulRestart"}' \
  https://192.168.1.100/redfish/v1/Systems/1/Actions/ComputerSystem.Reset
```

[↑ Back to Top](#table-of-contents)

---

## LDAP / Active Directory Integration

Centralizing authentication via LDAP eliminates local account sprawl.

```bash
curl -k -u admin:password -X PATCH -H "Content-Type: application/json" \
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
        {"LocalRole": "Administrator", "RemoteGroup": "CN=bmc-admins,OU=Groups,DC=example,DC=com"},
        {"LocalRole": "Operator",      "RemoteGroup": "CN=bmc-operators,OU=Groups,DC=example,DC=com"},
        {"LocalRole": "ReadOnly",       "RemoteGroup": "CN=bmc-readonly,OU=Groups,DC=example,DC=com"}
      ]
    }
  }' \
  https://192.168.1.100/redfish/v1/AccountService/
```

[↑ Back to Top](#table-of-contents)

---

## Fleet Automation with the SDK

Use `FleetManager` for bulk BMC operations. Each worker gets an isolated `RedfishClient` — no shared state between threads.

### Idempotent protocol hardening

```python
from pykesys_redfish import RedfishClient
from pykesys_redfish.fleet import FleetManager

def harden_bmc(rf: RedfishClient, host: str) -> dict:
    mgr = rf.manager()
    mgr.set_protocol_enabled("IPMI", False)
    mgr.set_protocol_enabled("SNMP", False)
    mgr.set_ntp_servers(["ntp1.corp.com", "ntp2.corp.com"])
    return {"host": host, "status": "hardened"}

fm = FleetManager(
    hosts=[f"bmc-dgx-{i:02d}.mgmt" for i in range(1, 11)],
    username="admin", password="password",
)
results = fm.run(harden_bmc)
for r in results:
    print(r["host"], r.get("status"), r.get("error", ""))
```

### Batch password rotation

```python
NEW_PASS = "RotatedP@ss2026!"

def rotate_password(rf: RedfishClient, host: str) -> dict:
    svc = rf.account_service()
    for acct in svc.accounts():
        if acct["UserName"] == "admin":
            svc.set_password(acct["@odata.id"], NEW_PASS)
            return {"host": host, "status": "rotated"}
    return {"host": host, "status": "admin account not found"}

fm.run(rotate_password)
```

### Firmware audit

```python
def firmware_audit(rf: RedfishClient, host: str) -> dict:
    data = rf.get("/redfish/v1/UpdateService/FirmwareInventory/")
    components = [rf.get(m["@odata.id"]) for m in data.get("Members", [])]
    return {"host": host, "firmware": {c["Id"]: c["Version"] for c in components}}

results = fm.run(firmware_audit)
for r in results:
    if "error" not in r:
        print(f"{r['host']}: {r['firmware']}")
```

[↑ Back to Top](#table-of-contents)

---

## Security Hardening Checklist

### Project web app

- [ ] Set `DJANGO_SECRET_KEY` to a strong random value — never use the default
- [ ] Set `DEBUG=false` in production
- [ ] Set `ALLOWED_HOSTS` to only the expected hostnames
- [ ] Run Django behind a reverse proxy (nginx/haproxy) with TLS termination
- [ ] BMC passwords are stored in plaintext in the database — restrict database access and encrypt at rest if required by policy
- [ ] Use Django admin only from the management network; consider disabling it in production if not needed

### Authentication and accounts

- [ ] Change all vendor default BMC passwords immediately
- [ ] Delete or disable unused built-in accounts
- [ ] Set `MinPasswordLength` ≥ 12
- [ ] Enable account lockout (`AccountLockoutThreshold` ≤ 10)
- [ ] Integrate LDAP/AD and use local accounts only as break-glass
- [ ] Rotate service account passwords on a schedule

### Network

- [ ] Place BMCs on a dedicated out-of-band management network, isolated from production
- [ ] ACL/firewall: only authorized management hosts can reach BMC port 443
- [ ] Disable IPMI-over-LAN (UDP 623)
- [ ] Disable SNMP unless actively used (SNMPv3 with auth+priv if enabled)
- [ ] Disable Telnet and plain HTTP
- [ ] Assign static IPs or DHCP reservations

### TLS / certificates

- [ ] Replace self-signed certs with CA-signed certs before production
- [ ] Enforce TLS 1.2+ (disable TLS 1.0, 1.1, SSL 3.0)
- [ ] Distribute the internal CA bundle to all management hosts
- [ ] Monitor certificate expiry — BMC certificates commonly expire silently

### Firmware

- [ ] Update BMC firmware to latest stable before provisioning
- [ ] Update BIOS/UEFI to latest stable
- [ ] Subscribe to vendor security advisories
- [ ] Establish a quarterly firmware patching cadence

### Logging and auditing

- [ ] Forward BMC SEL to a central syslog / SIEM
- [ ] Enable audit logging if supported by the vendor
- [ ] Configure Redfish event subscriptions to forward critical alerts to your monitoring stack
- [ ] Retain BMC logs for at least 90 days

### Physical security

- [ ] BMC NIC port patched into the OOB management switch, not a general-purpose switch
- [ ] Disable BMC OS side-channel (IPMI KCS/SSIF) if not needed
- [ ] Enable Secure Boot on the host if the workload supports it

[↑ Back to Top](#table-of-contents)

---

## Monitoring Integration

### Using the web app's REST API as a data source

```python
import requests

# Fleet health summary from the web app
fleet = requests.get("http://localhost:8000/api/fleet/").json()
for host in fleet:
    snap = host.get("latest_snapshot")
    if snap:
        print(f"{host['display_name']:30s}  {snap['power_state']:12s}  {snap['health']}")
```

### Prometheus / redfish_exporter

Run a `redfish_exporter` sidecar pointing at each BMC for metrics scraping:

```yaml
# prometheus.yml snippet
scrape_configs:
  - job_name: redfish
    static_configs:
      - targets:
          - bmc-dgx-01.mgmt
          - bmc-dgx-02.mgmt
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - target_label: __address__
        replacement: redfish-exporter:9610
```

### Redfish event webhook receiver

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
        logging.warning("[%s] %s: %s", severity, origin, message)
        # Forward to PagerDuty, Slack, OpsGenie, etc.
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=443, ssl_context=("cert.pem", "key.pem"))
```

[↑ Back to Top](#table-of-contents)

---

## Troubleshooting

### BMC unreachable over network

1. Verify physical connectivity to the OOB management port
2. Confirm VLAN tagging on the management switch port
3. Ping the BMC IP from a host on the same management VLAN
4. Try connecting via the host OS IPMI interface: `ipmitool -I open bmc info`
5. As a last resort, reset via the physical jumper (vendor-specific; see hardware manual)

### Firmware upgrade stuck / failed

1. Do NOT power off the host during a BMC update
2. Check the Task resource for error messages
3. BMC typically auto-recovers from a failed update (dual-bank firmware)
4. If unresponsive after a failed update, consult the vendor recovery procedure (usually a USB flash drive with recovery firmware)

### 503 Service Unavailable

The BMC may be busy initializing after a reset or under heavy load. Wait 2–5 minutes and retry. Check whether heavy polling is consuming BMC resources.

### Time sync issues (wrong log timestamps)

```bash
# Check current NTP
curl -k -u admin:password \
  https://192.168.1.100/redfish/v1/Managers/1/NetworkProtocol/ \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['NTP'])"

# Reconfigure NTP
curl -k -u admin:password -X PATCH -H "Content-Type: application/json" \
  -d '{"NTP": {"ProtocolEnabled": true, "NTPServers": ["pool.ntp.org"]}}' \
  https://192.168.1.100/redfish/v1/Managers/1/NetworkProtocol/
```

### Web app shows `last_error` for a host

Check the error message:

```bash
curl http://localhost:8000/api/hosts/1/ | python3 -c "import sys,json; print(json.load(sys.stdin)['last_error'])"
```

Common causes and fixes:

| Error | Fix |
|-------|-----|
| `Connection refused` | BMC unreachable — check network and BMC status |
| `RedfishAuthError` | Wrong credentials — update `username`/`password` on the host record |
| `SSL: CERTIFICATE_VERIFY_FAILED` | Set `verify_ssl: false` on the host, or distribute the BMC CA cert |
| `RedfishTimeoutError` | BMC slow/busy — increase `timeout` or reduce poll frequency |

[↑ Back to Top](#table-of-contents)

---

## Vendor-Specific Notes

### Dell iDRAC

- iDRAC 9 firmware 3.00+ provides comprehensive Redfish v1.x support
- Redfish is the preferred management path; WSMAN is legacy
- iDRAC Group Manager can manage up to 100 iDRAC instances from a single pane

### HPE iLO 5 / iLO 6

- iLO 5 introduced full Redfish; the iLO RESTful API is built on Redfish
- iLO Amplifier Pack provides fleet Redfish management for HPE estates

### OpenBMC

- Used by hyperscale operators and increasingly by ODM vendors
- Full open-source; Redfish implementation is `bmcweb`
- API keys are the preferred authentication method in many OpenBMC deployments

### Supermicro

- Redfish support quality varies by BMC generation (X11 vs X12 vs H12)
- Some older X11 systems have incomplete Redfish; fall back to IPMI for those

### NVIDIA DGX / HGX

- DGX systems use Baseboard Management Controllers that expose full Redfish v1.x
- GPU health and thermal data may be accessible via OEM extensions or through the OS-side `nvidia-smi` / DCGM stack
- Confirm Redfish URI structure against your specific DGX firmware version

[↑ Back to Top](#table-of-contents)

---

## HTTP Status Code Reference

| Code | Meaning in Redfish context |
|------|---------------------------|
| 200 OK | Successful GET — response body contains the resource |
| 201 Created | POST created a new resource — `Location` header has the URI |
| 202 Accepted | Async operation started — `Location` header points to a Task |
| 204 No Content | Successful PATCH/DELETE with no response body |
| 400 Bad Request | Malformed JSON or invalid property values |
| 401 Unauthorized | Missing or invalid credentials |
| 403 Forbidden | Authenticated but insufficient privilege |
| 404 Not Found | URI does not exist on this BMC implementation |
| 405 Method Not Allowed | HTTP verb not supported on this resource |
| 409 Conflict | State conflict (e.g., power-on while already on) |
| 500 Internal Server Error | BMC-side error — retry after a delay |
| 501 Not Implemented | Feature exists in the spec but not in this implementation |
| 503 Service Unavailable | BMC temporarily busy or overloaded |

[↑ Back to Top](#table-of-contents)
