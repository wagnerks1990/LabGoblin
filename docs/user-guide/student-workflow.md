# Student workflow

## Open an assigned lab

1. Sign in with your **LabGoblin account** and select your organization if prompted.
2. Your **My labs** home displays assigned labs, instructions, schedules, and machines.
3. Choose **Start lab** to prepare an available assignment. Progress remains visible
   and durable even if you leave the page.
4. Choose **Start machine** for a stopped machine. Wait for verified readiness.
5. Choose **Connect in browser** to open an available desktop or terminal.

The connection page chooses an available Windows RDP, Linux SSH terminal, or
Proxmox VNC method and lets you switch between validated choices. Guest network
services require the administrator's approved connection profile. The browser
never needs Proxmox or Guacamole account credentials.

**Show lab login** reveals the template guest account only when sharing is enabled
and your current assignment permits access. It hides after 30 seconds or when
the page becomes hidden. This guest login may differ from your LabGoblin account.

If no labs appear, check the selected organization and ask your instructor.
Closed or future lab windows do not permit provisioning or connections. The
backend rechecks membership, enrollment, assignment, ownership, and access policy
for each action. A displayed status is not permission to bypass those checks.

## Other actions and help

Use **My machines** for permitted power actions and status refreshes. Assigned
VM deletion is managed by your instructor. **Lab activity** shows durable jobs,
verified results, warnings, and errors. **Account settings** changes your
LabGoblin password. Ask your instructor or administrator for a login reset.

## Machine information and connection help

Open **My machines** for allocated vCPUs, memory, disk capacity and guest IPs.
Expand **Resource and network details** for CPU/memory use, uptime, per-disk
capacity, IP/MAC addresses, I/O totals and the last observation time. The same
information is available under **Machine details** on My labs and **VM resources
and IP addresses** on the connection page. Use Refresh for a new observation.

Disk capacity does not mean free space inside Windows or Linux. Missing agent
information is shown with an explanation; a saved address is labeled separately.
If RDP or terminal is unavailable, read that method's reason and ask your
instructor or platform administrator. Working VNC does not mean RDP is ready.
Students cannot approve connection destinations or change the lab's access policy.
