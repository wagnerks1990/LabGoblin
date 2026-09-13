# GUI validation

Validate the responsive interface against a disposable or isolated environment.
Never use production credentials, student data, or an unmanaged Proxmox cluster
for destructive checks.

Record the date, tester, commit SHA, browser version, viewport, environment, and
result. Screenshots must be sanitized before retention.

## Viewports

Run each changed workflow at these representative sizes:

| Viewport | Navigation expectation |
| --- | --- |
| 320 x 568 | Compact drawer and bottom navigation; no page-level overflow |
| 390 x 844 | Touch-friendly phone layout |
| 768 x 1024 | Tablet layout without clipped actions |
| 1024 x 768 | Desktop shell and readable dense data |
| 1440 x 900 | Bounded desktop content and persistent grouped navigation |

At every size, zoom to 200%, traverse the page by keyboard, and confirm that
focus remains visible. A table may scroll inside its labeled region; the whole
application must not require horizontal scrolling.

## Public and identity states

- First-run setup has visible labels, password confirmation, busy state, and an
  announced failure state.
- Sign-in works by keyboard and distinguishes invalid credentials from an
  unavailable API.
- Forced password change prevents access to the normal shell until complete.
- Logout failure leaves the authenticated interface active and explains that
  the server session remains open.
- Session expiry or revocation returns to sign-in without exposing protected
  page data.

The development-only `admin/admin` account exists only when an operator
explicitly runs the documented development seed. It is never an appliance or
production default.

## Shell and navigation

- The skip link moves focus to `#main-content`.
- The current destination has an active visual state and
  `aria-current="page"`.
- Desktop navigation can collapse without losing destination names for assistive
  technology, and its preference survives reload.
- The compact drawer reports its expanded state, traps focus, prevents
  background scrolling, and closes on Escape, backdrop selection, or route
  selection before returning focus to its trigger.
- Mobile bottom navigation offers three role-appropriate primary destinations
  and a More action.
- Organization switching updates tenant data without a full browser reload.
- Sign-out and account security remain reachable without searching the full
  navigation tree.

## Role matrix

| Identity | Expected workspace |
| --- | --- |
| Student | Dashboard, Lab VMs, Create VM, Operations, Account Security |
| Instructor | Dashboard, Lab VMs, Operations, classroom, pools, sessions, events |
| Tenant admin/owner | Instructor destinations plus Groups |
| Platform admin | Operational and platform-administration destinations; no implied tenant membership |

For each identity, paste a restricted URL directly into the address bar. The
route must show access denied, not restricted content. Repeat after membership
removal, organization disablement, and role change.

## Student workflow

1. Open **Create VM** and verify active assignments and approved templates.
2. Submit once and confirm the UI reports queued provisioning rather than
   immediate Proxmox success.
3. Follow progress in **Operations** and **My Lab VMs**.
4. Exercise allowed start, stop, reboot, refresh, and console actions.
5. Verify prohibited actions are absent or unavailable with explanatory text.
6. Review and cancel a deletion, then repeat with the exact server preview and
   verify durable completion.

## Instructor workflow

1. Create/select a class and manage its roster.
2. Build a lab blueprint from an enabled pool.
3. Create and schedule or activate a lab run.
4. Assign the active roster and exercise permitted bulk VM actions.
5. Verify loading, empty, error, and populated states for sessions and events.
6. Review the run-close preview, cancel once, then confirm and follow verified
   cleanup in Operations.

## Platform administration

1. Validate a canonical HTTPS Proxmox cluster with TLS verification enabled.
2. Review readiness, inventory, templates, storage, networks, and assets.
3. Import an approved template and confirm it becomes available to policy.
4. Exercise organization, membership, user, group, and session-management
   states with sanitized identities.
5. Check telemetry and troubleshooting during healthy, empty, partial-failure,
   and unavailable states.
6. Check update, apply, failed-health recovery, and rollback presentation without
   bypassing the protected updater workflow.

Raw Proxmox inventory uses node and VMID identity. App-managed lab VMs use
`student_vms.id`; the interface must not present those identifiers as
interchangeable.

## Console and live data

- noVNC fits after viewport and orientation changes.
- Connection state is announced and reconnect, expiry, logout, and revocation
  terminate or recover as documented.
- The SSE indicator distinguishes connected, retrying, expired, and failed
  states through the deployed proxy.
- Proxmox tickets, JWTs, credentials, private keys, and reusable passwords are
  absent from URLs, storage, responses, diagnostics, and screenshots.
- SSH terminal controls remain hidden while the feature is disabled.

## September 2026 workspace rebuild evidence

Automated checks cover combined VM search/status/sort, operation action/state/
warning filters, stable source arrays, rendered null-versus-zero capacity,
escaped metric content, and labeled search/layout controls. Existing role and
security contracts remain in the frontend suite. These tests are not browser
layout or interaction tests.

Cloud Browser could not open the local fixture preview: `ERR_BLOCKED_BY_CLIENT`.
No screenshots or successful visual checks are claimed for this iteration.
Before general rollout, validate sanitized student, instructor, tenant admin,
and platform admin sessions at **320, 390, 768, 1024, 1440 CSS pixels**:

1. Find a page via button and Ctrl/Cmd+K; search, Tab, Enter, Escape, focus return.
   Restricted routes must remain absent for each role.
2. Toggle Cards/List, combine search and status, reset filters, and verify resource
   identity and lifecycle controls. Check long VM names and error text.
3. Filter successful operations with warnings separately from failed history;
   expand full failure details and confirm active operations still update.
4. Create/edit/cancel a pool, search pools, open its details, and check readiness.
5. Review assignment and instructor provisioning before submitting one disposable
   VM; confirm server-verified result, power controls, and delete preview.
6. Check populated, empty, loading, error, and forbidden states. Failed discovery
   must not appear as a healthy cluster. Missing capacity must not display 0%.
7. Check page overflow, compact header/drawer, bottom navigation, keyboard focus,
   sign-in, tenant switching, and live feedback. Console connectivity still
   requires separate Ubuntu/Proxmox verification.
