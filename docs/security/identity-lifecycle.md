# Identity lifecycle

This document defines the V2 local-account authentication contract. Tenant
authorization is documented separately in [Organization tenancy](organization-tenancy.md).

## Session model

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
password change, password reset, username change, or account disablement
increments `token_version` and revokes every active session for that user.
Previously issued username-only JWTs are deliberately rejected after this
migration.

## User workflows

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
hash of the attempted username. Audit writes share the transaction with the
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


### Complete password hashing

New and changed passwords use Passlib's `bcrypt_sha256` scheme so the complete
UTF-8 password contributes to the hash, including bytes after bcrypt's 72-byte
input limit. Existing raw bcrypt hashes remain verifiable; they are replaced
with the new scheme when the user changes or resets the password. Existing
legacy hashes cannot recover bytes that bcrypt previously discarded, so users
who originally chose a password longer than 72 UTF-8 bytes should reset it to
establish its complete identity. Password changes and recovery continue to
revoke sessions according to the rules above; no token/session bypass is added.

A rollback must retain the `bcrypt_sha256` verification scheme once any new
hashes have been stored. Reverting the verifier to bcrypt-only would deny those
users authentication. Recovery does not require schema changes or rewriting
stored hashes; never convert hashes by truncating or extracting their fields.

Guided student-account setup accepts the same complete UTF-8 password as other
creation/reset workflows. An authenticated user with a legacy raw-bcrypt hash
may change its previously discarded suffix to establish a new complete identity;
the password-change path hashes the replacement and revokes sessions normally.
An exactly unchanged submitted password is still rejected.
