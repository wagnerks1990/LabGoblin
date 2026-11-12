# Email and support

LabGoblin integrates with Resend for account invitations, single-use password
recovery codes, password-change security notices, optional lab availability and
one-hour ending-window notices, verified operation results, and administrator
support mail. Email is disabled by default. Email never grants organization,
classroom, template, VM, or console access.

## Configure

Verify a dedicated domain or subdomain in Resend and enable sending and receiving
using the DNS records supplied by Resend. Do not replace existing institutional
mail MX records. The application accepts support mail only at the configured
support address; other addresses delivered to Resend are ignored by LabGoblin.

Under **System → Email & support**, configure an exact HTTPS application origin,
notification sender, support/reply address, API key, and webhook signing secret.
Only platform administrators may manage these settings or access the global
support inbox. Credentials are write-only and encrypted with the existing
`CONFIG_ENCRYPTION_KEY`; APIs return only configured/not-configured indicators.

The sending API alone can use a sending-only key. Incoming content retrieval
requires a Resend key with receiving access. Use a dedicated account/team and
the smallest permission/domain scope Resend supports for the enabled features.
Do not enable open/click tracking for authentication messages. Provider-side
message storage and retention are controlled separately in the Resend account.

For a root-operated Docker deployment, place the key in a root-owned mode-0600
file, then run from `/opt/labgoblin/app`:

```bash
sudo python3 deploy/configure-resend.py \
  --key-file /etc/labgoblin/resend-api-key \
  --origin https://lab.example.edu \
  --sender notifications@lab.example.edu \
  --support support@lab.example.edu \
  --enable-notifications
```

The origin must already be configured in `BROWSER_TRUSTED_ORIGINS`. The helper
checks readiness and verified domains, creates or reuses the exact callback
endpoint, and imports encrypted configuration over container stdin. Secrets are
never command arguments or printed output. Only the nonsecret webhook resource
ID and endpoint are recorded in `/var/lib/labgoblin/resend.json`. The helper does
not send test messages or alter DNS. If enrollment fails after registering a
webhook, rerun to reuse it or remove that exact endpoint in Resend.

The callback is `POST /api/email/resend/webhook`. Subscribe to `email.received`,
`email.sent`, `email.delivered`, `email.bounced`, `email.complained`,
`email.failed`, `email.delivery_delayed`, and `email.suppressed`. Verify the
Resend-generated signing secret before enabling receiving. The versioned
`/v1/api` mount is also available; register one endpoint to avoid duplicates.

NPM must forward `/api` and permit the signed POST callback. Cloudflare Access
is not bypassed: the root helper refuses Access-required deployments, which
need a separately reviewed provider-authenticated ingress path. Do not remove
the existing Access/session/origin protections to make webhooks work.

## Account workflows

On **Users**, choose to email an invitation when creating an account, or use
**Email a setup code** for an existing active account. Invitation creation uses
a random unknown initial password; no password is returned or emailed. Existing
accounts retain their current password until the code is redeemed. Invitations
do not create memberships or enrollments.

On the sign-in page, choose **Need help signing in? → Use an email code**.
Recovery requests always return the same accepted response for unknown,
inactive, disabled-mail, suppressed, and eligible accounts. Limits are three
requests per address and 100 per observed client address in 15 minutes;
redemption is limited to 20 attempts per observed client address per 15 minutes.
An upstream proxy may cause clients to share a limit. Forwarded addresses are
not promoted into identity or audit fields.

Recovery codes expire in 30 minutes; invitation codes expire in 24 hours. New
codes invalidate earlier codes. Codes are bound to the user, current email and
token version, are stored as hashes, and are single-use under a database lock.
The encrypted delivery payload temporarily contains the code for sending and
is scrubbed after provider acceptance. Codes are entered in the form, never
included in URLs or browser storage. Completing recovery revokes all sessions,
advances `token_version`, clears the forced change for that account, and
requires normal sign-in. Audit records contain no codes or passwords.

Users can disable optional lab/operation mail in **Account security → Email
notifications**. Security and user-requested account messages remain eligible.
Lab authorization and the recipient's current email/activation/preferences are
rechecked before sending. Assignment notices use active membership, enrollment,
run window, and enabled template checks. No historical notifications are
backfilled when notifications are first enabled. Messages contain a normal
application link and minimal status, never guest/infrastructure credentials or
provider errors. Students still must sign in and meet current authorization.

## Delivery and support

Mail uses an encrypted PostgreSQL outbox, bounded batches, persisted leases,
five bounded attempts, and a stable Resend idempotency key. An ambiguous send
can be retried with the same key; work older than 23 hours is cancelled before
Resend's 24-hour idempotency window expires. **Accepted** means provider
acceptance, not inbox delivery. Signed delivery webhooks update the result.
Out-of-order events cannot turn a complaint, suppression, or bounce into a
success. These events suppress future mail to that address. Suppression has
no automatic reset; review provider evidence before a deliberate remediation.

The `email` scheduler job appears in worker history when enabled. The admin page
shows failed webhook counts and supports retrying failed receipts after fixing
the cause. Refresh **Outgoing mail** to inspect queued/accepted/delivered or
failed status. Sending test mail is an explicit action to the signed-in admin's
registered email address; it is not an arbitrary-recipient relay.

Callbacks authenticate raw bytes with Svix v1 HMAC, constant-time comparison,
and a five-minute timestamp tolerance. A durable unique event ID prevents
duplicate processing; a second provider email ID protects inbound inserts.
Payloads are size bounded and provider content requests have fixed HTTPS
origins, deadlines, response-size limits, and no redirects.

Support mail appears in the platform-admin-only inbox. Reads, replies, and
archive/reopen actions are audited. Messages are untrusted input and confer no
identity or authority. Display uses escaped text only, with no remote images,
HTML execution, automatic attachment downloads, or automated replies. Manual
replies are queued to the received sender and use stable per-request keys.
Attachments can be reviewed separately in Resend; they are not ingested into
LabGoblin. The feature is an application support inbox, not IMAP/POP hosting.

Message contents and addresses are encrypted in PostgreSQL, excluded from normal
delivery summaries for account codes, and removed after 30 days by the worker,
including while sending is disabled. Nonsecret receipt IDs and delivery metadata
remain for deduplication. Backup retention and provider-side retention are
separate. Do not include real student messages in screenshots or test fixtures.

## Verification and rollback

Verify the migration reaches the single head `20261112_0020`; test public
readiness, unsigned webhook denial, a queued provider test, a signed callback,
an incoming support message, and account recovery with a disposable account.
Synthetic tests do not prove live inbox delivery, DNS, provider restrictions,
or browser/device accessibility. Record each separately.

Before deployment, take a PostgreSQL backup and protect `.env` and the existing
encryption key. The migration adds mail tables and does not rewrite existing
identity/VM data. To stop mail, disable sending in the GUI and disable the exact
Resend webhook. Reverting the application uses the guarded application/database
backup recovery procedure; do not manually downgrade a live database. Retain the
pre-deployment images and NPM configuration. Never restore another application's
NPM/database state as part of an email rollback.

Provider references: [sending](https://resend.com/docs/api-reference/emails/send-email),
[receiving](https://resend.com/docs/dashboard/receiving/introduction),
[webhook verification](https://resend.com/docs/webhooks/verify-webhooks-requests),
and [Svix manual verification](https://docs.svix.com/receiving/verifying-payloads/how-manual).
