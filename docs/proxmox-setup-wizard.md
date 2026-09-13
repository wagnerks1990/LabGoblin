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
- `VM.Allocate`, `VM.Audit`, `VM.Clone`, `VM.Console`, `VM.GuestAgent.Audit`,
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

Bootstrap reads the built-in Administrator role only to discover supported privilege names. It prefers VM.GuestAgent.Audit, uses VM.Monitor only on older servers lacking that replacement, and refuses unsupported required privileges before creating objects. It never assigns Administrator.


Template catalog refresh runs automatically when a platform administrator opens
Templates, Proxmox inventory, or VM provisioning. It discovers the active cluster
and upserts templates into the selected organization while preserving catalog IDs,
custom names, and disabled settings. Existing VMs remain inventory observations;
discovery does not grant student access or transfer ownership. Networks, storage,
and installation media are read from the cluster. Refresh is page-triggered, not a
background synchronization daemon. Template deletion and disk replication are not
automatic.

VM creation checks the cluster VM inventory before cloning, then tracks the durable
Proxmox task through completion. Failed inventory requests stop creation; HTTP 500
is never interpreted as absence. The provisioning page displays operation status
and errors, and Operations opens on all history with a Failed filter. Local tests
do not establish the cause of a particular production failure.


Power-task results matching `WARNINGS: N` (positive integer) may proceed to
observed-state verification. A start/reboot must still be running and a stop
must be stopped before the operation succeeds. Warning summaries and task IDs
are retained in the operation result and shown in Operations. Clone and delete
tasks continue to require `OK`. Historical failed operations are not rewritten.
VM deletion verifies cluster-wide absence before skipping Proxmox mutations;
failed inventory requests never establish absence. The frontend image normalizes
public static directories to 755 and files to 644 so nginx can read assets even
when the builder inherits a restrictive umask.
