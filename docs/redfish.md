# Redfish: Overview and Architecture


[↑ Back to Top](#table-of-contents)

## Table of Contents

- [What Is Redfish?](#what-is-redfish)
- [Core Design Principles](#core-design-principles)
- [Protocol Stack](#protocol-stack)
- [Resource Model](#resource-model)
- [Key Resource Types](#key-resource-types)
- [OData Annotations](#odata-annotations)
- [Versioning](#versioning)
- [Transport and Security](#transport-and-security)
- [Specification Documents](#specification-documents)
- [Vendor Implementations](#vendor-implementations)
- [Related Documentation](#related-documentation)

---


[↑ Back to Top](#table-of-contents)

## What Is Redfish?

Redfish is a RESTful API standard developed and maintained by the Distributed Management Task Force (DMTF) for out-of-band management of servers, storage, and networking equipment. It was designed as a modern replacement for the aging IPMI (Intelligent Platform Management Interface) protocol, addressing IPMI's scalability, security, and usability deficiencies.

First published in 2015 as DMTF DSP0266, Redfish provides a secure, standardized, machine-readable interface that enables datacenter operators and automation tooling to manage heterogeneous hardware at scale without vendor-specific agents or protocols.


[↑ Back to Top](#table-of-contents)

## Core Design Principles

- **RESTful**: Resources are modeled as addressable URIs. Standard HTTP verbs (GET, POST, PATCH, DELETE) map directly to read, create, modify, and remove operations.
- **JSON-based**: All request and response payloads are JSON. Schemas are formally defined using JSON Schema and published by DMTF.
- **Hypermedia-driven**: Every response includes `@odata.id` links to related resources. Clients discover capabilities by traversal rather than hard-coded URI construction.
- **Schema-backed**: Every resource type has a versioned schema. Clients and tools can validate payloads against published schemas.
- **Secure by default**: Transport is HTTPS only. Authentication options include HTTP Basic Auth, session tokens, and API keys.
- **Eventing**: Redfish supports push-based event delivery via Server-Sent Events (SSE) and HTTP POST callbacks, enabling real-time monitoring without polling.


[↑ Back to Top](#table-of-contents)

## Protocol Stack

```
┌─────────────────────────────────────────────┐
│           Client (curl / SDK / tool)         │
├─────────────────────────────────────────────┤
│                HTTPS / TLS                   │
├─────────────────────────────────────────────┤
│             Redfish REST API                 │
│         (JSON + OData annotations)           │
├─────────────────────────────────────────────┤
│      Baseboard Management Controller (BMC)   │
│   (iDRAC / iLO / iRMC / OpenBMC / etc.)     │
├─────────────────────────────────────────────┤
│            Hardware / Firmware               │
└─────────────────────────────────────────────┘
```


[↑ Back to Top](#table-of-contents)

## Resource Model

The Redfish data model is organized as a tree of resource collections and singleton resources rooted at `/redfish/v1/`.

### Root Resources

| URI | Description |
|-----|-------------|
| `/redfish/v1/` | Service root — entry point, links to all top-level collections |
| `/redfish/v1/Systems/` | Computer systems (servers) |
| `/redfish/v1/Chassis/` | Physical enclosures, blades, sleds |
| `/redfish/v1/Managers/` | BMC/management controllers themselves |
| `/redfish/v1/AccountService/` | User accounts and roles |
| `/redfish/v1/SessionService/` | Session management |
| `/redfish/v1/EventService/` | Event subscriptions and delivery |
| `/redfish/v1/TaskService/` | Long-running asynchronous operations |
| `/redfish/v1/UpdateService/` | Firmware/BIOS update workflows |
| `/redfish/v1/CertificateService/` | TLS certificate management |
| `/redfish/v1/Registries/` | Message and attribute registries |

### Resource Hierarchy Example

```
/redfish/v1/Systems/1/
├── Processors/
│   └── CPU1/
├── Memory/
│   ├── DIMM1/
│   └── DIMM2/
├── Storage/
│   ├── RAID1/
│   │   └── Drives/
│   │       ├── Drive1/
│   │       └── Drive2/
│   └── Volumes/
├── EthernetInterfaces/
│   └── NIC1/
├── PCIeDevices/
├── Bios/
├── LogServices/
│   └── Sel/
│       └── Entries/
├── Actions/
│   ├── #ComputerSystem.Reset
│   └── #ComputerSystem.SetDefaultBootOrder
└── Boot/
```


[↑ Back to Top](#table-of-contents)

## Key Resource Types

### ComputerSystem

Represents a single logical server instance. Key properties:

- `PowerState`: Current power state (`On`, `Off`, `PoweringOn`, `PoweringOff`)
- `Status.Health`: Aggregate health rollup (`OK`, `Warning`, `Critical`)
- `MemorySummary.TotalSystemMemoryGiB`: Total installed RAM
- `ProcessorSummary.Count` / `ProcessorSummary.Model`: CPU count and model string
- `BiosVersion`: Currently running BIOS version
- `Boot`: Boot source override settings
- `IndicatorLED`: Physical LED state for identification

### Chassis

Represents the physical enclosure. Contains sensors (temperature, voltage, fans), power supplies, and the physical inventory.

### Manager

Represents the BMC itself. Exposes:

- `FirmwareVersion`: BMC firmware version
- `NetworkProtocol/`: Enables/disables protocols (SSH, IPMI-over-LAN, HTTPS, SNMP, etc.)
- `EthernetInterfaces/`: BMC NIC configuration (IP, VLAN, DNS)
- `LogServices/`: BMC event log


[↑ Back to Top](#table-of-contents)

## OData Annotations

All Redfish responses include OData v4 annotations:

| Annotation | Meaning |
|------------|---------|
| `@odata.type` | Fully-qualified schema type name and version |
| `@odata.id` | Canonical URI of this resource |
| `@odata.context` | URI to the JSON-LD context / schema definition |
| `@odata.etag` | ETag for optimistic concurrency on PATCH |


[↑ Back to Top](#table-of-contents)

## Versioning

Redfish uses semantic versioning for both the API (`/redfish/v1/`) and individual resource schemas. The schema version is embedded in `@odata.type`:

```
#ComputerSystem.v1_20_0.ComputerSystem
```

Clients should program against a minimum schema version and handle additional properties gracefully (unknown properties must be ignored per the spec).


[↑ Back to Top](#table-of-contents)

## Transport and Security

- **HTTPS required**: HTTP is permitted only for initial redirect to HTTPS. Plaintext access must be disabled in production.
- **TLS version**: TLS 1.2 minimum; TLS 1.3 recommended.
- **Certificate validation**: Clients should validate server certificates. Self-signed certificates are common in BMC deployments; import the CA bundle or pin the certificate rather than disabling verification entirely.
- **Authentication methods**:
  - HTTP Basic Auth (stateless, per-request credential)
  - Session-based auth (`/redfish/v1/SessionService/Sessions/`) — returns an `X-Auth-Token` header
  - API keys (implementation-dependent, common in OpenBMC)


[↑ Back to Top](#table-of-contents)

## Specification Documents

| Document | Description |
|----------|-------------|
| DSP0266 | Redfish Specification (main protocol spec) |
| DSP0268 | Redfish Data Model Specification (resource schemas) |
| DSP0270 | Redfish Interoperability Profiles |
| DSP0272 | Redfish Interoperability Profile Specification |
| DSP8010 | Redfish Schema Bundle (downloadable schema ZIP) |
| DSP2046 | Redfish Resource and Schema Guide |

All documents are freely available at [https://www.dmtf.org/standards/redfish](https://www.dmtf.org/standards/redfish).


[↑ Back to Top](#table-of-contents)

## Vendor Implementations

| Vendor | BMC Product | Notes |
|--------|-------------|-------|
| Dell | iDRAC (9+) | Strong Redfish support; iDRAC 9 = full v1.x coverage |
| HPE | iLO 5 / iLO 6 | iLO 5 introduced full Redfish; iLO 6 on Gen11 |
| Lenovo | XCC (ThinkSystem) | XCC2 on Gen3 servers |
| Supermicro | IPMI/BMC | Varies by board generation |
| Intel | Intel BMC | Deprecated; now OpenBMC-based |
| OpenBMC | open-source | Community/OEM build; powers Meta, Google, and cloud-scale hardware |
| Ampere | Ampere BMC | ARM server; OpenBMC-based |


[↑ Back to Top](#table-of-contents)

## Related Documentation

- [User Guide](guide-users.md) — How to interact with a Redfish service: querying resources, performing actions, scripting
- [Admin Guide](guide-admin.md) — How to configure, secure, and maintain Redfish services in production
