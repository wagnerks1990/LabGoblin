# Development Workflow

## Branch model
- `main`: source of truth for the current alpha and release candidates
- `feature/*`, `fix/*`, and `audit/*`: scoped branches created from `main`

There is no active `develop` branch. Merging to `main` does not by itself confer
production support; the pre-production acceptance gates remain authoritative.

## Backend refactor policy
- Keep API paths backward-compatible during route splitting.
- Keep route logic in feature routers under `backend/app/api/routers`; the legacy router has been removed.
- Use service-layer modules to avoid route bloat.

## Proxmox-only scope
- Classroom VDI orchestration on Proxmox clusters/nodes only.
- No multi-hypervisor abstraction in this project.

## Schema drift policy
- Prefer tolerant Alembic migrations for existing drifted databases.
- Never drop data as part of Codex migration fixes.

## Safe testing policy
- Safe local and disposable validation is expected when its dependencies are
  available. Use `docs/development/validation.md` for the canonical commands.
- The disposable Compose live test may run only against its isolated local
  database and simulator with the required destructive-test acknowledgement.
- Never run destructive actions against a real Proxmox cluster, a reused
  database, or an actual deployment from an unattended development environment.
- Real-cluster, browser-console, TLS, update-recovery, and restore tests belong
  to the isolated acceptance environment and must be recorded in the
  pre-production acceptance checklist.

## Hosted Wiki synchronization

The versioned `docs/` directory is the source for the GitHub Wiki. The `Wiki
Sync` workflow publishes only git-tracked Markdown on approved `main` changes
or a manual dispatch; it uses the repository's `WIKI_TOKEN` secret through a
short-lived Git askpass helper. The token is never placed in the Git URL,
committed, or written to the Wiki. Initialize the Wiki once through GitHub's
**Wiki → Create the first page → Save Page** if cloning it reports not found.

`docs/index.md` becomes `Home`; other pages use `Docs-` followed by their path
with directory separators converted to hyphens. Relative document links and
reference links are converted to Wiki names; links to repository assets remain
repository links. Existing pages outside those generated names are preserved.
A name collision or repository-escaping link stops publication. Removed source
pages are retained in the Wiki until reviewed for safe cleanup.

Run the renderer tests and preview without publishing:

```sh
python -m unittest discover -s tests -p 'test_sync_wiki.py'
python scripts/sync_wiki.py --destination /tmp/labgoblin-wiki-preview
```

After the first approved workflow run, verify its logs and open the Wiki Home
and a nested operations link. A successful local preview does not establish
that `WIKI_TOKEN` is authorized to push.
