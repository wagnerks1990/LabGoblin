# Backend architecture

The FastAPI application is Proxmox-only. `app/api/routes.py` composes feature
routers from `app/api/routers/`; there is no legacy parallel router.

## Request boundary

Authentication accepts a bearer token for API tooling or the HttpOnly
`labgoblin_session` cookie used by the web application. The token must map to a live
`auth_sessions` record and the current user token version. Organization context
is resolved independently and fails closed for unknown roles or inactive
memberships.

Routers validate policy and create desired state. They do not own long-running
Proxmox mutations. VM mutation routes commit `durable_operations` and return
HTTP `202` with an operation identifier.

## Service boundary

- `services/proxmox.py` is the backend-only Proxmox adapter.
- `services/operation_service.py` allocates VMIDs, queues, leases, executes,
  retries, and verifies infrastructure operations.
- `services/classroom_access.py` evaluates enrollment, assignment, schedule,
  ownership, and lab access flags.
- `services/organization_access.py` resolves tenant scope and role rank.
- `services/asset_sync.py` manages restart-safe asset jobs with JSON metadata.
- `services/guacamole_console.py` brokers same-origin browser sessions through
  bundled guacd; `remote_profile.py` enforces approved guest identity and login.
- `services/vm_observations.py` collects typed resource data;
  `guest_discovery.py` reads and filters VM-bound guest-agent interfaces.

## Background work

APScheduler currently runs inside the API process. Durable operations use
PostgreSQL row leases, while worker overlap and reconnect-token replay use
Redis in Compose. Asset jobs are claimed from PostgreSQL. This is safe for the
single-API pilot; separating worker and scheduler processes remains required
before horizontal API scaling.

## Persistence and contracts

SQLAlchemy models live in `app/models/models.py`; all schema changes use the
single linear Alembic history. OpenAPI is exported to `frontend/openapi.json`
and produces `frontend/src/generated/api-schema.d.ts`. CI rejects contract
drift.

## Remote access

The primary browser path is the same-origin Guacamole WebSocket for Windows
RDP, Linux SSH terminal, and Proxmox VNC. Compose bundles guacd 1.6.0; there is
no separate Guacamole web application or student account. Proxmox VNC uses an
authenticated temporary bridge. Guest RDP/SSH uses an administrator-approved
reserved address, matching Proxmox MAC, pinned server identity and encrypted
VM-specific or template login. Lab policy and live sessions remain authoritative.
Legacy compatibility routes are retained; the old SSH pilot is disabled and
SPICE is unsupported. See [browser connections](operations/consoles.md).

## Read-only VM observations

`GET /api/vms` and `GET /api/vms/{id}/status` authorize the application VM id
before calling Proxmox. `VMResponse.resources` contains allocation, usage,
uptime and cumulative I/O. `observed_addresses` contains filtered agent IP/MAC
observations. `observed_at`, `resource_warning` and `discovery_hint` distinguish
fresh, partial and unavailable data. These fields are transient response data;
no resource migration or guest-IP persistence is performed.

The list limits active VM checks to four and the overall check to 20 seconds.
Status/configuration calls and agent discovery have their own deadlines.
Partial failures preserve available fields with warnings. Disk capacity is
allocated storage, not guest filesystem free space. Discovery must never write
`assigned_ip`, modify remote profiles or authorize credential transmission.

Connection options return independent `method_hints`; a successful VNC check
must not hide a blocked RDP/SSH reason. A saved profile enables its corresponding
VM protocol flag, while assignment policy can still deny student access.
