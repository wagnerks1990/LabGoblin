# Dependency security remediation — 2026-10-12

## Scope and audit counting

Audits were reproduced from main commit `4eba9580ee2ead572c85ac04737efbb5d960e640` in the isolated cloud development environment. Installed Python packages had 20 distinct advisories: 14 in PyJWT 2.13.0 and six in pip 25.0.1. Resolving the runtime and development manifests produced the same 14 PyJWT advisories; pip is an environment installer rather than a runtime dependency. The frontend lockfile had nine affected package entries (seven high, two moderate), representing six distinct root advisories (four high, two moderate). Parent entries are dependency propagation, not additional vulnerabilities.

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
- Installed Python audit: **20 → 0** distinct advisories. Runtime/development manifest audit: **14 → 0**. Frontend audit: **9 affected packages / 6 root advisories → 0**.
- Exact audit commands: `python -m pip_audit --format json --aliases --desc`; the same command with `-r backend/requirements.txt -r backend/requirements-dev.txt`; `npm audit --json` in frontend. No ignored advisories or relaxed thresholds.
- Complete `scripts/codex_cloud_check.sh` gate passed with test-only Compose interpolation values: branding, repository hygiene, shell/Compose syntax, Python compile, Ruff format/lint, Bandit, dependency audits, migration structure, Python/frontend tests, build, generated OpenAPI/type drift and strict MkDocs build. Separate guarded PostgreSQL validation confirmed head `20260914_0019` and no new upgrade operations.
- Final diff review found only dependency declarations/lockfile, JWT regression tests and this report/navigation entry. No secrets or private environment artifacts are included. There are no runtime, API, model, migration, workflow or visual changes.

## Development isolation and limitations

The environment-only PyJWT constraint and its embedded installer copy were refreshed to 2.15.0. pip is controlled by the new development requirement. Private environment helpers, credentials and database state are not committed. Existing guards still verify the exact local database/user, development marker, local Docker socket, loopback bindings, zero Proxmox records, disabled integrations and rejection of seed/reset.

Only GitHub, Python/npm registries and guarded loopback development services were used. No production Proxmox, Guacamole, classroom infrastructure or physical devices were contacted. Network snapshot is restricted, VPN is unconfigured, and TCP grants are empty; the status tool reports enforcement as unknown, so this is not claimed as independently verified egress enforcement.

No merge, auto-merge, deployment or production mutation is authorized by this change. Live Ubuntu/nginx/systemd, real Proxmox, Guacamole consoles, browser acceptance, TLS, backup/restore and update-recovery checks remain separate acceptance work. Zero dependency findings is a point-in-time advisory result, not production certification.


## Runtime Docker pip follow-up — 2026-10-12

Main commit `2fc4196` (after PR #170) still used unpinned `python:3.12-slim`.
The following identities are from local **linux/amd64** builds, not an inspection
of a deployed production container. A mutable tag cannot establish what an
older deployment used.

| Identity | Original | Corrected |
| --- | --- | --- |
| Base reference | `python:3.12-slim` | `python:3.12.15-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1` |
| Resolved base index digest | `sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1` | Same, now explicitly pinned |
| Resolved amd64 base manifest | `sha256:2b4f19dae3a777dfc3b76730bda1e82e1f66ab2a2686fa93ca78edbfb4f04ffe` | Same |
| Python / distribution | Python 3.12.15 / Debian 13.7 (trixie) | Same |
| Local resulting image configuration ID | `sha256:dafa104c92dc61c245b129af9a0818a4bda8df97faa2c63c8ea29fc8d4d301f8` | `sha256:c1f3c40f21b1622e08a7047a3578d3b91cab91024d68cd2243421c586cfb5987` |
| Installed runtime pip | 25.0.1 | Absent; verified 26.2 used during build only |

Local image configuration IDs are not registry manifest digests. No application
image was published. The latest resolved base still inherits pip 25.0.1, so a
base pin alone does not fix this finding. The existing approved pip 26.2 version
from development requirements is installed as a wheel with `--require-hashes`,
`--only-binary=:all:` and `--no-deps`, then its imported version is asserted before
application dependencies are installed. The PyPI wheel SHA-256 is
`931c303696af6fa3417112103b1cad26890e5a07eccb5b99783700e33f2b8aad`.
`pip check` passes before pip is uninstalled. The standard-library `ensurepip`
bootstrap package (including its bundled old pip wheel) is removed too.

No runtime requirement, dependency version, entrypoint, migration, API behavior,
TLS setting or runtime user was changed. The optional BuildKit `proxy_ca` secret
allows TLS-verifying builds with a combined CA bundle; it is never copied into
an image layer. Normal builds use the base's standard certificate trust. The
final filesystem contains neither pip, ensurepip, a pip cache, the temporary
requirements file, the CA mount, setuptools, wheel, gcc nor make. System package
management and Debian runtime libraries inherited from the slim base remain.

### Actual-image audits and remaining findings

Both images were audited inside their containers with pip-audit 2.9.0, using
read-only external audit tooling and `--path /usr/local/lib/python3.12/site-packages
--format json --aliases`. This scopes the audit to the actual image's installed
packages; the auditor's own environment is excluded. The original single-stage
runtime had all six pip advisories listed above (five moderate, one low), with
no other installed Python findings. The corrected runtime has **zero** installed
Python findings. Runtime-manifest and aligned development-environment audits
also report zero, without ignored advisories. Audit tooling is not installed in
the final image.

Trivy 0.67.2 (`aquasec/trivy@sha256:e2b22eac59c02003d8749f5b8d9bd073b62e30fefaef5b7c8371204e0a4b0c08`)
scanned the actual local Docker images with `--scanners vuln --format json`.
The database was downloaded via `registry-1.docker.io/aquasec/trivy-db:2`, updated
at `2026-10-12T19:08:28Z`; the same cached database was used for the comparison.
Trivy independently confirms **six → zero** pip/Python findings. There are no
separate builder stages in either application Dockerfile. Pip 26.2 is transient
in the corrected install step and absent from the merged runtime filesystem.
Inherited base layers still contain historical installer bytes; deletion does
not rewrite upstream layers. A layer-history or build-cache inventory must not
be confused with packages executable in the running container. This change
does not claim those historical bytes have been physically purged.

**The whole image is not vulnerability-free.** Both scans report the same 166
Debian package/advisory entries: 44 high, 58 medium, 61 low, three unknown, and
zero critical. These represent 73 distinct scanner identifiers, rather than
166 distinct CVEs. Only two entries report fixes: `liblzma5` 5.8.1-1+deb13u1,
`DSA-6549-1` and `TEMP-1147318-639065`, with 5.8.1-1+deb13u2 recorded as fixed.
No finding was hidden or dismissed. OS package remediation remains separate
from this narrow installer follow-up; this report does not approve deployment.

### Runtime software inventory

The pinned base supplies Python 3.12.15, its standard library (except ensurepip),
and Debian 13.7. `dpkg-query` lists 87 installed binary packages; Trivy analyzes
93 OS package records. The base identity above fixes the inherited OS inventory.
The application adds the following 46 installed Python distributions. Comparing
original and corrected inventories shows only removal of pip 25.0.1; all
application and transitive versions are identical between these builds. The
existing direct requirements remain pinned; transitive requirements retain the
repository's existing resolution policy.

```text
APScheduler==3.10.4
Mako==1.4.3
MarkupSafe==3.0.4
PyJWT==2.15.0
PyYAML==6.0.3
SQLAlchemy==2.0.35
alembic==1.13.2
annotated-doc==0.0.5
annotated-types==0.8.0
anyio==4.15.1
asyncssh==2.24.0
bcrypt==4.0.1
certifi==2026.7.22
cffi==2.1.1
click==8.5.0
cryptography==50.0.2
dnspython==2.9.0
email_validator==2.2.0
fastapi==0.141.1
greenlet==3.5.6
h11==0.16.0
httpcore==1.0.9
httptools==0.9.0
httpx==0.27.2
idna==3.20
passlib==1.7.4
psycopg-binary==3.3.4
psycopg==3.3.4
pycparser==3.11
pydantic-settings==2.5.2
pydantic==2.14.1
pydantic_core==2.50.1
python-dotenv==1.2.4
python-multipart==0.0.32
pytz==2026.5
redis==5.0.8
six==1.17.0
sniffio==1.3.1
starlette==1.7.0
typing-inspection==0.4.4
typing_extensions==4.16.0
tzlocal==5.4.4
uvicorn==0.30.6
uvloop==0.23.0
watchfiles==1.3.0
websockets==17.1
```

Reproduce the OS and Python inventories from a built image without network access:

```sh
docker run --rm --network none --entrypoint dpkg-query labgoblin-runtime:fixed -W
docker run --rm --network none --entrypoint python labgoblin-runtime:fixed -c \
  'import importlib.metadata as m; print("\n".join(sorted("{}=={}".format(d.metadata["Name"], d.version) for d in m.distributions())))'
```

### Validation and isolation

- Both backend images built successfully. The original reproduction used only
  an ephemeral Dockerfile adaptation to mount the cloud CA bundle during pip
  installation; no CA was persisted and TLS verification stayed enabled.
- Corrected image inspection confirms `USER app` (UID 100/GID 101), unchanged
  `docker-entrypoint`, and unchanged uvicorn command. A read-only filesystem,
  all capabilities dropped, and `no-new-privileges` passed runtime checks.
- Guarded checkout suite: **320 passed, 68 warnings**. The preinstalled cloud
  environment initially retained PyJWT 2.13.0 and failed two already-merged JWT
  regression tests; aligning its local dependencies with main (PyJWT 2.15.0,
  pip 26.2) resolves both. No test was weakened.
- Final-image suite: **320 passed, 68 warnings**, with application and dependency
  imports verified to come from the image and externally mounted pytest tooling.
  The test runner uses a read-only repository mount, no network, and an executable
  temporary filesystem for mocked shell commands; tooling is outside the runtime
  inventory. The separate default-entrypoint validation uses the actual app user.
- Trivy secret scanning of the corrected image reports **zero findings**.
- The default non-root entrypoint with `RUN_MIGRATIONS=true` migrates a fresh,
  disposable PostgreSQL 16 database. Replaying `alembic upgrade head` succeeds;
  repository and database both have the single head `20260914_0019`;
  `alembic check` reports no new upgrade operations. The database contains zero
  Proxmox cluster records.
- Actual-container `/api/health` returns `{"status":"ok"}` and `/api/ready`
  returns `{"ready":true}`. Startup uses an internal-only Docker network,
  no published ports, a read-only root filesystem, no capabilities and
  `no-new-privileges`. Its only service peer is the disposable database;
  the scheduler is disabled and Proxmox/guacd destinations are loopback.
  Containers, database volume, test environment files and network are removed
  after validation. No production Proxmox or Guacamole host is contacted.
- Python compile, Ruff formatting/lint, Bandit, branding, repository hygiene,
  entrypoint shell syntax and diff whitespace checks pass. The final diff is
  confined to the backend Dockerfile and this existing report, with no secrets,
  private environment files, runtime databases or generated artifacts committed.
- This is local cloud validation. Ubuntu host deployment, live infrastructure,
  real Guacamole connections and other CPU architectures are not validated.
  No merge, auto-merge, deployment or production infrastructure change occurs.

## Frontend container security follow-up — 2026-10-12

The original frontend runtime `nginx:1.27-alpine` resolves to index digest
`sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10`.
A fresh Trivy 0.67.2 scan using the same approved database records 161 Alpine
package/advisory entries: two critical, 41 high, 76 medium and 42 low. The
original image is Alpine 3.21.3, and many entries have available package fixes.

The frontend Dockerfile now uses the supported nginx 1.31 Alpine runtime,
pinned at index digest
`sha256:df221db836e1754089190208cee7eeda94f233197056426eda74a43ab1abeac2`,
and the supported Node 24 LTS builder at
`sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1`.
Node 20 reached end of support in April 2026. Application dependencies, nginx
routing/security headers/listen port and asset permissions are unchanged.

The optional BuildKit CA secret supports TLS-verifying npm installs behind the
approved proxy without copying its bundle into an image layer. npm retains
`--strict-ssl=true`. A frontend Docker context ignore file prevents host
node_modules, old dist files, environment files and logs from replacing clean
installed dependencies or entering the builder context. No image is published
or deployed; the existing disposable-container CI remains the application gate.

The updated pinned nginx base alone still has six fixable entries (three high,
three medium): libexpat/CVE-2026-93990 (2.8.5-r0), libpng/CVE-2026-46675
(1.6.59-r0), nghttp2-libs/CVE-2026-58055 (1.70.0-r0), pcre2/CVE-2026-103111
(10.49-r0), tiff/CVE-2026-4775 (4.7.2-r0), zlib/CVE-2026-85091 (1.3.2-r1).
The final runtime additionally upgrades installed Alpine packages, and the
existing container integration job requires each library at or above its
recorded fixed version. No findings are suppressed. Local image builds before
the package upgrade passed nginx syntax validation and retain those six
findings; the approved proxy explicitly denies Alpine mirror access (HTTP403
for dl-cdn.alpinelinux.org), so the final installation must be qualified by
hosted CI. Do not call the newer base or that pre-upgrade local image
vulnerability-free.

The new `frontend-container-security` CI job builds the actual final web image,
runs the digest-pinned Trivy scanner for vulnerabilities and secrets, prints
all advisory counts/identifiers, and retains its complete JSON as a 14-day
artifact. Qualification rejects every advisory with a recorded available fix
at every severity and every secret finding. Unfixed records remain visible;
there are no ignored-advisory lists or scanner exclusions. This supplements
npm auditing and the existing container application tests. The upload action
is pinned to verified upload-artifact v4.6.2 commit. Add this proven check to
main protections after its hosted validation succeeds; existing wrong required
contexts must first be repaired by an authorized administrator.
