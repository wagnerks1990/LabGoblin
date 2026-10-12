# Dependency security remediation — 2026-10-12

## Scope and audit counting

Audits were reproduced from main commit `4eba9580ee2ead572c85ac04737efbb5d960e640` in the isolated cloud development environment. Installed Python packages had 20 distinct advisories: 14 in PyJWT 2.13.0 and six in pip 25.0.1. Resolving the runtime and development manifests produced the same 14 PyJWT advisories; pip is an environment installer rather than a runtime dependency. The frontend lockfile had nine affected package entries (seven high, two moderate), representing seven distinct root advisories (five high, two moderate). Parent entries are dependency propagation, not additional vulnerabilities.

Each pip-audit record is counted once using its GHSA identifier; CVE and PYSEC aliases below identify that same record. References to earlier vulnerabilities in advisory descriptions are not aliases. npm records are deduplicated by GHSA URL; propagated string entries are not counted as new advisories. Severity comes from the GitHub advisory, not the number of aliases or the number of affected parents.

## Python findings

| Package/version | PYSEC | CVE | GHSA | Severity | First recorded fix |
| --- | --- | --- | --- | --- | --- |
| pip 25.0.1 | PYSEC-2026-196 | CVE-2026-8643 | [GHSA-wf93-45jw-7689](https://github.com/advisories/GHSA-wf93-45jw-7689) | moderate | 26.1.2 |
| pip 25.0.1 | PYSEC-2026-1795 | CVE-2025-8869 | [GHSA-4xh5-x5gv-qwph](https://github.com/advisories/GHSA-4xh5-x5gv-qwph) | moderate | 25.3 |
| pip 25.0.1 | PYSEC-2026-1796 | CVE-2026-1703 | [GHSA-6vgw-5pg2-w6jp](https://github.com/advisories/GHSA-6vgw-5pg2-w6jp) | low | 26.0 |
| pip 25.0.1 | PYSEC-2026-2875 | CVE-2026-3219 | [GHSA-58qw-9mgm-455v](https://github.com/advisories/GHSA-58qw-9mgm-455v) | moderate | 26.1 |
| pip 25.0.1 | PYSEC-2026-2876 | CVE-2026-6357 | [GHSA-jp4c-xjxw-mgf9](https://github.com/advisories/GHSA-jp4c-xjxw-mgf9) | moderate | 26.1 |
| pip 25.0.1 | PYSEC-2026-3721 | CVE-2026-13346 | [GHSA-qwm4-qh6w-59xr](https://github.com/advisories/GHSA-qwm4-qh6w-59xr) | moderate | 26.2 |
| pyjwt 2.13.0 | PYSEC-2026-4145 | CVE-2026-102268 | [GHSA-ffc3-869f-jxw9](https://github.com/advisories/GHSA-ffc3-869f-jxw9) | critical | 2.14.0 |
| pyjwt 2.13.0 | PYSEC-2026-4146 | CVE-2026-103001 | [GHSA-gvp8-978c-rx2q](https://github.com/advisories/GHSA-gvp8-978c-rx2q) | moderate | None recorded |
| pyjwt 2.13.0 | PYSEC-2026-4149 | CVE-2026-102271 | [GHSA-p4g4-x82p-q773](https://github.com/advisories/GHSA-p4g4-x82p-q773) | high | 2.14.0 |
| pyjwt 2.13.0 | PYSEC-2026-4152 | CVE-2026-102274 | [GHSA-w6j9-cwv2-h6wq](https://github.com/advisories/GHSA-w6j9-cwv2-h6wq) | moderate | 2.14.0 |
| pyjwt 2.13.0 | PYSEC-2026-4144 | CVE-2026-102267 | [GHSA-9v7f-9g4p-ffgj](https://github.com/advisories/GHSA-9v7f-9g4p-ffgj) | high | 2.14.0 |
| pyjwt 2.13.0 | PYSEC-2026-4143 | CVE-2026-102266 | [GHSA-9j54-fg26-wv3r](https://github.com/advisories/GHSA-9j54-fg26-wv3r) | high | 2.14.0 |
| pyjwt 2.13.0 | PYSEC-2026-4148 | CVE-2026-102270 | [GHSA-jwrc-g2q2-pq5p](https://github.com/advisories/GHSA-jwrc-g2q2-pq5p) | moderate | 2.14.0 |
| pyjwt 2.13.0 | PYSEC-2026-4140 | CVE-2026-101917 | [GHSA-2gx3-rcp4-g85q](https://github.com/advisories/GHSA-2gx3-rcp4-g85q) | moderate | 2.14.0 |
| pyjwt 2.13.0 | PYSEC-2026-4141 | CVE-2026-101918 | [GHSA-42vr-xj54-vc7v](https://github.com/advisories/GHSA-42vr-xj54-vc7v) | moderate | 2.15.0 |
| pyjwt 2.13.0 | PYSEC-2026-4147 | CVE-2026-102269 | [GHSA-hxm8-2xgr-2p9m](https://github.com/advisories/GHSA-hxm8-2xgr-2p9m) | moderate | 2.14.0 |
| pyjwt 2.13.0 | PYSEC-2026-4151 | CVE-2026-102273 | [GHSA-w2cx-738m-mc7w](https://github.com/advisories/GHSA-w2cx-738m-mc7w) | high | 2.14.0 |
| pyjwt 2.13.0 | PYSEC-2026-4150 | CVE-2026-102272 | [GHSA-r6x4-923q-g947](https://github.com/advisories/GHSA-r6x4-923q-g947) | high | 2.14.0 |
| pyjwt 2.13.0 | PYSEC-2026-4142 | CVE-2026-102265 | [GHSA-8wjv-2p76-3863](https://github.com/advisories/GHSA-8wjv-2p76-3863) | moderate | 2.14.0 |
| pyjwt 2.13.0 | PYSEC-2026-4183 | CVE-2026-102275 | [GHSA-x33g-cr3x-6449](https://github.com/advisories/GHSA-x33g-cr3x-6449) | moderate | 2.15.0 |

PyJWT is a direct runtime dependency with the crypto extra; both the API and Cloudflare Access use it. 2.15.0 is the smallest release covering the recorded 2.14.0 fixes plus the payload recursion and OKP key consistency fixes. Python 3.12 and installed cryptography 50.0.2 satisfy its requirements. No other runtime Python versions changed. pip 26.2 is the smallest release covering all six installer advisories and is now pinned in development requirements. The tar extraction advisory is additionally mitigated by the existing Python 3.12 runtime (PEP 706); this does not excuse the other pip findings.

The options-mutation advisory (`PYSEC-2026-4146`, moderate) has no recorded fixed release in the advisory feed. The affected range ends at 2.13.0. Direct regression testing on 2.15.0 confirms caller options stay unchanged and a subsequent verified decode rejects expiration. Neither application verification path shares an unverified options dictionary. The post-upgrade audit reports zero findings; this discrepancy is documented rather than assigning an invented fix version.

## Frontend findings and dependency paths

| Affected package | Locked version | Path / cause | Resolution |
| --- | --- | --- | --- |
| brace-expansion | 2.1.4 | openapi-typescript → @redocly/openapi-core → minimatch → brace-expansion | Patch to 2.1.7 (minimatch allows ^2.0.1) |
| braces | 3.0.3 | tailwindcss → chokidar / micromatch → braces | Remove unused Tailwind dependency; no published braces 3.x fix |
| chokidar | 3.6.0 | tailwindcss → chokidar → braces | Removed with Tailwind |
| micromatch | 4.0.8 | tailwindcss → micromatch → braces | Removed with Tailwind |
| fast-glob | 3.3.3 | tailwindcss → fast-glob → micromatch → braces | Removed with Tailwind |
| postcss-nested | 6.2.0 | tailwindcss → postcss-nested → postcss-selector-parser | Removed with Tailwind |
| postcss-selector-parser | 6.1.4 | tailwindcss direct and via postcss-nested | Removed with Tailwind (recorded fix 7.1.6) |
| source-map-js | 1.2.1 | vite → postcss → source-map-js (also previously via Tailwind) | Patch to 1.2.2 within ^1.2.1 |
| tailwindcss | 3.4.19 | Parent propagation of braces and selector parser findings | Remove unused declaration instead of major migration to 4.3.3 |

Distinct frontend advisories:

- [GHSA-q2hr-2g5m-vwhr](https://github.com/advisories/GHSA-q2hr-2g5m-vwhr): brace-expansion, moderate, affected `>=2.0.0 <2.1.7`; brace-expansion: Quadratic-time expansion of the `{a},b}` rewrite causes CPU denial of service.
- [GHSA-qhr7-859c-m2p7](https://github.com/advisories/GHSA-qhr7-859c-m2p7): brace-expansion, high, affected `>=2.0.0 <2.1.6`; brace-expansion: DoS via uncontrolled recursion on nested brace groups causing stack exhaustion.
- [GHSA-6j4f-fj2g-mc7p](https://github.com/advisories/GHSA-6j4f-fj2g-mc7p): brace-expansion, high, affected `>=2.0.0 <2.1.5`; brace-expansion: DoS via uncontrolled recursion in parseCommaParts causing stack exhaustion.
- [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm): braces, high, affected `<=3.0.3`; braces vulnerable to stack-exhaustion denial of service through deeply nested patterns.
- [GHSA-rj75-hqrm-r3gf](https://github.com/advisories/GHSA-rj75-hqrm-r3gf): postcss-selector-parser, moderate, affected `<7.1.6`; PostCSS: Quadratic complexity in flat selector parsing allows CPU exhaustion.
- [GHSA-68fv-2mgg-jv7q](https://github.com/advisories/GHSA-68fv-2mgg-jv7q): source-map-js, high, affected `>=1.0.0 <1.2.2`; source-map-js allows event-loop denial of service through indexed source-map section offsets.

The project uses ordinary CSS. Repository search found no Tailwind configuration, plugin, directives, or source usage. Removing Tailwind removes 63 lockfile entries without changing application code. The only retained packages changing version are brace-expansion and source-map-js. No force upgrade or new override was used; the existing js-yaml override is preserved. All three production JS/CSS assets remain byte-for-byte identical by SHA-256 after rebuilding. Node 24.19.0 was used locally; CI retains Node 22 and the dependency engine constraints are unchanged.

## JWT and production security review

- Access tokens remain restricted to the configured algorithm (HS256 in the guarded profile), with a trusted server-side secret. Cloudflare Access remains RS256-only with RSA JWK parsing, bounded key cache, issuer, audience and required expiration checks. Reconnect grants remain HS256-only. No mixed symmetric/asymmetric algorithm allow-list was introduced.
- Regression tests reject unsigned, unexpected-algorithm, wrong-key, expired and deeply nested-header access tokens before database access. Additional tests check nested payload error handling, DER asymmetric key rejection as an HMAC secret, and options reuse.
- Existing tests cover login/logout, HttpOnly and SameSite cookies, CSRF/origin checks, forced password change, credential changes and resets, token_version, live session rows, and SSE/WebSocket revocation. Session identity uses jti and user identity rather than a hash of serialized token text. No stateless bypass or assertion weakening was introduced.
- No runtime auth code, infrastructure configuration, database guard, or production security control changed. Existing short-key test fixtures produce warnings; they are not production credentials.

## Validation and audit comparison

- Guarded complete Python suite: **320 passed, 68 warnings** (all 312 pre-existing tests plus eight new JWT regressions).
- Frontend: **40 passed**, zero failed, cancelled or skipped; build passed, 157 modules.
- Environment guard suite: **11 passed, 71 subtests passed**.
- Installed Python audit: **20 → 0** distinct advisories. Runtime/development manifest audit: **14 → 0**. Frontend audit: **9 affected packages / 7 root advisories → 0**.
- Exact audit commands: `python -m pip_audit --format json --aliases --desc`; the same command with `-r backend/requirements.txt -r backend/requirements-dev.txt`; `npm audit --json` in frontend. No ignored advisories or relaxed thresholds.
- Complete `scripts/codex_cloud_check.sh` gate passed with test-only Compose interpolation values: branding, repository hygiene, shell/Compose syntax, Python compile, Ruff format/lint, Bandit, dependency audits, migration structure, Python/frontend tests, build, generated OpenAPI/type drift and strict MkDocs build. Separate guarded PostgreSQL validation confirmed head `20260914_0019` and no new upgrade operations.
- Final diff review found only dependency declarations/lockfile, JWT regression tests and this report/navigation entry. No secrets or private environment artifacts are included. There are no runtime, API, model, migration, workflow or visual changes.

## Development isolation and limitations

The environment-only PyJWT constraint and its embedded installer copy were refreshed to 2.15.0. pip is controlled by the new development requirement. Private environment helpers, credentials and database state are not committed. Existing guards still verify the exact local database/user, development marker, local Docker socket, loopback bindings, zero Proxmox records, disabled integrations and rejection of seed/reset.

Only GitHub, Python/npm registries and guarded loopback development services were used. No production Proxmox, Guacamole, classroom infrastructure or physical devices were contacted. Network snapshot is restricted, VPN is unconfigured, and TCP grants are empty; the status tool reports enforcement as unknown, so this is not claimed as independently verified egress enforcement.

No merge, auto-merge, deployment or production mutation is authorized by this change. Live Ubuntu/nginx/systemd, real Proxmox, Guacamole consoles, browser acceptance, TLS, backup/restore and update-recovery checks remain separate acceptance work. Zero dependency findings is a point-in-time advisory result, not production certification.
