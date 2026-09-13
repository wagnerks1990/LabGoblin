# LabGoblin documentation

**Virtual Lab Provisioning & Management**  
**Real Skills. Virtual Machines.**

This documentation is the source of truth for LabGoblin. It is stored with the code so that architectural, operational, security, branding, and user-facing changes can be reviewed and released together.

See [Brand and naming](brand.md) for canonical product identity, colors, terminology, legacy-name migration rules, and requirements for AI/coding agents.

## Current status

LabGoblin is currently an alpha-stage control-plane prototype. Proxmox VE discovery, template import, basic VM lifecycle operations, administrative CRUD, and operational views exist. The application is not yet approved for unsupervised student or production use.

Implemented pilot foundations now include first-admin enrollment, tenant-scoped classroom assignments, atomic VMIDs, leased durable VM operations, expiration cleanup, server-brokered noVNC/SSH, immutable-SHA updates, and database rollback.

The remaining release blockers are:

- complete migration to canonical, default-deny authorization;
- live Proxmox lifecycle and browser-console acceptance testing;
- per-assignment SSH credentials and rotation;
- isolated-network and multi-VM blueprint execution;
- tested off-host backup/restore and TLS deployment;
- separate worker/scheduler scaling and failure drills;
- CSV roster import, extensions, snapshots, reset, and rebuild workflows.

See the [V2 rebuild roadmap](roadmap/v2-rebuild.md) for implementation order.

## Intended users

- **Platform administrators** connect infrastructure and manage global policy.
- **Organization administrators** manage one school or organization.
- **Teachers** create classes and labs and operate their assigned lab resources.
- **Students** access only the labs and resources explicitly assigned to them.

## Core classroom workflow

1. An administrator connects a Proxmox VE cluster with a least-privilege token.
2. An administrator opens Templates to discover the active cluster catalog automatically, reviews enabled templates, and configures placement policy.
3. A teacher creates a class, imports a roster, and defines a lab.
4. LabGoblin creates or allocates isolated resources for students or teams.
5. Students launch their assigned systems through the supported console.
6. The teacher monitors, extends, resets, or ends the lab.
7. Durable workers reconcile and clean up the resources according to policy.

## Documentation ownership

Behavior without documentation is incomplete. Every pull request that changes configuration, authorization, data models, deployment, branding, or a user workflow must update the relevant page in this wiki and, when appropriate, `AI_CONTEXT.md`/`AGENTS.md`.
