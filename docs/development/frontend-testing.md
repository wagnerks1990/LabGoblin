# Frontend testing

Frontend validation is layered so inexpensive regressions fail early while
environment-dependent behavior is reported honestly.

## Required pull-request checks

From `frontend/`:

```bash
npm ci
npm test
npm run build
npm audit --audit-level=moderate
```

The Node test suite protects API, security, route-capability, responsive-shell,
accessibility, and design-token contracts without requiring a browser. The
production build catches JSX, import, bundling, and asset failures.

Run the documentation gates from the repository root:

```bash
python scripts/check_branding.py
python scripts/check_repository_hygiene.py
mkdocs build --strict
```

## Development dependency security

Keep the complete `npm audit --audit-level=moderate` gate, including development
dependencies. A production-only audit is useful for attribution, but does not
replace the full gate. Do not use `npm audit fix --force` to introduce an
unreviewed major upgrade.

The October 2026 audit reported nine affected package entries (seven high and
two moderate), including parents affected through their dependencies. All were
development-only; four packages carried the underlying advisory records:

| Package and original version | Dependency chain | Advisory and remediation |
| --- | --- | --- |
| `brace-expansion` 2.1.4 | `openapi-typescript` -> `@redocly/openapi-core` -> `minimatch` | [GHSA-q2hr-2g5m-vwhr](https://github.com/advisories/GHSA-q2hr-2g5m-vwhr), [GHSA-qhr7-859c-m2p7](https://github.com/advisories/GHSA-qhr7-859c-m2p7), [GHSA-6j4f-fj2g-mc7p](https://github.com/advisories/GHSA-6j4f-fj2g-mc7p): resolve 2.1.7, which covers all three fixes. |
| `braces` 3.0.3 | `tailwindcss` -> `chokidar` or `micromatch`; also through `fast-glob` -> `micromatch` | [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm): no published patched version at review time; remove the unused Tailwind dependency chain. |
| `postcss-selector-parser` 6.1.4 | `tailwindcss`, directly and through `postcss-nested` | [GHSA-rj75-hqrm-r3gf](https://github.com/advisories/GHSA-rj75-hqrm-r3gf): patched in 7.1.6; remove the unused Tailwind chain rather than force a transitive major upgrade. |
| `source-map-js` 1.2.1 | `vite` -> `postcss`; previously also through Tailwind's PostCSS tooling | [GHSA-68fv-2mgg-jv7q](https://github.com/advisories/GHSA-68fv-2mgg-jv7q): resolve 1.2.2. |

Tailwind was the only direct dependency among the nine audit entries. It was
not used by application imports, CSS directives, configuration, or the Vite
build. The application uses its authored CSS and shared design tokens; removing
the unused package preserves that pipeline. Its removal also eliminates the
affected `chokidar`, `micromatch`, `fast-glob`, `postcss-nested`, and
`postcss-selector-parser` entries. No advisory is suppressed or accepted.

The two patched versions fit their existing parents' semver ranges and are
recorded in `package-lock.json`. Runtime dependency records remain unchanged.
Use `npm ci`, all frontend tests, the production build, branding and repository
hygiene checks, and the full audit to verify future dependency changes.

## View-state matrix

For every changed data-backed page, validate:

| State | Required result |
| --- | --- |
| Loading | Stable progress message; controls cannot double-submit |
| Empty | Explains what is absent and, where allowed, the next useful action |
| Populated | Primary information and actions follow the page hierarchy |
| Partial failure | Working sections remain usable and the failed section is explicit |
| Unavailable | Error is distinguishable from an empty result and offers safe retry |
| Forbidden | Access-denied view appears; restricted content is not rendered |
| Mutation queued | Durable state is shown without claiming external success |
| Mutation failed | Failure remains visible and retry does not duplicate work |

## Role matrix

Exercise logged-out, student, instructor, tenant administrator/owner, and
platform administrator identities. Check both visible navigation and direct URL
access. The backend remains authoritative even when a link is hidden.

## Responsive matrix

At minimum, test 320 x 568, 390 x 844, 768 x 1024, 1024 x 768, and 1440 x 900.
At each size confirm:

- no page-level horizontal overflow;
- navigation is reachable, dismissible, and keyboard operable;
- focus is not hidden under overlays;
- forms retain labels and understandable grouping;
- destructive actions remain visually distinct;
- data tables either scroll within a labeled region or use an adaptive view;
- console and terminal surfaces fit their container.

## Accessibility review

Use keyboard-only navigation through the shell and every changed workflow.
Confirm the skip link, current-page state, labels, heading order, visible focus,
dialog focus return, live feedback, 200% zoom, and status text. Automated scans
are useful, but they do not replace this review.

## Browser and live-system boundary

The local Node suite and Vite build do not prove browser layout, noVNC, SSE,
WebSocket revocation, proxy behavior, or live Proxmox operations. Record those
results against the tested commit and environment in the
[pre-production acceptance checklist](../operations/preproduction-acceptance.md).

Screenshots used for documentation or visual review must contain deterministic,
sanitized data. Never capture credentials, tokens, private infrastructure
addresses, or identifiable student data.

### Workspace collection and rendering regression tests

`npm test` also runs `workspace-collections.test.js` and
`workspace-render.test.js`. The latter loads the actual JSX primitives with
Vite and renders them through React DOM server to check semantic output and
unknown capacity handling. It does not execute browser effects, layout, or
keyboard interactions. No browser dependency or production authentication
bypass is introduced. See the September evidence in the GUI validation page
for the blocked local-preview attempt and required manual viewport checks.
