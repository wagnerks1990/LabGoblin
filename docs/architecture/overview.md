# V2 architecture

## Design goals

V2 is a classroom orchestration system, not a thin collection of Proxmox API
buttons. The database records desired state, durable workers reconcile that
state with Proxmox, and the API exposes explicit, authorized workflows.

The primary design goals are:

- safe student and teacher isolation;
- recoverable infrastructure mutations;
- a complete class-to-lab-to-assignment workflow;
- one-command installation on a dedicated Ubuntu host;
- database-managed operational configuration;
- reliable browser access through Guacamole;
- optional, permission-aware AI assistance;
- maintainability by both people and coding agents.

## Runtime components

| Component | Responsibility |
|---|---|
| Web | React/TypeScript application and role-aware user experience |
| API | Authentication, policy, validation, query APIs, and job submission |
| Worker | Leased Proxmox mutations, asset sync, reconciliation, cleanup, and retries; currently hosted in the API process |
| Scheduler | Creates periodic reconciliation, expiration, and health work; currently hosted in the API process |
| PostgreSQL | Authoritative configuration, desired state, jobs, and audit history |
| Redis | Queue transport, distributed locks, rate limits, and short-lived events |
| Console broker | Same-origin Guacamole broker and bundled private guacd for Proxmox VNC, Windows RDP and Linux SSH |
| Reverse proxy | TLS termination and routing for web, API, WebSocket, and Guacamole traffic |
| Cloudflare edge | Optional DNS, TLS, WAF, Access, and outbound Tunnel publication; disabled by default |
| Documentation | Version-matched MkDocs wiki |
| AI gateway | Planned optional provider abstraction; current AI behavior is documentation-only and read-only |

The current scheduler is embedded in the API process. Redis locks and database
leases prevent overlapping work, but separating and independently scaling the
worker/scheduler is still required before multi-API deployment.

## Optional external edge

The supported Cloudflare topology uses a `cloudflared` connector in the
opt-in `cloudflare` Compose profile and binds the appliance HTTP listener to
loopback. The public hostname terminates at Cloudflare and reaches the connector
over an outbound Tunnel; the origin is not independently Internet-reachable.
LabGoblin does not hold a broad Cloudflare account API credential.

Cloudflare Access can provide pre-authentication and machine service policies.
When enabled, the API validates the Access assertion signature, issuer,
audience, and time claims as an additional edge boundary. The verified assertion
does not create a LabGoblin session or grant a role. Application login, session
revocation, organization membership, ownership, RBAC, CSRF, and WebSocket origin
checks remain authoritative.

LabGoblin does not currently promote Cloudflare forwarding headers into
identity or audit fields. Any future use must accept them only from the
exclusive trusted Tunnel path. Dynamic API, identity, event-stream, and console
traffic is never edge-cached. See
[Optional Cloudflare edge integration](../operations/cloudflare.md).

## Domain boundaries

V2 uses feature modules rather than large global router files:

- identity and organizations;
- classes and enrollments;
- lab blueprints and lab runs;
- Proxmox clusters and inventory;
- templates and assets;
- VM assignments and instances;
- networking and isolation;
- console sessions;
- durable jobs and reconciliation;
- audit and telemetry;
- AI recommendations.

Each feature owns its API schemas, application service, persistence model,
authorization policies, and tests. Proxmox-specific code is behind an adapter
interface so tests can use a deterministic fake implementation.

## Organization identity

V2 introduces organizations as the tenant boundary. A user may belong to more
than one organization with a different tenant role in each. Tenant roles are
`student`, `instructor`, `admin`, and `owner`; unknown roles always fail closed.

The existing global `Admin`, `Teacher`, and `Student` roles remain temporarily
for compatibility. Global `Admin` is an explicit break-glass scope. Existing
accounts are backfilled into a visible `default` organization so upgrades do
not silently strand development data. Core resources—including templates, VMs,
sessions, pools, groups, classes, labs, and audit events—carry an organization
identifier and are filtered at the API boundary.

Authenticated HTTP requests select an organization with `X-Organization-ID`.
The server verifies active membership; the identifier is context, never proof
of access. Accounts with one active membership are selected automatically.
Accounts with multiple memberships must select one. A global `Admin` may select
any enabled organization through an explicit, audited break-glass path. Browser
clients persist the selection locally and attach it to each API request.

## Desired-state workflow

Infrastructure operations follow this sequence:

1. Validate authentication, organization scope, policy, quota, and input.
2. Create a durable job with a unique idempotency key.
3. Commit the desired state and audit request in one transaction.
4. A worker claims the job with a distributed lock.
5. The worker submits a Proxmox task and stores its UPID immediately.
6. The worker polls or reconciles the result after restarts.
7. The final observed state and audit outcome are committed.
8. Failures enter a retry, compensation, or manual-review state.

API request processes never own long-running Proxmox work through an in-memory
task.

## Resource identity

Every managed Proxmox resource receives platform tags containing immutable
organization, lab-run, assignment, and VM-instance identifiers. Names are for
people; tags and database identifiers establish ownership.

Deleting an application record is never equivalent to deleting a Proxmox
resource. Both operations have separate names, permissions, previews, and audit
events.

## Lab model

A **Lab Blueprint** is reusable curriculum infrastructure. It can describe one
VM or a multi-VM topology with private networks, routers, firewalls, services,
and client systems.

A **Lab Run** is a scheduled use of that blueprint by a class. It creates
assignments for individual students or teams and applies quotas, network
isolation, access permissions, start/end times, and cleanup policy.

This split supports introductory single-VM labs immediately without blocking
future Network+, Security+, or penetration-testing topologies.
