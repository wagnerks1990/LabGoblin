# Changelog

LabGoblin has not published a supported production release. Until versioned
releases begin, material changes are recorded in pull requests and this file.

## Unreleased

- Fixed Proxmox bootstrap on servers returning HTTP 500 for nonexistent roles or users by discovering identities through collection endpoints.

- Re-enabled Proxmox root bootstrap as a one-time, secure-context workflow that
  creates and validates a fixed least-privilege `labgoblin@pve` service user,
  role, and token without storing the root password or creating a root token.
- Added an optional, disabled-by-default Cloudflare Tunnel deployment profile,
  restricted token-file setup helper, loopback origin binding, and opt-in
  Cloudflare Access JWT validation while preserving LabGoblin sessions and RBAC.
- Added Cloudflare DNS/TLS, cache, WAF, rate-limit, SSE/WebSocket, rotation,
  outage recovery, rollback, and acceptance guidance. R2 backup support remains
  deliberately deferred pending complete encrypted backups and tested restores.
- Added guided, idempotent Cloudflare provisioning with protected file-based API
  credentials, reviewed plan/apply workflow, local JSON status, least-privilege
  district IdP group policy, DNS-last publication, nonsecret resource state,
  connector health gating, and fail-closed disable behavior for safe at-home
  student access.
- Rebuilt the frontend around a responsive, role-aware application shell,
  simplified workflow navigation, reusable interface primitives, labeled forms,
  adaptive data regions, and explicit loading/error/empty states.
- Added GUI architecture, role-based user guides, responsive and accessibility
  acceptance matrices, and structural regression coverage for the rebuild.
- Pre-production security, tenant-isolation, durable-operation, deployment,
  frontend reliability, validation, and documentation hardening is in progress.
- Removed unreachable placeholder route modules and an unused 7.5 MB archive of
  decompiled third-party Deskpool reference code from the active source tree.
- The product remains alpha until every required gate in
  `docs/operations/preproduction-acceptance.md` has a recorded passing result.
