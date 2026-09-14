# Frontend architecture

LabGoblin's frontend is a React and Vite single-page application. It presents
the same control-plane API through role-appropriate workflows; it is not an
authorization boundary. Every operation remains authorized by the backend.
Student, instructor, tenant-administrator, and platform-administrator views use
the same shell with different capability-filtered destinations.

## Information architecture

The application shell separates routine lab work from administration:

- **Workspace** provides the overview, assigned VMs, student provisioning, and
  durable-operation activity.
- **Teaching** contains classes, sessions, pools, and classroom events for
  instructors and tenant administrators.
- **People & access** contains organization, user, and group administration for
  the applicable tenant or platform role.
- **Platform administration** contains infrastructure, templates, users,
  organizations, telemetry, troubleshooting, and updates for platform admins.

Navigation visibility is derived from the authenticated platform role and the
selected organization's tenant role. Hiding a link never replaces a backend
authorization check. Direct navigation to a disallowed route must render the
access-denied state.

## Structure

- `pages/` contains route-level workflow containers.
- `layouts/` contains the application shell and navigation.
- `components/` contains reusable presentation and interaction primitives.
- `components/operational/` contains shared status and activity views.
- `services/` contains API adapters.
- `hooks/` contains stateful browser and streaming logic.
- `auth/` contains capability derivation and authentication-state helpers.
- `state/` contains external stores used by live operational views.
- `styles.css` contains tokens and shared responsive primitives.
- `generated/` contains generated OpenAPI types and is never edited manually.

Page containers own data loading and workflow orchestration. Repeated form,
status, table, toolbar, dialog, and empty/error/loading patterns belong in
shared components. API access must continue through the `/api` client.

## Responsive contract

The interface must work without page-level horizontal scrolling at a 320 CSS
pixel viewport. The supported validation widths are:

| Mode | Validation viewport | Expected behavior |
| --- | --- | --- |
| Compact phone | 320 to 479 px | Off-canvas navigation, one-column content, full-width primary controls |
| Phone | 390 x 844 | Touch-friendly actions and stacked detail views |
| Tablet | 768 x 1024 | Compact navigation and adaptive grids |
| Small desktop | 1024 x 768 | Persistent shell where space permits |
| Desktop | 1440 x 900 | Persistent grouped navigation and bounded readable content |

Dense tables must be placed in a labeled scroll container or transformed into
readable cards. Controls may wrap, but primary and destructive actions must not
become ambiguous. Console canvases and terminals resize to their container.

## Accessibility contract

- Use one page-level `h1` and preserve heading order.
- Provide a keyboard-visible skip link to the main content.
- Identify the current navigation destination with `aria-current="page"`.
- Give every input a persistent accessible name; placeholders are examples,
  not labels.
- Mobile navigation exposes its expanded state and closes with Escape, after
  route selection, and when the viewport leaves compact mode.
- Modal dialogs have a name, deliberately manage focus, close with Escape when
  safe, and return focus to their trigger.
- Status changes use `role="status"`; failures requiring attention use
  `role="alert"`.
- Focus indicators, disabled state, and status meaning never depend on color
  alone.
- Pointer targets are at least 44 CSS pixels in compact layouts.
- Motion honors `prefers-reduced-motion`.

## View state contract

Every data-backed view distinguishes loading, empty, error, and populated
states. An unavailable API must never silently appear as an empty successful
list. Mutations expose a busy state, prevent duplicate submission, preserve the
server's error detail when safe, and announce the result.

Durable VM operations remain visibly queued or running until the backend
reports a terminal result. The frontend must not invent successful Proxmox
state. Destructive operations retain their server-provided preview and exact
confirmation contract.

## Security boundaries

- Session JWTs remain in HttpOnly cookies.
- Organization selection may be stored locally; credentials, tickets, secrets,
  and reusable grants may not.
- Proxmox and console tickets never appear in browser URLs or frontend state.
- Cookie-authenticated mutations and WebSockets remain same-origin.
- The connection page enables Guacamole SSH only after VM, assignment, guest
  profile and server-identity checks pass. The legacy SSH pilot remains disabled.
  See [Browser connections](operations/consoles.md) for the integrated gateway.

## Testing layers

Dependency-free source-contract tests protect security and structural
invariants. Rendered component and browser tests should cover behavior that
source inspection cannot prove. See [Frontend testing](development/frontend-testing.md)
and [GUI validation](gui-section-validation.md).

## Branded workspace rebuild (September 2026)

The shared shell now includes **Find a page** (`Ctrl+K` / `Cmd+K`), backed by
exactly the same role-aware navigation model as the sidebar. The native dialog
supports Escape, keyboard navigation, and focus return. It navigates pages;
it does not search private backend resources or grant additional permissions.

- **Overview:** canonical LabGoblin mark, both taglines, role-specific workflow
  links, VM counts, cluster capacity meters, and explicit unknown capacity data.
- **Lab VMs:** search name/VMID/node/IP, status filtering, name/VMID sorting,
  card/list layouts, visible resource identity, refresh-all, and existing verified
  lifecycle actions with destructive details kept behind disclosure.
- **Templates:** branded cards or table, enabled/disabled filters, discovery,
  source node/VMID, and links into classroom assignment. Enabling a catalog
  template does not itself authorize student provisioning.
- **Operations:** newest-first history, combined search/action/state filters,
  separate warnings and failures, summary counts, and expandable full errors.
  History is retained and existing active-job polling remains authoritative.
- **Provision:** selection plus a review panel showing template, name prefix,
  provisioning mode, and automatic start. Existing assignment and durable-job
  enforcement still applies.
- **Pools:** searchable management, linked detail pages, a collapsible create/edit
  form, duplicate-save protection, and latest requested readiness results.
- **Classroom:** counts and step guidance; dependent roster/assignment failures
  are shown explicitly and stale responses are ignored.
- **Inventory:** categories for machines/templates, networks/storage, and media;
  the template-catalog link now targets `/admin/templates`.
- **Sign-in and workflow states:** shared LabGoblin branding and a consistent
  visual treatment using existing tokens, without external fonts or image hosts.

Shared composition lives in `WorkspaceKit.jsx`; appearance in `workspace.css`;
collection selection logic in `workspaceCollections.js`. Public branding stays
at `/brand/labgoblin-icon.svg`. No API schema, backend authorization, database
migration, or console transport was changed by this rebuild.

## Guided setup and student home

The teaching entry now uses a five-step editable setup wizard: lab/class,
machines, students, access/schedule, and review. It reuses existing resources or
creates linked classroom records atomically. New accounts remain platform-admin
only. Saved drafts reopen through Edit setup; unsaved password fields remain
memory-only. Detailed classroom management remains available for shared
blueprints and destructive run actions. Students land on My labs with
instructions, start/provision, browser Connect, and approved guest-login reveal.

Validation covers atomic rollback, replay, stale edits, linked-VM protection,
role and tenant boundaries, enrollment availability, wizard validation, and the
production frontend build. Browser visual/keyboard validation at 320, 390, 768,
1024, and 1440 CSS pixels remains a required deployment check; no live browser
or Proxmox classroom result is claimed from these local tests.

## VM observations and connection guidance

`VmResources.jsx` is shared by VM cards, student machine details and connection
details. Formatting lives in `vmResources.js`; zero is distinct from missing
values, sizes use binary units, IPs wrap, and observed IPs participate in search.
The student home suppresses overlapping refreshes. VM details use application
VM ids and the normal authorized API, not direct Proxmox calls.

`ConnectVmPage.jsx` displays per-method `method_hints`, places guest preparation
above VNC, preserves the saved service port, and reselects the preferred verified
method after saving. Only the server's `can_configure` capability exposes the
platform-admin preparation form. Backend authorization remains authoritative.
Connected/connecting badges use success/pending states. The canonical setup and
limits are in [browser connections](operations/consoles.md).
