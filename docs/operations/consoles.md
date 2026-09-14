# Browser connections

LabGoblin bundles Apache Guacamole 1.6.0. Students select **Connect in browser**
on an assigned VM. LabGoblin checks the actual Proxmox guest OS and running
state, authenticates a temporary Proxmox VNC session, and tests the approved
guest service and server identity. It also checks the private gateway. The
page opens the best available permitted method: Windows RDP, Linux SSH
terminal, or Proxmox VNC. The other verified methods remain selectable.

The same page provides reconnect, disconnect, full screen, and Ctrl+Alt+Delete.
Closing the page disconnects the session without shutting down the VM. A
stopped VM must be started first. Failed checks are reported instead of being
represented as successful connections. Recheck after changing guest settings.

## Bundled architecture

The default Compose deployment includes the pinned `guacamole/guacd:1.6.0`
image from the Apache project. It starts automatically during installation or
a GUI update. There is no separate Guacamole web application, database,
service account, or student login. LabGoblin is the authenticated tunnel broker.

The official Apache `guacamole-common-js` 1.6.0 modules are included in the
frontend build with their license and notice. See
`frontend/src/vendor/GUACAMOLE-SOURCE.md` for provenance.

Only the LabGoblin web proxy is published. guacd has no host port and is not
attached to the web/Cloudflare network. The API and gateway share a private
console network; a separate gateway network allows outbound guest connections.
Never publish guacd port 4822: guacd itself is not an authentication boundary.

### Proxmox VNC

VNC does not require a guest VNC server, an IP address, or an installed guest
agent. The broker obtains and authenticates a Proxmox ticket over the configured
cluster transport. VeNCrypt Plain and legacy VNC authentication are supported;
upstream unauthenticated RFB is rejected. Proxmox's existing TLS verification
and host policy remain authoritative.

A temporary password-protected RFB adapter connects guacd to the Proxmox
WebSocket. Its port is unpublished, its password is generated per connection,
and it accepts only one authenticated connection. The adapter and its tasks
close with the browser session. Proxmox tokens and tickets are never forwarded
to guacd or the browser. The Proxmox identity requires VM.Console permission on
the selected VM.

### Windows RDP and Linux SSH terminal

Guacamole is installed automatically; guest operating systems still need their
own services enabled. Windows needs an edition supporting an RDP server,
Remote Desktop with NLA, a permitted guest account, and the guest firewall
rule for port 3389. Linux needs SSH, a permitted guest account, and port 22.
A port being open does not prove authentication or authorization will succeed.

A platform administrator can prepare a guest entirely in the connection GUI:

1. Open the VM's browser connection page. VNC can be used for guest setup.
2. Use **Administrator: prepare guest access** above the console (opened automatically when guest access is unavailable). LabGoblin reads current
   QEMU guest-agent interfaces through the VM-bound Proxmox API, matches their
   MAC addresses to the hypervisor adapters, and filters invalid/local addresses.
   A single candidate is prefilled; multiple candidates remain an explicit GUI
   selection. Addresses matching static cloud-init `ipconfigN` values are labeled.
   Agent failures are shown, not replaced with a stale saved IP. Existing approved
   profiles are retained without silently changing their destinations.
   Verify a DHCP/IPAM reservation for this exact VM; matching guest-reported MACs
   alone is not proof of ownership. Discovery sends no credentials to guest IPs.
3. Confirm the reserved address, verify the guest service port (custom ports are supported), and select **Detect guest service**. LabGoblin
   detects RDP/NLA and its certificate or SSH and its host key; no credentials
   are transmitted during this probe.
4. Verify the displayed identity against the guest, select its Proxmox network
   adapter, and supply an account dedicated to this VM. Approve the profile.

Subsequent connection checks automatically enable the matching browser method
when the service is reachable and its saved identity matches. There are no
per-VM Guacamole connection IDs or protocol switches to maintain. A saved
profile is bound to the application VM id and verified Proxmox MAC. Changed
MACs, server identities, disabled profiles, closed ports, unknown OS types,
and disallowed lab protocols block the corresponding method. RDP uses NLA
and SHA-256 certificate pins. SSH requires the saved OpenSSH host key.
Credentials are encrypted with the existing CONFIG_ENCRYPTION_KEY and never
returned by profile APIs. Use unique guest accounts/credentials and regenerate
cloned host keys/certificates where needed; avoid shared classroom passwords.

**Limit:** RDP/SSH cannot be securely enabled merely from an arbitrary IP
reported by a guest. This release requires the GUI approval above; it does not
yet reconcile authoritative DHCP/IPAM reservations or provision guest accounts
automatically. Proxmox VNC works without that preparation. Fully unattended
RDP/SSH for newly created VMs requires a future trusted IPAM/account provisioning
integration. Do not weaken identity checks to make a discovery result green.

The guest agent exposes network observations, not a password-recovery mechanism.
Cloud-init configuration may contain password hashes rather than usable login
secrets; these are not read, returned or reused by discovery. Template cloning
currently does not create new cloud-init credentials or reset existing accounts.

An optional deployment restriction, `GUACAMOLE_ALLOWED_NETWORKS`, accepts
comma-separated CIDRs. If supplied, even administrator-approved addresses must
fall within these ranges. Loopback, link-local, multicast, unspecified addresses,
and hostnames are rejected. Private management destinations must not be approved.
Existing deployments do not need this variable to use the GUI workflow.

## Authorization and session lifecycle

All WebSockets use the existing HttpOnly LabGoblin session cookie, selected
organization, origin validation, optional Cloudflare Access, and VM ownership /
instructor-class authorization. Each connection rechecks its specific lab flag
(console, RDP, or terminal) and assignment/run window. These policies take
precedence over availability detection. Students cannot choose backend hosts,
ports, Guacamole connection IDs, protocols outside the fixed list, or stored
credentials. The tunnel parser rejects destination changes, session joins,
clipboard/file streams and other unsupported input instructions.

The broker records launches and marks a session active only after receiving
remote display synchronization. It rechecks the original login session and
assignment access every 30 seconds, and profile revision/enabled state every
15 seconds. Disconnects cancel and await pumps and close upstream resources.
A maximum of five launching/active browser sessions is checked per user.
Clipboard transfer, file transfer, drives, printing and microphone input are
disabled in this initial integrated gateway.

The older noVNC transport remains for compatibility. The deployment-wide SSH
pilot remains disabled by default (`SSH_TERMINAL_ENABLED=false`); the new
Guacamole SSH route does not enable that pilot. A Proxmox serial terminal
transport exists as a compatibility path but is not the student connection UI.

## Validation and operations

The default Compose health gate checks guacd before starting the API. CI also
negotiates each gateway protocol and verifies security parameters for VNC,
RDP, and SSH. You can repeat that non-secret check on the server:

```sh
cd /opt/labgoblin/app
docker compose exec -T api python < backend/scripts/check_guacd.py
```

Cloud validation covers build, protocol framing, server-only authentication,
malformed/forbidden browser instructions, role/origin checks, and migration
shape. It does not prove a real Windows or Linux session works on your network.
After updating through the GUI, validate one assigned Windows VM and one Linux
VM: connection checks, guest login, keyboard/mouse, resizing, reconnect, logout
revocation, assignment expiry, and changed-host-identity rejection. Also check
concurrent classroom load and the supported GUI viewport widths. The Cloud
browser preview is blocked in this environment, so no live browser screenshots
or production transport validation are claimed.

References: [Apache Guacamole server](https://github.com/apache/guacamole-server),
[protocol](https://guacamole.apache.org/doc/gug/guacamole-protocol.html), and
[connection security parameters](https://guacamole.apache.org/doc/gug/configuring-guacamole.html).

### Template lab logins

Organization administrators can save an existing guest username, password, and
optional domain in **Templates → Guest credentials**. These encrypted settings
have separate switches for automatic connections and student sharing. Saving
credentials does not create or reset accounts inside a template or its clones.
A VM profile may inherit this login or retain a VM-specific override. Reserved
address, adapter, and pinned host identity validation still apply before sending
credentials. Template changes revoke inherited sessions on the profile check.

When sharing is enabled, **Show lab login** on an assigned VM makes an audited,
no-store POST request that rechecks current organization, ownership, enrollment,
assignment, and run access. The revealed lab account hides after 30 seconds or
when the page becomes hidden. It is never stored in browser storage or returned
by VM/template lists. This explicit sharing feature does not expose Proxmox,
gateway, infrastructure SSH credentials, private keys, or VM-specific overrides.
Shared template accounts are shared across clones; use separate template accounts
or VM overrides where separate guest identities are required.

## Resource visibility and unavailable connections

**My machines**, student **Machine details**, and the connection page's
**VM resources and IP addresses** show live VM observations. The API reads only
authorized VMs, limits concurrent checks to four, and caps each list refresh at
20 seconds. Rows not refreshed show a warning; use that VM's Refresh action.
The student home avoids overlapping refresh requests.

- vCPUs and allocated memory come from VM configuration; CPU use, reported memory
  use and uptime come from Proxmox status. These are hypervisor observations,
  not a guarantee of guest application memory use.
- Disk capacity sums attached virtual data/system disks with known sizes. CD-ROM,
  cloud-init, EFI and unused disks are excluded. Unknown sizes remain unknown;
  capacity is not filesystem used/free space.
- Network and disk I/O are cumulative byte counts, not instantaneous rates.
- IP/MAC observations come from the QEMU agent matched to Proxmox VM adapters.
  Missing agent data gets an explanation. Saved addresses remain labeled as such.
  Observations never replace approved connection destinations or authorize logins.

Each connection method now reports its own blocker: setup incomplete, disabled
profile, lab policy, guest service/identity failure, stopped VM, or gateway failure.
Working VNC does not establish that Windows RDP is enabled or configured.
A platform administrator uses the setup panel above VNC to approve the guest
address and detected identity and select the saved template login. After saving,
the page checks again and selects the preferred available method. Students see
the reason but cannot approve destinations. No server shell configuration is
required for this GUI workflow; guest RDP/SSH service setup is still necessary.
