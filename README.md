# LabGoblin

VM cards now show live allocated CPU, memory and disk capacity, usage and uptime, and guest-agent IP/MAC observations. Connection choices explain unavailable RDP/SSH and expose administrator preparation above VNC. See [browser connections](docs/operations/consoles.md).

Guided lab setup now combines class, pool, roster/accounts, assignments, and access scheduling in an editable wizard. Students land on a simplified My labs home with direct browser connections. See [instructor setup](docs/user-guide/instructor-workflow.md).


Template guest logins can now be encrypted in template settings, inherited for automatic browser connections, and explicitly shared with authorized students through an audited, temporary reveal. See [console access](docs/operations/consoles.md).


**Virtual Lab Provisioning & Management**  
**Real Skills. Virtual Machines.**

LabGoblin is a classroom-focused control plane for giving students controlled access to virtual lab resources while instructors manage templates, assignments, scheduling, provisioning, lifecycle operations, and auditability.

> **Development status:** the current application is an alpha. It is suitable for isolated development and review, but it is not yet approved for unsupervised student or production use. The V2 stabilization and rebuild roadmap is documented in [`docs/roadmap/v2-rebuild.md`](docs/roadmap/v2-rebuild.md).

The source-controlled documentation wiki starts at [`docs/index.md`](docs/index.md). Brand and naming rules are documented in [`docs/brand.md`](docs/brand.md).

## Brand identity

- **Product:** LabGoblin
- **Category:** Virtual Lab Provisioning & Management
- **Primary tagline:** Real Skills. Virtual Machines.
- **Campaign line:** Build. Deploy. Learn. Repeat.
- **Primary color:** Goblin Green `#22C55E`
- **Primary dark:** Deep Space `#0B1220`

LabGoblin is the product identity. **Proxmox VE** is currently the underlying hypervisor integration and is referenced by name only where technically relevant.

## Workspace experience

The branded workspace includes quick page finding (`Ctrl+K` / `Cmd+K`),
searchable VM and template collections, card/list layouts, a provisioning review,
an activity center with warning/failure filters, and guided classroom and pool
management. See [Frontend architecture](docs/frontend-architecture.md) for the
workflow map and [GUI validation](docs/gui-section-validation.md) for acceptance
checks and remaining browser validation.

## Appliance installation

A dedicated Debian or Ubuntu VM on the Proxmox cluster is the recommended deployment target.

```bash
curl -fsSL https://raw.githubusercontent.com/wagnerks1990/labgoblin/main/deploy/install.sh | sudo sh
```

A fresh installation is fully LabGoblin-native: `/opt/labgoblin`, `/var/lib/labgoblin`, the `labgoblin-updater` service/group, LabGoblin database defaults, and LabGoblin application identifiers.

The installer deploys LabGoblin with Docker Compose, generates bootstrap secrets, runs database migrations, installs the local update agent, and waits for the application health gate. See [`docs/operations/deployment.md`](docs/operations/deployment.md) before using the direct-on-hypervisor override. For a private repository, clone with a read-only deploy key first; unauthenticated `raw.githubusercontent.com` links do not work for private repositories.

### Proxmox connection

From an HTTPS page or a localhost SSH tunnel, a platform administrator can use
the Proxmox setup page and a one-time `root@pam` password to create the fixed
`labgoblin@pve` user, least-privilege `LabGoblinRole`, and
`labgoblin@pve!labgoblin` API token automatically. LabGoblin stores only the
encrypted generated token, never the root password. Existing conflicting users
or roles are not overwritten. See
[`docs/proxmox-setup-wizard.md`](docs/proxmox-setup-wizard.md).

### Optional Cloudflare edge

The deployment includes an opt-in `cloudflare` Compose profile for publishing
LabGoblin through an outbound-only Cloudflare Tunnel. This is the recommended
public path when students need to use their assigned labs from home. Students
open one HTTPS URL, complete district SSO through Cloudflare Access, sign in to
LabGoblin, and use their assigned browser consoles. They do not need WARP, a
VPN client, a Cloudflare account, or access to Proxmox, SSH, the database, or
internal lab networks.

The guided provisioner can plan and reconcile the Tunnel, ingress, Access
application and least-privilege policy, and DNS record. Prefer an approved
district IdP group; the supported email-domain fallback is broader and weaker.

```bash
cd /opt/labgoblin/app
sudo python3 deploy/provision_cloudflare.py plan \
  --api-token-file /root/cloudflare-api-token \
  --account-id CLOUDFLARE_ACCOUNT_ID \
  --zone example.edu \
  --hostname lab.example.edu \
  --team-domain school.cloudflareaccess.com \
  --access-group-id CLOUDFLARE_ACCESS_GROUP_ID
# Review the plan, then repeat the same protected arguments with `apply`.
sudo deploy/configure-cloudflare.sh status --json
```

The provisioner passes the Tunnel token directly to the hardened local helper;
only nonsecret resource IDs are persisted. It keeps the origin on loopback,
uses a restricted token file, configures the exact HTTPS browser origin and
secure cookies, and requires a cryptographically validated Access assertion
before LabGoblin's own login and RBAC. Cloudflare Access is an outer gate, not
a replacement identity or authorization system. Read the complete scopes,
manual fallback, security, real-environment staging, outage recovery, rotation,
verification, and rollback procedure in
[`docs/operations/cloudflare.md`](docs/operations/cloudflare.md) before enabling
the profile. Cloudflare R2 backups are deliberately deferred until LabGoblin
supports complete client-side encrypted backups and isolated restore tests.

## Stack
- Frontend: React + Vite
- Backend: FastAPI + SQLAlchemy
- DB: PostgreSQL
- Auth: revocable JWT sessions in HttpOnly same-site cookies + bcrypt password hashing

## Project structure
- `backend/app/main.py` – FastAPI entrypoint
- `backend/app/api/routes.py` – REST endpoints
- `backend/app/models/models.py` – relational models (`users`, `roles`, `vm_templates`, `student_vms`, `permissions`, `audit_logs`)
- `backend/app/services/proxmox.py` – secure backend-only Proxmox API client
- `backend/alembic/` – authoritative PostgreSQL schema migrations
- `backend/scripts/seed_dev_admin.py` and `seed_dev_lab_data.py` – development-only seed helpers
- `frontend/src/main.jsx` – application routes and bootstrap
- `frontend/public/brand/` – application branding assets

## Working development features

- organization membership and tenant roles;
- revocable login sessions, password lifecycle, and persistent login throttling;
- instructor-scoped classes, rosters, lab blueprints, scheduled runs, and assignments;
- student VM access gated by membership, enrollment, assignment, run window, and ownership;
- template discovery/import, placement-aware VM provisioning, lifecycle controls, and reconciliation;
- Docker Compose installation, health-gated GitHub updates, and rollback;
- structured identity and classroom audit events;
- optional Cloudflare Tunnel publication and validated Access pre-authentication;
- source-controlled MkDocs wiki and CI validation.

The current API is mounted at `/api` and `/v1/api` during the versioned transition. Interactive OpenAPI documentation is available at `/docs` on a running development installation and is branded as the **LabGoblin API**.

## Disposable live test

The repository includes a stateful Proxmox simulator and a guarded end-to-end test. It exercises first-admin enrollment, organization and classroom setup, student authorization, durable VM clone/start/stop/delete operations, and logout through the public HTTP API. The test is destructive and is intended only for the disposable Docker Compose database created for CI.

```bash
export POSTGRES_PASSWORD='live-test-database-password'
export JWT_SECRET_KEY='live-test-jwt-secret-at-least-32-characters'
export CONFIG_ENCRYPTION_KEY='live-test-encryption-key-at-least-32-characters'
export UPDATER_TOKEN='live-test-updater-token'
export BOOTSTRAP_ADMIN_TOKEN='live-test-bootstrap-token'
export UPDATER_GID='0'
docker compose -f docker-compose.yml -f docker-compose.live-test.yml up -d --build
python scripts/live_test.py --bootstrap-token "$BOOTSTRAP_ADMIN_TOKEN" \
  --i-understand-this-deletes-data
docker compose -f docker-compose.yml -f docker-compose.live-test.yml down \
  --volumes --remove-orphans
```

See [`docs/operations/live-test.md`](docs/operations/live-test.md) for safety boundaries, troubleshooting, and what this simulator does not prove.

## Development setup

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/ensure_config_encryption_key.py --create
alembic upgrade head
uvicorn app.main:app --reload
```

Alembic is the only supported schema initialization path. For optional development data, use the seed scripts after migrating; `seed_dev_lab_data.py` requires `DEV_ORGANIZATION_SLUG` so records cannot be written into an implicit tenant.

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## First administrator

A fresh appliance has no default password. The installer prints a random, one-time bootstrap token used by the first-run page to create the initial administrator. See [`docs/operations/first-run.md`](docs/operations/first-run.md).

## Proxmox VE configuration

Set the appropriate configuration in `backend/.env` or configure the integration through the administration interface. Relevant variables include:

- `PROXMOX_BASE_URL`
- `PROXMOX_TOKEN_ID`
- `PROXMOX_TOKEN_SECRET`
- `PROXMOX_VERIFY_SSL`

The token is used only by the backend service and is never exposed to frontend code. LabGoblin-generated Proxmox tokens default to the token ID `labgoblin`.

## LabGoblin runtime identifiers

Fresh installations use these canonical application-owned names:

- install root: `/opt/labgoblin`
- state root: `/var/lib/labgoblin`
- Compose project: `labgoblin`
- default PostgreSQL database/user: `labgoblin`
- web session cookie: `labgoblin_session`
- updater unit/group: `labgoblin-updater.service` / `labgoblin-updater`
- updater executable: `/usr/local/lib/labgoblin-updater.py`
- host runner: `labgoblin-runner`
- frontend package: `labgoblin-frontend`
- canonical repository: `https://github.com/wagnerks1990/labgoblin.git`

Proxmox-specific names remain where they describe the actual hypervisor integration rather than LabGoblin itself.

## Security notes

- Passwords are stored as bcrypt hashes.
- VM actions require authenticated authorization.
- Student provisioning requires an active classroom assignment; legacy direct and group template permissions are not sufficient.
- VM operations are auditable.
- Secret values are sourced from protected configuration.
- Branding changes must never weaken authorization, tenant isolation, updater safety, or audit behavior.

## Post-pull validation

Run this command to validate current live backend health after pulling changes:

```bash
python backend/scripts/validate_deploy.py
```

It checks backend module compilation, required architecture events, a single Alembic head, database connectivity, and live `/api/health` state.

## SSE proxy requirement

The shipped frontend NGINX configuration includes a dedicated `/api/admin/events/stream` location that disables proxy buffering and keeps the stream open. Custom Compose proxies can reuse `deploy/nginx/sse-events-stream.conf`; deployments using a host-level proxy must replace its `api:8000` container upstream with the host's actual API upstream.

## Naming policy

This repository is development software intended for fresh installation. LabGoblin-owned technical identifiers use canonical LabGoblin naming and predecessor repository/runtime identifiers are not permitted in active configuration or documentation. See [`docs/brand.md`](docs/brand.md).

## Future expansion-ready

The architecture leaves space for quotas, scheduled cleanup, snapshots, VLAN/private network workflows, SSO providers, embedded remote consoles, and broader hypervisor abstraction.

### Automatic inventory and provisioning status


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

Power-task warnings remain visible without falsely failing a verified running VM.
See [Proxmox operations guidance](docs/proxmox-setup-wizard.md) for the verification boundary.

### Integrated browser connections

The default deployment now includes Apache Guacamole. **Connect in browser**
checks VM availability and opens Windows RDP, Linux SSH terminal, or Proxmox VNC
in LabGoblin. VNC works without guest network setup. RDP/SSH guest services,
identity and VM-specific credentials are prepared in the GUI; authoritative
IPAM/account auto-provisioning is not implemented. See
[Browser connections](docs/operations/consoles.md) for the exact readiness and
security contract and post-update validation.

Guest setup now discovers current QEMU-agent addresses through Proxmox, matches
VM adapters, and labels static cloud-init matches. It does not recover guest
passwords or silently replace approved destinations.
