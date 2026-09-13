# Proxmox Setup Wizard

## Automatic dedicated access

A LabGoblin platform administrator can connect a cluster without manually
creating a Proxmox token. Open **Administration > Proxmox setup**, expand the
connection form, and provide:

- a descriptive cluster name;
- the HTTPS Proxmox API URL, normally
  `https://PROXMOX_HOST:8006/api2/json`;
- the one-time `root@pam` password; and
- whether the Proxmox TLS certificate must be verified.

The form is enabled only in a secure browser context (HTTPS or localhost). The
backend signs in to Proxmox as `root@pam`, creates the exact resources below,
validates the generated token, and stores only the encrypted token secret. The
root password is never stored, logged, returned, or used to create a root API
token.

| Resource | Fixed value |
| --- | --- |
| Proxmox user | `labgoblin@pve` |
| Role | `LabGoblinRole` |
| API token | `labgoblin@pve!labgoblin` |
| ACL | `/`, propagated, `LabGoblinRole` only |

The first configured cluster becomes active automatically. A later cluster is
saved inactive until an administrator explicitly activates it.

The automatic role contains only these privileges:

- `Datastore.AllocateSpace`, `Datastore.AllocateTemplate`, `Datastore.Audit`
- `Pool.Allocate`, `Pool.Audit`
- `SDN.Audit`, `SDN.Use`
- `Sys.Audit`
- `VM.Allocate`, `VM.Audit`, `VM.Clone`, `VM.Console`, `VM.Monitor`,
  `VM.PowerMgmt`

LabGoblin refuses to overwrite an existing `labgoblin@pve` user or an existing
`LabGoblinRole` with a different privilege set. Remove or rename the conflicting
Proxmox object after reviewing it, or use the manual-token form. If validation
fails after LabGoblin created the user and role, it attempts to remove those new
objects. Interactive root logins that require a second factor are not supported
by this one-time flow; create a dedicated token manually instead.

## Manual token fallback

Enter the cluster name, API URL, token user, token ID, token secret, and TLS
verification choice. LabGoblin validates the token before encrypting it with
`CONFIG_ENCRYPTION_KEY`. Back up that encryption key. Never use a root token.

Deleting a cluster removes only the LabGoblin database configuration; it does
not delete Proxmox users, tokens, roles, or VMs. Environment-variable fallback
still applies when no active database cluster exists.

## Discovery and placement

Discovery-driven defaults cover nodes, storage targets, VM templates, and
bridges/networks. Manual defaults remain available when discovery is empty.

Placement policy options are `manual` (requires an online default node),
`balanced`, and `prefer_default_then_balance`.


## Cluster readiness panel
The Proxmox Setup page includes a Cluster Readiness panel with PASS/WARN/FAIL, eligible/excluded nodes, reasons, and recommended next steps.

Bootstrap discovers identity existence through successful role/user collection responses. Proxmox can return HTTP 500 for missing individual identities; never treat arbitrary HTTP 500 failures as absence. Discovery failures must stop setup.
