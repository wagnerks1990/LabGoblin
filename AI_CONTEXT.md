# LabGoblin AI contributor context

Read this file, `AGENTS.md`, `docs/brand.md`, and the documentation page for the feature before changing code.

## Canonical identity

- Product: **LabGoblin**
- Category: **Virtual Lab Provisioning & Management**
- Primary tagline: **Real Skills. Virtual Machines.**
- Campaign line: **Build. Deploy. Learn. Repeat.**
- Canonical technical identifier: `labgoblin`
- Canonical service prefix: `labgoblin-`
- Install root: `/opt/labgoblin`
- State root: `/var/lib/labgoblin`
- Session cookie: `labgoblin_session`
- Canonical repository: `https://github.com/wagnerks1990/labgoblin.git`

All user-facing and LabGoblin-owned technical identifiers must use LabGoblin naming. Proxmox VE is an infrastructure integration, not part of the product name.

## Product boundary

LabGoblin is a classroom control plane. PostgreSQL is authoritative for desired state; Proxmox VE is an external system whose observed state must be reconciled. Students never gain broad Proxmox access.

## Clean-install branding rules

This repository is development software intended for fresh installation. There is no requirement to preserve predecessor installation paths, service names, database defaults, package names, cookie names, logger namespaces, helper names, updater state paths, or repository URLs.

- Do not introduce new LabGoblin-owned identifiers using `proxmox-lab-platform`, `proxmox_lab`, `plp_`, or `proxmox-lab-*` naming.
- Do not use the retired repository path `wagnerks1990/proxmox-lab-platform`; the canonical repository is `wagnerks1990/labgoblin`.
- Keep `PROXMOX_*`, `ProxmoxCluster`, Proxmox API routes/fields, and similar terminology when they genuinely describe the Proxmox VE integration.
- Keep README, source-controlled wiki, operator docs, release notes, frontend metadata, deployment code, tests, and AI-aware files synchronized.
- Do not imply that LabGoblin is affiliated with, endorsed by, or part of Proxmox Server Solutions GmbH.

## Design tokens

- Goblin Green: `#22C55E`
- Deep Space: `#0B1220`
- Slate Surface: `#1F2937`
- Steel Secondary: `#3B4754`
- Cloud Light: `#E5E7EB`
- Mint Accent: `#A7F3D0`
- UI/body type: Inter or system-ui fallback

The complete interface contract is in `docs/brand.md` and
`docs/frontend-architecture.md`. Use shared tokens and components rather than
inline status styling. The shell groups work by role, marks the active route,
offers an accessible compact drawer and bottom navigation, and supports a 320
CSS pixel viewport without page-level horizontal scrolling.

## Non-negotiable invariants

- Resolve organization membership and object ownership on every request.
- Persist Proxmox mutations as `durable_operations` before calling Proxmox.
- Store the Proxmox UPID, use idempotency keys, lease jobs, and verify results.
- Allocate VMIDs through `vmid_allocators`; never calculate them from row counts.
- Preview destructive actions and require an explicit confirmation value.
- Keep JWTs in HttpOnly cookies. Never put JWTs, tickets, credentials, keys, or provider secrets in URLs, logs, browser storage, or normal API responses.
- Enforce exact browser origins on cookie-authenticated unsafe requests and WebSockets.
- Do not change a credential-bound Proxmox origin or TLS policy in place.
- Root bootstrap is a one-time `root@pam` exchange that creates the fixed
  least-privilege `labgoblin@pve` user and token. Never persist the root
  password, create a root token, or overwrite conflicting Proxmox identities.
- Keep SSH terminal access disabled until per-assignment credentials and trusted destination binding replace deployment-wide credentials and guest-claimed IP authority.
- Treat AI-generated material as untrusted advice. AI is read-only until a human approves a normal, authorized durable operation.
- Treat Cloudflare as an optional edge, not an application authority. Preserve
  the `cloudflare` Compose profile, `cloudflared` service, loopback HTTP bind,
  root-owned `/etc/labgoblin/cloudflare-tunnel-token` restricted to the
  dedicated connector group, exact HTTPS origin, and secure-cookie contract
  described in `docs/operations/cloudflare.md`.
- Preserve guided Cloudflare `plan` and `apply` reconciliation, protected
  file-only API-token input, nonsecret resource-ID state, local JSON status,
  DNS-last publication, connector health gating, and fail-closed disable
  behavior. A LAN bind is restored only through the explicit
  `--restore-lan-bind` choice.
- Prefer an approved district IdP group for student access. Treat the
  email-domain selector as a weaker fallback and never publish Proxmox, SSH,
  PostgreSQL, Redis, updater, management, or lab-network services.
- Access enforcement validates `Cf-Access-Jwt-Assertion` cryptographically and
  then continues through normal LabGoblin authentication, revocable sessions,
  organization membership, RBAC, ownership, CSRF, and audit checks. Never map
  Access email/groups directly to authority or accept header presence alone.
- Cloudflare forwarding headers are not application identity or audit fields.
  Any future use is restricted to the configured Tunnel path; never use a
  forwarded client address as identity or authorization evidence.
- R2 backup work remains deferred until a complete client-side encrypted backup
  and repeatable isolated restore contract exists.
- Add a linear Alembic migration for schema changes and regenerate the OpenAPI contract.

## Validation

Run backend tests, frontend tests/build, dependency audits, the single-head migration check, strict documentation build, generated-contract drift check, and branding regression checks. Offline tests do not prove behavior against a real Proxmox cluster.

Frontend work additionally requires role/navigation, responsive, view-state,
keyboard, accessible-name, and live-region checks. Use the matrices in
`docs/development/frontend-testing.md` and `docs/gui-section-validation.md`.
Passing source-contract tests does not prove browser layout or interaction.

## Useful entry points

- API composition: `backend/app/api/routes.py`
- Authorization: `backend/app/api/deps.py`, `backend/app/services/organization_access.py`
- Durable work: `backend/app/services/operation_service.py`, `backend/app/workers/operation_worker.py`
- Proxmox adapter: `backend/app/services/proxmox.py`
- Classroom policy: `backend/app/services/classroom_access.py`
- Deployment: `deploy/install.sh`, `deploy/updater_agent.py`, `deploy/labgoblin-updater.service`, `docker-compose.yml`
- Cloudflare edge: `deploy/configure-cloudflare.sh`, `docker-compose.yml`,
  `docs/operations/cloudflare.md`
- Contract: `frontend/openapi.json`, `frontend/src/generated/api-schema.d.ts`
- Brand: `docs/brand.md`, `frontend/public/brand/`
- Navigation model: `frontend/src/navigation/appNavigation.js`
- Application shell: `frontend/src/layouts/AppLayout.jsx`,
  `frontend/src/components/navigation/`
- Frontend validation: `frontend/tests/`,
  `docs/development/frontend-testing.md`

Bootstrap discovers identity existence through successful role/user collection responses. Proxmox can return HTTP 500 for missing individual identities; never treat arbitrary HTTP 500 failures as absence. Discovery failures must stop setup.

Bootstrap reads the built-in Administrator role only to discover supported privilege names. It prefers VM.GuestAgent.Audit, uses VM.Monitor only on older servers lacking that replacement, and refuses unsupported required privileges before creating objects. It never assigns Administrator.


Template catalog refresh runs automatically when a platform administrator opens
Templates, Proxmox inventory, or VM provisioning. It discovers the active cluster
and upserts templates into the selected organization while preserving catalog IDs,
custom names, and disabled settings. Existing VMs remain inventory observations;
discovery does not grant student access or transfer ownership. Networks, storage,
and installation media are read from the cluster. Refresh is page-triggered, not a
background synchronization daemon. Template deletion and disk replication are not
automatic.

VM creation checks the cluster VM inventory before cloning, then tracks the durable
Proxmox task through completion. Failed inventory requests stop creation; HTTP 500
is never interpreted as absence. The provisioning page displays operation status
and errors, and Operations opens on all history with a Failed filter. Local tests
do not establish the cause of a particular production failure.
