# Development validation

Run from the repository root with safe test-only environment values:

```bash
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
python -m compileall -q backend/app backend/tests deploy/provision_cloudflare.py
ruff format --check backend/app backend/tests deploy scripts tests
ruff check backend/app backend/tests deploy scripts tests
bandit -r backend/app deploy -ll -q
pip-audit -r backend/requirements.txt
PYTHONPATH=backend alembic -c backend/alembic.ini upgrade head
PYTHONPATH=backend alembic -c backend/alembic.ini check
PYTHONPATH=backend pytest -q backend/tests
python scripts/check_branding.py
python scripts/check_repository_hygiene.py
mkdocs build --strict
sh -n deploy/install.sh backend/docker-entrypoint.sh
docker compose -f docker-compose.yml -f docker-compose.live-test.yml config --quiet
cd frontend && npm ci && npm test && npm run build && npm audit --audit-level=moderate
```

Frontend changes must also follow the role, viewport, view-state, and
accessibility matrices in [Frontend testing](frontend-testing.md). The current
dependency-free test suite checks structural UI contracts; a passing source
assertion does not by itself prove rendered or browser behavior.

Regenerate the API contract after route or schema changes:

```bash
scripts/generate_api_contract.sh
```

CI fails if `frontend/openapi.json` or `frontend/src/generated/api-schema.d.ts` drifts. Generated types are the frontend/backend contract; do not maintain a conflicting handwritten schema.

`scripts/codex_cloud_check.sh` runs the complete local gate and fails with setup
guidance when a required tool or installed dependency is missing. It never treats
a skipped validation as success. CI additionally migrates disposable PostgreSQL,
verifies its current revision equals the repository head, and explicitly imports
every runtime Python module.

The backend commands require the safe test environment values used by CI and a
disposable PostgreSQL database. The GitHub workflow is the canonical executable
reference when reproducing them locally.

These checks do not validate a live Proxmox cluster, host networking, systemd
permissions, browser compatibility, TLS termination, update failure recovery,
or real backup restoration. Record those results with the
[pre-production acceptance checklist](../operations/preproduction-acceptance.md).

## Compatible backend maintenance updates

Keep `bcrypt==4.0.1` while the current Passlib 1.7.4 password backend remains.
Passlib's backend self-check hashes a long test vector; bcrypt 5 rejects it with
`ValueError` even when the requested application password is short, breaking
bootstrap and password hashing. Upgrading bcrypt requires replacing or adapting
the password backend with regression coverage for existing stored hashes first.
The existing password/session tests remain mandatory.

Ruff remains at the repository's validated 0.12.12 version. A formatter-major
upgrade needs a separate reviewed formatting migration rather than making a
mixed runtime dependency update fail its formatting gate. Other compatible
runtime/tooling updates can proceed through the complete existing CI gates.
