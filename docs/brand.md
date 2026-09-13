# LabGoblin brand and naming

## Canonical identity

| Item | Value |
| --- | --- |
| Product | **LabGoblin** |
| Category | Virtual Lab Provisioning & Management |
| Primary tagline | **Real Skills. Virtual Machines.** |
| Campaign line | **Build. Deploy. Learn. Repeat.** |
| Alternate campaign line | Virtual Labs. Real Opportunities. |
| Technical identifier | `labgoblin` |
| Service prefix | `labgoblin-` |
| Install root | `/opt/labgoblin` |
| State root | `/var/lib/labgoblin` |
| Session cookie | `labgoblin_session` |
| Repository | `https://github.com/wagnerks1990/labgoblin.git` |

LabGoblin is the product. Proxmox VE is currently the primary hypervisor integration and should be named only where the underlying platform matters technically.

## Positioning

LabGoblin gives instructors and students a controlled layer over virtual lab infrastructure. It covers templates, assignments, lab runs, provisioning, lifecycle operations, access policy, reconciliation, and auditing without exposing broad hypervisor access to students.

In the broader Goblin product family:

- **RoomGoblin** manages classrooms and physical labs.
- **LabGoblin** manages virtual labs and student virtual environments.
- **PatchGoblin** is reserved for patch/update management.
- **ScreenGoblin** is reserved for digital signage.

Avoid copy that makes these products sound interchangeable.

## Voice

LabGoblin should sound technical, capable, approachable, education-first, and slightly playful. Use direct language. The goblin identity adds personality; it must not reduce clarity around security, destructive actions, permissions, or operational status.

## Color system

| Token | Hex | Purpose |
| --- | --- | --- |
| Goblin Green | `#22C55E` | Primary brand/action |
| Deep Space | `#0B1220` | Main dark background |
| Slate Surface | `#1F2937` | Cards/panels |
| Steel Secondary | `#3B4754` | Secondary UI |
| Cloud Light | `#E5E7EB` | Light neutral/text |
| Mint Accent | `#A7F3D0` | Success/highlight |
| White | `#FFFFFF` | High-contrast text |

Green should identify primary actions, active state, success, and brand emphasis. Do not flood large UI surfaces with saturated green. Never rely on green alone to communicate state; use text and/or an icon as well.

## Typography

- Preferred UI/body: **Inter**.
- Optional display/marketing: **Poppins**.
- Fallback: `system-ui, "Segoe UI", Arial, sans-serif`.

Font binaries are not stored in the repository. Use properly licensed sources if web fonts are added later.

## Interface system

The authenticated interface uses a quiet dark workspace with restrained green
emphasis. Content, not decoration, owns the visual hierarchy.

- Use the shared spacing, radius, surface, text, border, shadow, and motion
  tokens in `frontend/src/styles.css`; do not add arbitrary inline colors.
- Use bounded page content, clear page headings, and progressive disclosure for
  advanced infrastructure controls.
- Reserve the strongest green for the current destination and primary action.
- Secondary actions use neutral surfaces. Destructive actions use the danger
  treatment and explicit action text.
- PASS, WARN, FAIL, queued, running, and unavailable states use a shared badge
  or alert treatment with visible text. Color is supplemental.
- Controls use a consistent height and retain at least a 44 by 44 CSS pixel
  pointer target in compact layouts.
- Focus indicators must remain visible against every surface.

The desktop shell groups destinations by workflow. Compact layouts use a
header, off-canvas menu, and role-aware bottom navigation. Responsive behavior
must not remove access to an allowed destination or expose one the role cannot
use.

## Content guidance

- Prefer action names such as **Create VM**, **End run**, and **Check for
  updates** over vague labels.
- Explain technical identifiers such as VMID and UPID where they first appear.
- Use sentence case for headings and controls.
- Empty states say what is absent and, when appropriate, what to do next.
- Errors state what failed without exposing secrets or pretending the result was
  successful.

## Logo and icon

The canonical application icon is `frontend/public/brand/labgoblin-icon.svg`.

Rules:

- Do not stretch, skew, or rotate the logo.
- Keep adequate clear space around the mark.
- Do not recolor the green mark arbitrarily.
- Do not use decorative glow/shadow effects where they reduce legibility.
- Use accessible `alt` text when the mark communicates identity; use empty `alt` text when adjacent text already says LabGoblin.

## Clean-install naming policy

This repository is development software intended for fresh installations. LabGoblin-owned runtime and developer identifiers use LabGoblin naming directly; predecessor compatibility aliases are not required.

Canonical examples:

- repository: `wagnerks1990/labgoblin`
- Compose project: `labgoblin`
- PostgreSQL default database/user: `labgoblin`
- updater group and unit: `labgoblin-updater` / `labgoblin-updater.service`
- updater executable: `/usr/local/lib/labgoblin-updater.py`
- host runner: `labgoblin-runner`
- host helper: `/usr/local/sbin/labgoblin-asset-server`
- asset units: `labgoblin-iso-server.service` and `labgoblin-ct-template-server.service`
- logger namespace: `labgoblin`
- frontend package: `labgoblin-frontend`

Do not introduce LabGoblin-owned identifiers using predecessor forms such as `proxmox-lab-platform`, `proxmox_lab`, `plp_`, or `proxmox-lab-*`.

## Legitimate Proxmox terminology

Do not mechanically remove the word Proxmox. These names describe the supported hypervisor integration and should remain when technically accurate:

- `PROXMOX_*` configuration variables;
- `ProxmoxCluster`, `ProxmoxNode`, and other integration models;
- Proxmox API clients, URLs, token concepts, VMIDs and UPIDs;
- Proxmox Setup, Inventory, Assets, and integration documentation;
- database tables whose domain object is specifically a Proxmox resource.

The distinction is ownership: LabGoblin-owned runtime names use LabGoblin; integration-domain names use Proxmox where appropriate.

## Repository naming

The canonical GitHub repository is `wagnerks1990/labgoblin`. Active installer, updater, MkDocs, documentation, automation, test, and AI-agent references must point to the canonical repository and must not rely on GitHub redirects from the retired repository path.

## AI/coding-agent contract

Agents must read `AI_CONTEXT.md`, `AGENTS.md`, and this file before branding or infrastructure changes. Agents must keep documentation synchronized and must not weaken authorization, tenant isolation, secret handling, auditability, durable operations, update safety, or rollback behavior for the sake of rebranding.

The workspace rebuild applies this identity to the overview hero, sign-in,
page finder, classroom guidance, provisioning review, and empty/loading states.
Resource cards and collections use shared token colors, line icons, and the
canonical SVG mark. Do not replace real resource state with decorative metrics.
