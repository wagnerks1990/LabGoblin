# LabGoblin visual rendering reference

## Status

This document records the approved visual direction selected by the project owner from the September 2026 LabGoblin concept renderings. It is a **design reference**, not evidence that every illustrated control, metric, integration, or workflow is implemented.

Future frontend work should use this reference together with `docs/brand.md`, `docs/frontend-architecture.md`, `AGENTS.md`, and `AI_CONTEXT.md`. Security, authorization, accessibility, truthful operational state, and existing product contracts take precedence over a rendering when they conflict.

## Approved direction

The approved renderings establish a modern education-focused virtual-lab workspace with:

- a dark, persistent application/navigation shell on desktop;
- light, high-clarity content surfaces for dense operational information;
- restrained LabGoblin brand accents rather than large saturated brand-color surfaces;
- simple cards for student labs and templates;
- clear status badges that always include text and never rely on color alone;
- concise dashboards with real resource and activity data rather than decorative metrics;
- prominent direct actions such as **Connect**, **Start**, **Create VM**, and **Use template** only when the authenticated user's capabilities permit them;
- a focused browser-console experience where the remote desktop is the dominant surface;
- responsive layouts that simplify progressively for tablets and phones.

The renderings are conceptual. Labels and navigation must follow the canonical application information architecture rather than copying generated artwork literally.

## Canonical brand translation

Concept artwork may contain blue or purple accent treatments. Those are **not new canonical brand colors**. Implementation must translate the visual composition into the repository's established LabGoblin palette:

- Goblin Green `#22C55E` — primary action, active state, success, brand emphasis;
- Deep Space `#0B1220` — primary dark shell/background;
- Slate Surface `#1F2937` — dark cards and panels;
- Steel Secondary `#3B4754` — secondary controls/surfaces;
- Cloud Light `#E5E7EB` — light neutral/text;
- Mint Accent `#A7F3D0` — success/highlight;
- White `#FFFFFF` — high-contrast text/surfaces where appropriate.

Use the canonical SVG at `frontend/public/brand/labgoblin-icon.svg`. Generated mascot/logo variants in concept artwork are inspiration only and must not replace the canonical mark without an explicit branding change.

## Screen references

### Sign in

Use a visually simple, branded sign-in experience. Keep authentication choices truthful to the configured deployment. Do not add provider buttons merely because a rendering depicts them. A school/lab visual treatment may support the page, but the form must remain accessible and usable at compact widths.

### Overview / dashboard

The dashboard should prioritize information that helps the current role act: assigned or managed VMs, active/running state, capacity when genuinely known, recent durable operations, warnings/failures, and role-appropriate shortcuts. Never invent utilization, health, activity, user, or uptime values to reproduce a mockup.

### My labs / student home

The student experience should remain deliberately simpler than the administrative workspace. Assigned labs should be presented as readable cards with state, essential resource information, and the next valid action. **Connect** is the primary action when a connection is actually available. Start/provision actions remain subject to enrollment, assignment, run-window, template, and ownership policy.

### Lab VMs

Administrative VM management may use a table or card/list presentation depending on viewport and task density. Preserve search/filtering, visible identity, observed resource information, durable lifecycle operations, explicit destructive-action confirmation, and truthful partial/unknown state.

### Templates

Templates should be visually scannable and show useful identity/platform information. A template being present or enabled does not imply student authorization. Classroom assignment and policy remain separate.

### Classes and guided setup

Use clean, step-oriented teaching workflows instead of exposing raw infrastructure configuration unnecessarily. The current five-step guided setup remains authoritative: lab/class, machines, students, access/schedule, review.

### Browser console

The remote guest display should occupy most of the available workspace. Keep connection state and essential controls understandable without overwhelming the session. The actual connection preparation, method availability, identity checks, and server-side authorization defined in `docs/operations/consoles.md` remain authoritative.

### Reports / operations

Charts and summary cards should only visualize real backend data with clearly defined meaning. Operations remains the source for durable-operation state, warnings, failures, task details, and history. Do not convert unknown or failed data retrieval into a healthy zero.

## Responsive interpretation

Use the rendering composition as a desktop visual target, not a fixed canvas. Preserve the frontend responsive contract:

- 320–479 px: off-canvas navigation, one-column content, full-width primary controls;
- 390 × 844: touch-friendly phone experience;
- 768 × 1024: tablet/adaptive grids;
- 1024 × 768: small desktop;
- 1440 × 900: persistent grouped navigation and bounded content.

No page-level horizontal scrolling is acceptable at 320 CSS pixels. Dense tables must become readable cards or use a clearly labeled local scroll region.

## Design hierarchy

When implementing or reviewing a screen, resolve conflicts in this order:

1. Security, authorization, tenant isolation, secret handling, and truthful operational state.
2. Accessibility and responsive requirements.
3. Existing documented workflow and API contracts.
4. Canonical LabGoblin brand tokens and navigation architecture.
5. This rendering reference's layout, density, visual hierarchy, and interaction inspiration.
6. Incidental generated-art details.

Generated text, dates, counts, logos, OS names, provider buttons, charts, and example data in concept artwork are not product requirements by themselves.

## AI and contributor instruction

AI/coding agents should treat this document as the approved **visual target** for frontend changes. Before materially changing the UI, compare the proposed experience against it and document intentional deviations. Do not blindly reproduce generated artwork. Reuse existing components and tokens, preserve backend authorization as authoritative, and keep screenshots/help/documentation synchronized with implemented behavior.

When visual screenshots are added to the repository, place sanitized approved captures or source design assets under `docs/design/` and link them from this page. Do not commit secrets, real student information, school infrastructure details, guest credentials, tokens, or screenshots containing sensitive production data.
