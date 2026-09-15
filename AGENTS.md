# LabGoblin — AGENT Guardrails

## Project
- This is **LabGoblin — Virtual Lab Provisioning & Management**.
- Primary tagline: **Real Skills. Virtual Machines.**
- Campaign line: **Build. Deploy. Learn. Repeat.**
- It is a classroom VM orchestration/control-plane app.
- Backend is FastAPI.
- Frontend is React/Vite.
- Database is PostgreSQL.
- ORM is SQLAlchemy.
- Migrations use Alembic.
- Runtime deployment uses Ubuntu, nginx, and systemd.
- Proxmox VE API access must remain backend-only.
- Remote access direction is Guacamole-first, with ttyd only as fallback/debug if already present.
- Cloudflare is an optional deployment edge. The canonical contract is in
  `docs/operations/cloudflare.md`.

## Branding and documentation
- User-facing names MUST use **LabGoblin**.
- LabGoblin-owned technical identifiers MUST use `labgoblin` / `labgoblin-` naming.
- This is development software for fresh installation; predecessor installation identifiers do not require compatibility preservation.
- Do not introduce LabGoblin-owned identifiers named `proxmox-lab-platform`, `proxmox_lab`, `plp_`, or `proxmox-lab-*`.
- Do not reference the retired repository `wagnerks1990/proxmox-lab-platform`; the canonical repository is `wagnerks1990/labgoblin`.
- Keep Proxmox terminology only when it genuinely names the Proxmox VE integration, API objects, VMIDs/UPIDs, configuration variables, or integration-specific database models.
- Keep README, MkDocs/wiki pages, deployment/runbooks, architecture notes, release notes, screenshots/help text, and `AI_CONTEXT.md` synchronized with relevant behavior changes.
- Brand guidance and design tokens are defined in `docs/brand.md`.
- The project owner's approved visual direction is documented in `docs/design/rendering-reference.md`. Frontend work should use it as a visual target after security, accessibility, documented workflow/API contracts, and canonical brand rules. Do not blindly copy generated artwork or fabricated data.

## Workflow
- Never work directly on `main`.
- Always use focused feature branches.
- Avoid broad rewrites unless explicitly requested.
- Preserve existing working behavior.
- Prefer incremental, testable changes.
- Keep frontend API base URL as `/api`.
- Preserve the disabled-by-default `cloudflare` Compose profile, root-owned
  Tunnel token restricted to the dedicated connector group, loopback origin
  binding, connector health gate, exact public-origin settings, and explicit
  `--restore-lan-bind` requirement. Preserve the provisioner's reviewed
  plan/apply reconciliation, local JSON status, and DNS-last ordering.

## Frontend experience

- Preserve the responsive application shell, grouped role-aware navigation,
  active-route semantics, skip link, compact drawer, and mobile bottom
  navigation.
- The frontend is not an authorization boundary. Hidden navigation must match
  capabilities, and the backend must still deny direct restricted requests.
- Support 320, 390, 768, 1024, and 1440 CSS pixel validation widths without
  page-level horizontal scrolling.
- Every data-backed view must distinguish loading, empty, error, forbidden, and
  populated states. Do not convert a failed request into a healthy empty state.
- Give form controls persistent accessible names. Preserve heading order,
  visible focus, keyboard operation, live feedback, and dialog focus return.
- Use shared design tokens and status treatments. Never rely on color alone or
  add arbitrary inline status colors.
- Do not replace durable operation progress with optimistic Proxmox success.
- Keep screenshots and help text sanitized and synchronized with navigation or
  workflow changes.

## Preserve
- login
- RBAC
- `/api/auth/me`
- `/api/health`
- VM list/create/start/stop/reboot/delete
- guest-agent IP discovery
- template permissions
- session activity
- telemetry summary/events
- SSE operational stream
- Operations page
- Troubleshooting page
- scheduler/worker visibility
- Alembic migration chain
- frontend build behavior
- responsive and keyboard-accessible navigation
- explicit loading, empty, error, and durable-operation states

## Security
- Never expose Proxmox API tokens to frontend code.
- Proxmox root bootstrap may use `root@pam` only as a one-time credential to
  create the fixed least-privilege `labgoblin@pve` service identity. Never
  persist or return the root password, create a root token, or overwrite a
  conflicting service user or role.
- Never include guest credentials in VM/template lists, URLs, storage, or logs.
  Explicit user-authorized exception: an audited, no-store POST reveal may return
  the template lab login to a currently authorized VM user when template sharing
  is enabled. Automatic connections keep secrets server-side. See consoles.md.
- Never expose infrastructure SSH credentials or private keys to frontend code.
  The explicit template lab-login reveal exception above also covers lab SSH passwords.
- Never expose Guacamole credentials to frontend code.
- Never commit `.env` files.
- Never commit secrets, private keys, certificates, passwords, tokens, local databases, or generated runtime artifacts.
- Students may only access their own VMs.
- Tenant instructors, administrators, and owners may manage VMs only in the selected organization. Students may manage only VMs they own.
- Global platform roles do not replace tenant membership. Global `Admin` is the explicit break-glass exception and must still select an organization.
- Enforce RBAC on backend endpoints.
- Access tokens must remain bound to a live `auth_sessions` row and the current user `token_version`; do not add stateless-token bypasses for tests or tools.
- Password, username, activation, and credential-recovery changes must preserve documented session-revocation behavior.
- Identity audit metadata must never contain plaintext usernames from failed unknown-user logins, passwords, hashes, tokens, or other credentials.
- Cloudflare Access may be an outer authentication gate, but LabGoblin sessions,
  tenant membership, RBAC, ownership, revocation, CSRF, and origin checks remain
  authoritative.
- When Access enforcement is enabled, validate the assertion signature,
  algorithm, issuer, configured application audience, and time claims. Header
  presence or an asserted email/group never grants a LabGoblin role.
- Do not promote Cloudflare client/protocol headers into application identity
  or audit fields. Any future use is limited to the exclusive configured Tunnel
  path; a forwarded address is never proof of identity or authorization.
- Never store a Tunnel token, Access service-token secret, Access assertion, or
  broad Cloudflare API token in git, the database, normal logs, browser storage,
  URLs, or support bundles.
- Cloudflare provisioning API tokens must be accepted only through protected
  files, limited to the selected account/zone, and discarded after use. Persist
  only nonsecret Cloudflare resource IDs.
- Prefer a district IdP group for student Access. The allowed-email-domain
  fallback is explicitly weaker; never substitute an Everyone or Bypass policy.
- Cloudflare publication exposes only the LabGoblin web proxy. Never publish
  Proxmox, SSH, PostgreSQL, Redis, the updater, or lab/management networks.
- Do not add R2 backup support until the backup is complete and client-side
  encrypted and isolated restore testing proves it can recover the application.

## VM/API rules
- VM route identity should use the app database VM id unless explicitly documented otherwise.
- Do not confuse app database VM id with Proxmox VMID.
- Return clean JSON errors.
- Do not fake successful VM, terminal, or protocol behavior.
- Unsupported protocol buttons must be hidden or clearly disabled.
- WEB TERMINAL should prefer Guacamole-first architecture long term.
- ttyd may remain only as fallback/debug if already present.

## Alembic
- Use Alembic for all schema changes.
- Migrations must be idempotent where practical.
- Migrations must be replay-safe.
- Migrations must be branch-safe.
- Do not create multiple Alembic heads.
- Do not destructively alter production data.
- Do not rely on manual `ALTER TABLE` instructions.

## Codex Cloud
- Codex Cloud can inspect repo structure, make safe source changes, run local compile/build checks when dependencies are available, and create PRs.
- Codex Cloud must not claim to validate production nginx, systemd, PostgreSQL state, live Proxmox behavior, live SSE browser behavior, Guacamole/ttyd runtime behavior, or production login.
- PRs must clearly list what was validated in Cloud and what still requires Ubuntu server validation.

## Migration baseline policy
- Current development migration baseline is `20260521_0001`.
- Future migrations must be linear from `20260521_0001`.
- Do not create legacy bridge/merge migrations unless explicitly required.
- Run Alembic head checks before PRs that touch backend models or migrations.
- After any development DB reset, run `backend/scripts/validate_post_reset_state.py`.
- Seed scripts must be idempotent and safe to rerun.
- Seed scripts must not call live Proxmox APIs.
- `CONFIG_ENCRYPTION_KEY` belongs in `backend/.env` or deployment secret stores.
- Never generate encryption keys inside committed migrations.
- Do not rotate `CONFIG_ENCRYPTION_KEY` casually after encrypted tokens are stored.
- Default dev admin may be `admin/admin` only in development.
- Never use `admin/admin` in production.
- `reset_dev_users.py` must never run automatically.
- Do not remove force-password-change behavior globally; only seed dev admin with `force_password_change=false`.

## V2 rebuild invariants
- V2 work belongs on a focused branch, never directly on `main`.
- Unknown or missing roles are denied. Authorization must positively identify an allowed role.
- Student access is always scoped by organization, enrollment, assignment, and resource ownership.
- Do not restore legacy permission-only student provisioning. A student VM must be linked to an effective lab assignment, and every lifecycle or console path must re-check the run window and blueprint access flags.
- Expiring a lab run closes student authorization immediately. Do not claim a Proxmox VM was stopped, reset, or deleted until a durable job verifies it.
- A template must be enabled and assigned before a student can provision it.
- Proxmox mutations are durable jobs with idempotency keys and persisted task identifiers.
- Database record removal and Proxmox resource deletion are separate, explicitly named operations.
- Destructive operations require a preview, an authorization check, an audit record, and a verified result.
- Proxmox, gateway, infrastructure SSH, database, and AI provider secrets never appear in URLs, logs, browser storage, or API responses. Template lab logins have only the audited reveal exception above.
- AI features begin read-only. AI-generated mutations require a human-approved execution plan.
- Configuration belongs in the database when it is operational state. Bootstrap secrets belong in a secret store or protected environment file.
- OpenAPI is the frontend/backend contract. Do not hand-code a second incompatible client contract.
- Documentation and migration changes ship in the same pull request as the behavior they describe.

## VM observations and browser connection maintenance

- Read `docs/operations/consoles.md` and `docs/backend-architecture.md` before changing console or observation paths.
- Resource and agent IP/MAC observations are transient API data, not approved destinations. Never write discovery into `assigned_ip`, approve profiles automatically, or send credentials based on a guest assertion.
- Preserve authorization before Proxmox observation, bounded concurrency/deadlines and explicit partial-failure warnings. Missing values must not become zero or healthy state.
- Keep allocated disk capacity separate from filesystem used/free space and cumulative I/O separate from rates.
- The current default broker is bundled Guacamole guacd, not a planned future feature. SPICE is unsupported and the legacy SSH pilot remains disabled.
- Preserve platform-admin destination approval, pinned guest identity, template/VM login encryption, lab flags and periodic session revalidation. Template login sharing is only the audited reveal exception above.
- Keep independent connection method hints and the preparation panel before the console; test enabled service, policy denial and identity failure separately.
