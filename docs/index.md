# LabGoblin documentation

**Virtual Lab Provisioning & Management**  
**Real Skills. Virtual Machines.**

This documentation is the source of truth for LabGoblin. It is stored with the code so that architectural, operational, security, branding, and user-facing changes can be reviewed and released together.

See [Brand and naming](brand.md) for canonical product identity, colors, terminology, legacy-name migration rules, and requirements for AI/coding agents. See [Visual rendering reference](design/rendering-reference.md) for the project owner's approved visual direction for future frontend work; it is a design target rather than evidence that every depicted feature exists.

## Current status

LabGoblin is currently an alpha-stage control-plane prototype. Proxmox VE discovery, template import, basic VM lifecycle operations, administrative CRUD, and operational views exist. The application is not yet approved for unsupervised student or production use.

Implemented pilot foundations now include first-admin enrollment, tenant-scoped classroom assignments, atomic VMIDs, leased durable VM operations, expiration cleanup, bundled Guacamole VNC/RDP/SSH, encrypted template guest logins, an editable lab
setup wizard, student My labs home, live VM resource observations, immutable-SHA
updates, and database rollback. See [browser connections](operations/consoles.md).

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
3. A teacher uses the [editable lab wizard](user-guide/instructor-workflow.md) to select class, template/pool, students, access and schedule.
4. Students use [My labs](user-guide/student-workflow.md) to prepare assigned machines through durable jobs.
5. Students connect through an available browser method; RDP/SSH needs guest preparation and administrator approval.
6. Teachers monitor resources, edit unbound assignments, or end runs through reviewed workflows.
7. Durable workers verify lifecycle results. Isolated multi-VM topologies, extensions and rebuild workflows remain roadmap work.


## Documentation ownership

Behavior without documentation is incomplete. Every pull request that changes configuration, authorization, data models, deployment, branding, or a user workflow must update the relevant page in this wiki and, when appropriate, `AI_CONTEXT.md`/`AGENTS.md`.