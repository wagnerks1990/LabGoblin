# Platform administration

Platform administration is organized around setup, inventory, policy, identity,
and operations.

## Infrastructure setup

1. Open **Proxmox Setup** and add a canonical HTTPS `/api2/json` endpoint.
2. Keep TLS verification enabled and validate a least-privilege token.
3. Review node, storage, network, and template readiness.
4. Open **Proxmox Inventory** to import approved templates.
5. Use **Proxmox Assets** only for explicit, reviewed synchronization work.

Cluster credentials remain backend-only. Existing credential-bound origins and
TLS policy are not edited in place.

## Policy and identity

- **Templates** controls the application catalog.
- **Pools** controls placement and availability policy.
- **Organizations**, **Users**, and **Groups** control identity and membership.
- **System Updates** checks, applies, and rolls back through the protected host
  updater rather than through a direct repository pull.

Global administration does not silently create tenant membership. Select an
organization before performing tenant-scoped work.

## Observe and recover

Use **Telemetry**, **Troubleshooting**, **Events / Tasks**, and **Operations** to
separate application health, external integration failures, and durable-job
state. Treat unavailable data as an error, not an empty healthy result.

Deletion and update actions require their preview or exact confirmation. Retain
the resulting audit and operation records for the acceptance evidence.
## Email and support

Use **System → Email & support** to configure Resend, inspect outgoing delivery
state, and read or manually reply to support mail. Invitations can be queued
when creating a user or from the user's security actions. No classroom
membership is granted by an email code. See [Email and support](../operations/email.md).
