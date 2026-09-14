# Instructor workflow

Open **Classes & labs → Create a lab**. The guided setup combines the records
needed for a working classroom into five steps:

1. **Lab & class:** name the lab, write student instructions, and create or reuse a class.
2. **Machines:** select an imported template to create a dedicated pool automatically,
   or reuse an enabled pool. Templates are prepared by administrators beforehand.
3. **Students:** select active student members. Platform administrators can also add
   new student login accounts here; passwords must be changed at first sign-in.
4. **Access & schedule:** choose the number of machines per student, permitted browser
   methods, and a draft, scheduled, or open-now state.
5. **Review:** confirm the students, resource source, and access window, then save.

The final save creates class, pool, lab, run, enrollments, and assignments together
in one database transaction. A failure rolls back those changes. Retrying an
unchanged submission reuses its receipt. VM creation happens separately through
the existing durable provisioning flow when students select **Start lab**.

**Save draft** prepares the setup without opening student access. Return to
**Your lab setups → Edit setup** to change it. Unsaved form changes are held only
in memory. New account passwords are never kept in browser drafts or receipts;
share initial account passwords with students separately. Template guest logins
are different from LabGoblin login accounts. Their optional settings save
immediately and affect all VMs inheriting that template login.

Edits reject stale versions and cannot move a run to another class. Removing a
student, reducing a quota, or replacing the pool is blocked if it would affect
a linked VM. Existing class enrollments and other labs remain intact. Ended runs
are read-only. Shared blueprints with several runs use detailed management.

Open **Detailed classroom and infrastructure management** for shared blueprints,
roster maintenance, bulk start/stop/reboot, assignment revocation, and reviewed
run cleanup. An operation is complete only after the worker verifies its result.
Ending a run closes access immediately and queues its documented VM cleanup.

Instructors manage only their own classes in the selected organization; tenant
administrators and owners can manage all tenant classes. Account creation still
requires the platform administrator role. Saving a setup does not prove live
hypervisor capacity or RDP/SSH/VNC connectivity; those are checked by provisioning
and connection workflows.

## Prepare browser access and inspect resources

The wizard's browser-method checkboxes permit access; they do not configure
Windows Remote Desktop or Linux SSH. A platform administrator opens the VM's
**Connect in browser → Administrator: prepare guest access** panel above VNC,
confirms the reserved address, detects the guest service on its actual port,
verifies its server identity and approves the login. Template credentials may
be reused when automatic connections are enabled in template settings. After
saving, LabGoblin rechecks and selects the preferred available method.

Students cannot perform destination approval. If a method is blocked by lab
policy, edit the lab's access settings; if setup, service or identity is the
blocker, follow [browser connection preparation](../operations/consoles.md).
Guest-agent IP discovery is informational and does not grant connection authority.

Use **My machines** or a machine's details to inspect allocated CPU/memory/disk,
usage, uptime and IP/MAC observations. I/O is cumulative and disk capacity is
not filesystem free space. Failed/partial refreshes show warnings; refresh the
individual VM before relying on its displayed information.
