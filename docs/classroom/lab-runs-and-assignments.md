# Lab runs and student assignments

The classroom control plane separates reusable curriculum from a scheduled
classroom event:

- a **class** owns a roster and is assigned to an instructor;
- a **lab blueprint** selects a desktop pool and student access flags;
- a **lab run** applies a schedule and per-student VM quota to one blueprint;
- a **lab assignment** grants one student one template slot in that run;
- an assigned VM remains owned by the student but is controlled by the run.

This is an authorization boundary, not just a frontend workflow. Direct or
group template permissions no longer authorize student VM creation by
themselves.

## Student access decision

A student request is accepted only when all of these conditions are true:

1. the selected organization is enabled;
2. the student has an active membership in that organization;
3. the student has an active enrollment in the run's class;
4. an assignment exists for the student, run, template, and slot;
5. the assignment is not revoked or expired;
6. the run is active, or scheduled and inside its start/end window;
7. the VM is owned by that student and linked to that assignment;
8. the requested power or console operation is enabled by the lab blueprint.

The API repeats this decision for listing, status, start, stop, reboot, REST
console launch, and WebSocket console launch. A hidden frontend button is not a
security control.

## Run lifecycle

| Current state | Allowed actions | Behavior |
| --- | --- | --- |
| `draft` | schedule, activate, cancel | Assignments can be prepared but are not usable |
| `scheduled` | activate, cancel | Access opens automatically inside the configured time window |
| `active` | end, cancel | Access is open until manually ended or the end time passes |
| `ended` | none | Assignments are marked expired |
| `cancelled` | none | Assignments are marked revoked |

Scheduling controls authorization without requiring a worker to flip the state
at the exact start time. At `ends_at`, access closes immediately even if the
database state still says `scheduled` or `active`.

Time-window expiration immediately blocks student access. The explicit End run
action requires a preview and queues verified VM deletion; the click itself does
not mean deletion has completed. Instructors can still investigate tenant VMs
and monitor the durable cleanup operations.

## Instructor workflow

The **Classroom** page implements the first working path:

1. create or select a class;
2. enroll active organization members as students;
3. create a lab blueprint using an enabled pool;
4. create a run with optional start/end times and a quota from 1–10 VMs;
5. assign the current roster idempotently;
6. schedule the run or activate it immediately;
7. monitor assignment-to-VM links and revoke individual assignments;
8. end the run to expire access.

Instructors only see classes assigned to them. Organization administrators and
owners can manage all classes in the tenant.

## Assignment and quota rules

An assignment is unique by lab run, student, and slot number. Bulk assignment
is idempotent, so retrying it does not create duplicates. The slot number may
not exceed `max_vms_per_student`, and one assignment can link to at most one
application VM record.

The default assignment template comes from the lab's enabled desktop pool.
That pool must not be in maintenance mode, must reference a Proxmox template
VMID, and the matching organization template must be imported and enabled.

## API map

| API | Minimum authority |
| --- | --- |
| `GET /api/classroom/assignments` | Authenticated tenant member; returns only the caller's assignments |
| `GET/POST /api/admin/lab-runs` | Tenant instructor |
| `PATCH /api/admin/lab-runs/{id}/state` | Instructor assigned to the class, or tenant admin/owner |
| `GET/POST /api/admin/lab-runs/{id}/assignments` | Instructor assigned to the class, or tenant admin/owner |
| `POST /api/admin/lab-runs/{id}/assignments/bulk` | Instructor assigned to the class, or tenant admin/owner |
| `DELETE /api/admin/lab-runs/{id}/assignments/{assignment_id}` | Instructor assigned to the class, or tenant admin/owner |

Classroom mutations emit structured audit actions beginning with
`classroom.`. Metadata contains identifiers and counts, never credentials.

## Migration and development data

Migration `20260908_0013` adds enrollment activation, `lab_runs`, and
`lab_assignments`. It does not invent assignments for existing development VMs.
After upgrading, existing student-owned VMs are intentionally hidden from
students until an instructor creates an active run and assignment. Tenant
instructors and administrators can still see those records and decide whether
to assign, migrate, or remove them.


## Unified setup API

The default teaching screen now uses the [guided setup](../user-guide/instructor-workflow.md).
`GET /api/admin/lab-setups/catalog` returns tenant-scoped database choices without
requiring a live hypervisor request. `POST /api/admin/lab-setups` creates the reviewed
setup atomically; `GET/PUT /api/admin/lab-setups/{run_id}` retrieves and edits it.
All routes require tenant instructor authority and enforce class ownership.
New login accounts additionally require the canonical platform Admin role.

A UUID submission receipt in migration `20260914_0019` prevents duplicate retries.
Receipts contain identifiers and a request fingerprint, never account passwords.
The same key cannot be reused for changed settings. Edits require the snapshot
ETag and lock the run/assignment rows; changed VM bindings invalidate the edit.
Roster removal does not delete class enrollment or silently detach a VM. Pool
changes and roster/quota reductions affecting a linked VM require separate cleanup.
The wizard cannot downgrade an active run to a draft or edit an ended run.
