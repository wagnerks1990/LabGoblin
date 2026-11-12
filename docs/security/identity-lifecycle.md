# Identity lifecycle

This document defines the V2 local-account authentication contract. Tenant
authorization is documented separately in [Organization tenancy](organization-tenancy.md).

## Session model

Email is the primary sign-in identifier. `POST /api/auth/login` accepts
`email` and `password`; the sign-in page uses this contract. Email lookup ignores
case and surrounding whitespace. Existing `username` API input remains accepted
for compatibility, but sending both fields is rejected. Email-shaped input is
resolved only as an email, never as someone else's account handle. Both aliases
share one per-account/client login lockout. Unknown identifiers remain hashed in
audit records and authentication failures do not disclose account existence.

New accounts and first-admin enrollment need no separate username. A stable
internal handle is generated when absent; existing handles, user IDs, JWT
subjects and live session checks are preserved. The unique functional email
index from migration `20261112_0021` prevents case/whitespace duplicate accounts.
Migration stops on collisions without printing identities, changing passwords,
merging accounts or deleting records. Resolve collisions before retrying.

Successful login creates an `auth_sessions` row and a signed access token. The
token contains a random session identifier (`jti`) and the user's current
`token_version`. A request is accepted only when all of the following remain
true:

- the signature, token type, and expiry are valid;
- the user exists and is active;
- the token version matches the current user version;
- the matching database session exists, has not expired, and is not revoked;
- a forced password change is not pending for non-identity APIs.

This makes logout and administrative revocation effective immediately. A
password change, password reset, username/email change, or account disablement
increments `token_version` and revokes every active session for that user.
Previously issued username-only JWTs are deliberately rejected after this
migration.

## User workflows

Optional Resend email adds `POST /api/auth/email/request` (generic accepted
response) and `POST /api/auth/email/complete` (single-use code redemption).
Successful redemption revokes every existing session and advances the token
version without automatically signing in. Codes are bound to current email and
token version, expire after 30 minutes (24 hours for invitations), and never
appear in links or browser storage. See [email operations](../operations/email.md).

| API | Purpose | Result |
| --- | --- | --- |
| `POST /api/auth/login` | Verify local credentials | Creates a revocable session and access token |
| `GET /api/auth/me` | Load identity state | Includes `force_password_change` |
| `POST /api/auth/change-password` | Change the caller's password | Revokes other sessions and returns a replacement token |
| `GET /api/auth/sessions` | Review active sessions | Shows device, source IP, creation, and expiry |
| `DELETE /api/auth/sessions/{id}` | Revoke one owned session | Takes effect on the next request |
| `POST /api/auth/logout` | Revoke the current session | Takes effect immediately |
| `POST /api/admin/users/{id}/revoke-sessions` | Platform-admin revocation | Revokes all sessions and advances token version |

The Account Security page exposes password change and session review. Accounts
marked `force_password_change` are restricted to identity endpoints until the
password is changed. The administrator reset workflow always supports marking
the replacement as temporary.

## Password policy

New and replacement passwords default to at least 12 characters and require an
upper-case letter, lower-case letter, number, and symbol. The minimum length is
configured with `PASSWORD_MIN_LENGTH`. Passwords are stored only as bcrypt
hashes. Current passwords, replacements, and hashes must never be written to
audit metadata, logs, AI prompts, or API responses.

## Login abuse control

Failed attempts are counted by a SHA-256 digest of normalized username plus
source IP. Raw attempted usernames and passwords are not retained in the
throttle table. The default policy blocks the pair for 15 minutes after five
failures within five minutes and returns HTTP `429` with `Retry-After`.

The counters live in PostgreSQL, so API process restarts do not clear them.
Settings are:

- `LOGIN_MAX_FAILURES`;
- `LOGIN_FAILURE_WINDOW_SECONDS`;
- `LOGIN_LOCKOUT_SECONDS`.

Reverse proxies must preserve a trustworthy client address. The application
must only trust forwarded-address headers after the deployment proxy boundary
is explicitly configured; otherwise the socket peer address is used.

## Structured identity audit events

Identity actions use dotted names such as `identity.login`,
`identity.password_changed`, and `identity.sessions_revoked`. Each event can
record an outcome, actor, target, request ID, source IP, message, and JSON
metadata. Unknown-user login failures have a nullable actor and store only a
hash of the attempted identifier. Audit writes share the transaction with the
identity state change.

Existing operational audit writers remain readable because new audit fields
have safe defaults. Converting every legacy action to the structured helper is
tracked separately and must preserve tenant scope.

## Operations and recovery

- Run Alembic through `20260908_0012` before starting the updated API.
- Expect every browser to sign in again after the migration; legacy JWTs do not
  identify a database session.
- Back up `users`, `auth_sessions`, `auth_login_attempts`, and `audit_logs` with
  the rest of PostgreSQL.
- If an account is suspected compromised, disable it or use **Revoke Sessions**
  before investigation.
- Do not manually lower `token_version`; doing so can make an older token valid
  again.

Authentication lifecycle tests cover login, logout, forced changes, token
replacement, persistent throttling, structured audit records, and
administrator password resets.

