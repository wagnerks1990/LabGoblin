from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta

import httpx
from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import (
    AuditLog,
    Class,
    DurableOperation,
    Lab,
    LabAssignment,
    LabRun,
    Organization,
    OrganizationMembership,
    StudentVM,
    User,
    VMTemplate,
    VmidAllocator,
)
from app.services.proxmox import ProxmoxClient
from app.architecture.events import DomainEvent, VM_STARTED, bus
from app.services.classroom_access import (
    active_assignment_for_vm,
    enforce_student_vm_operation,
    utcnow as classroom_utcnow,
)
from app.services.organization_access import normalize_organization_role
from app.services.rbac import ROLE_ADMIN, get_role_name


class OperationAuthorizationError(RuntimeError):
    """Raised when a queued user operation is no longer authorized to execute."""


def _is_not_found(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None) == 404


def utcnow() -> datetime:
    return datetime.utcnow()


def allocate_vmid(
    db: Session,
    scope: str = "proxmox-cluster",
    *,
    proxmox_cluster_id: int | None = None,
) -> int:
    allocator = (
        db.query(VmidAllocator)
        .filter(VmidAllocator.scope == scope)
        .with_for_update()
        .first()
    )
    if not allocator:
        allocator = VmidAllocator(scope=scope, next_value=200000)
        db.add(allocator)
        db.flush()
    vmids = db.query(StudentVM.vmid)
    if proxmox_cluster_id is None and scope.startswith("proxmox-cluster:"):
        try:
            proxmox_cluster_id = int(scope.rsplit(":", 1)[1])
        except ValueError:
            proxmox_cluster_id = None
    if proxmox_cluster_id is not None:
        vmids = vmids.filter(StudentVM.proxmox_cluster_id == proxmox_cluster_id)
    largest = vmids.order_by(StudentVM.vmid.desc()).limit(1).scalar() or 199999
    value = max(allocator.next_value, largest + 1, 200000)
    allocator.next_value = value + 1
    allocator.updated_at = utcnow()
    return value


def safe_vm_name(username: str, lab_name: str, vmid: int) -> str:
    stem = re.sub(r"[^a-z0-9-]+", "-", f"{username}-{lab_name}".lower()).strip("-")[:45]
    return f"{stem or 'lab'}-{vmid}"


def enqueue_operation(
    db: Session,
    *,
    organization_id: int | None,
    requested_by: int | None,
    operation_type: str,
    target_type: str,
    target_id: str | None,
    payload: dict,
    idempotency_key: str | None = None,
) -> DurableOperation:
    key = idempotency_key or str(uuid.uuid4())
    existing = (
        db.query(DurableOperation)
        .filter(DurableOperation.idempotency_key == key)
        .first()
    )
    if existing:
        return existing
    row = DurableOperation(
        organization_id=organization_id,
        requested_by=requested_by,
        operation_type=operation_type,
        target_type=target_type,
        target_id=target_id,
        idempotency_key=key,
        payload_json=json.dumps(payload, sort_keys=True),
        state="queued",
        run_after=utcnow(),
    )
    db.add(row)
    db.flush()
    return row


def claim_operation(db: Session, worker_id: str) -> DurableOperation | None:
    now = utcnow()
    row = (
        db.query(DurableOperation)
        .filter(
            or_(
                DurableOperation.state == "queued",
                (DurableOperation.state == "running")
                & (DurableOperation.lease_expires_at < now),
            ),
            or_(
                DurableOperation.run_after.is_(None), DurableOperation.run_after <= now
            ),
        )
        .order_by(DurableOperation.created_at, DurableOperation.id)
        .with_for_update(skip_locked=True)
        .first()
    )
    if not row:
        return None
    row.state = "running"
    row.lease_owner = worker_id
    row.lease_expires_at = now + timedelta(seconds=settings.operation_lease_seconds)
    row.started_at = row.started_at or now
    row.attempts += 1
    db.commit()
    db.refresh(row)
    return row


def _validate_operation_authorization(
    db: Session,
    row: DurableOperation,
    vm: StudentVM,
    payload: dict,
) -> None:
    """Revalidate the authority represented by a queued operation."""
    if row.organization_id is None or row.organization_id != vm.organization_id:
        raise OperationAuthorizationError(
            "Operation and VM organization scopes no longer match"
        )

    organization = (
        db.query(Organization)
        .filter(
            Organization.id == row.organization_id,
            Organization.enabled.is_(True),
        )
        .first()
    )
    if organization is None:
        raise OperationAuthorizationError("Operation organization is not active")

    # Actor-less work is a separate, narrowly scoped system-cleanup capability.
    if row.requested_by is None:
        if (
            row.operation_type != "vm.delete"
            or payload.get("expiration_cleanup") is not True
        ):
            raise OperationAuthorizationError(
                "Actor-less operations are restricted to assignment cleanup"
            )
        assignment = (
            db.query(LabAssignment)
            .filter(
                LabAssignment.organization_id == row.organization_id,
                LabAssignment.student_vm_id == vm.id,
            )
            .first()
        )
        if assignment is None:
            raise OperationAuthorizationError(
                "System cleanup no longer owns an assignment for this VM"
            )
        expired = assignment.status in {"expired", "revoked"} or (
            assignment.expires_at is not None
            and classroom_utcnow() >= assignment.expires_at
        )
        if not expired:
            access = active_assignment_for_vm(
                db,
                user_id=assignment.user_id,
                organization_id=row.organization_id,
                vm_id=vm.id,
            )
            if access is not None:
                raise OperationAuthorizationError(
                    "System cleanup assignment is still active"
                )
        return

    actor = (
        db.query(User)
        .filter(User.id == row.requested_by, User.is_active.is_(True))
        .first()
    )
    if actor is None:
        raise OperationAuthorizationError("Requesting user is no longer active")

    # Platform Admin is the documented cross-tenant break-glass role.
    if get_role_name(actor) == ROLE_ADMIN:
        return
    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == row.organization_id,
            OrganizationMembership.user_id == actor.id,
            OrganizationMembership.is_active.is_(True),
        )
        .first()
    )
    member_role = normalize_organization_role(getattr(membership, "role", None))
    if membership is None or member_role is None:
        raise OperationAuthorizationError(
            "Requesting user no longer has organization access"
        )
    if member_role in {"admin", "owner"}:
        return
    if member_role == "instructor":
        teaches_vm = (
            db.query(LabAssignment.id)
            .join(LabRun, LabRun.id == LabAssignment.lab_run_id)
            .join(Lab, Lab.id == LabRun.lab_id)
            .join(Class, Class.id == Lab.class_id)
            .filter(
                LabAssignment.organization_id == row.organization_id,
                LabAssignment.student_vm_id == vm.id,
                LabRun.organization_id == row.organization_id,
                Lab.organization_id == row.organization_id,
                Class.organization_id == row.organization_id,
                Class.instructor_id == actor.id,
            )
            .first()
        )
        if teaches_vm is None:
            raise OperationAuthorizationError(
                "Instructor no longer teaches the class assigned to this VM"
            )
        return
    if vm.owner_id != actor.id:
        raise OperationAuthorizationError("Student no longer owns the target VM")
    try:
        enforce_student_vm_operation(
            db,
            user_id=actor.id,
            organization_id=row.organization_id,
            vm=vm,
            operation=row.operation_type.split(".", 1)[-1],
        )
    except HTTPException as exc:
        raise OperationAuthorizationError(
            str(exc.detail or "Student classroom authorization is no longer active")
        ) from exc


def _validate_absent_vm_operation(
    db: Session, row: DurableOperation, payload: dict
) -> None:
    """Validate the requester even when a target disappeared before execution."""
    if row.organization_id is None:
        raise OperationAuthorizationError("Operation has no organization scope")
    if row.requested_by is None:
        if (
            row.operation_type != "vm.delete"
            or payload.get("expiration_cleanup") is not True
        ):
            raise OperationAuthorizationError(
                "Actor-less operations are restricted to assignment cleanup"
            )
        return
    organization = (
        db.query(Organization)
        .filter(
            Organization.id == row.organization_id,
            Organization.enabled.is_(True),
        )
        .first()
    )
    actor = (
        db.query(User)
        .filter(User.id == row.requested_by, User.is_active.is_(True))
        .first()
    )
    if organization is None or actor is None:
        raise OperationAuthorizationError(
            "Operation organization or requesting user is no longer active"
        )
    if get_role_name(actor) == ROLE_ADMIN:
        return
    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == row.organization_id,
            OrganizationMembership.user_id == actor.id,
            OrganizationMembership.is_active.is_(True),
        )
        .first()
    )
    if normalize_organization_role(getattr(membership, "role", None)) is None:
        raise OperationAuthorizationError(
            "Requesting user no longer has organization access"
        )


async def execute_operation(db: Session, row: DurableOperation) -> None:
    payload = json.loads(row.payload_json or "{}")

    vm = None
    if row.target_type == "student_vm" and row.target_id:
        vm = db.query(StudentVM).filter(StudentVM.id == int(row.target_id)).first()
        if vm is not None:
            _validate_operation_authorization(db, row, vm, payload)
        else:
            _validate_absent_vm_operation(db, row, payload)

    def renew_lease() -> None:
        row.lease_expires_at = utcnow() + timedelta(
            seconds=settings.operation_lease_seconds
        )
        db.commit()

    task_warnings = []

    async def wait_for_task(
        proxmox: ProxmoxClient, node: str, upid: str, timeout_seconds: int
    ) -> None:
        allow_warnings = row.operation_type in {"vm.start", "vm.stop", "vm.reboot"} or (
            row.operation_type == "vm.create"
            and payload.get("_phase") == "start_submitted"
        )
        task = await proxmox.wait_for_task(
            node,
            upid,
            timeout_seconds=timeout_seconds,
            on_poll=renew_lease,
            allow_warnings=allow_warnings,
        )
        if isinstance(task, dict) and str(task.get("exitstatus", "")).startswith(
            "WARNINGS:"
        ):
            task_warnings.append({"task_id": upid, "message": task["exitstatus"]})

    def persist_task(upid: object, phase: str | None = None) -> str | None:
        row.proxmox_upid = str(upid or "") or None
        if phase:
            payload["_phase"] = phase
            row.payload_json = json.dumps(payload, sort_keys=True)
        renew_lease()
        return row.proxmox_upid

    if row.operation_type == "vm.create":
        if not vm:
            raise RuntimeError("VM record no longer exists")
        template = db.query(VMTemplate).filter(VMTemplate.id == vm.template_id).first()
        if not template:
            raise RuntimeError("VM template no longer exists")
        proxmox = ProxmoxClient(vm.proxmox_cluster_id)
        phase = payload.get("_phase")
        if row.proxmox_upid and phase == "start_submitted":
            await wait_for_task(
                proxmox,
                vm.proxmox_node,
                row.proxmox_upid,
                settings.operation_task_timeout_seconds,
            )
            live = await proxmox.get_vm_status(vm.proxmox_node, vm.vmid)
            if live.get("status") != "running":
                raise RuntimeError("Proxmox did not observe the VM running after start")
        else:
            if row.proxmox_upid:
                await wait_for_task(
                    proxmox,
                    vm.proxmox_node,
                    row.proxmox_upid,
                    settings.operation_clone_timeout_seconds,
                )
            else:
                if await proxmox.vm_exists(vm.vmid):
                    raise RuntimeError(
                        f"VMID {vm.vmid} already exists in Proxmox and is not owned by this operation"
                    )
                _validate_operation_authorization(db, row, vm, payload)
                response = await proxmox.clone_vm(
                    vm.proxmox_node, template.source_vmid, vm.vmid, vm.vm_name
                )
                persist_task(response.get("data"), "clone_submitted")
                if not row.proxmox_upid:
                    raise RuntimeError("Proxmox clone did not return a task identifier")
                await wait_for_task(
                    proxmox,
                    vm.proxmox_node,
                    row.proxmox_upid,
                    settings.operation_clone_timeout_seconds,
                )
            live = await proxmox.get_vm_status(vm.proxmox_node, vm.vmid)
        vm.status = live.get("status", "stopped")
        if payload.get("auto_start") and vm.status != "running":
            _validate_operation_authorization(db, row, vm, payload)
            response = await proxmox.start_vm(vm.proxmox_node, vm.vmid)
            start_upid = response.get("data") if isinstance(response, dict) else None
            persist_task(start_upid, "start_submitted")
            if not row.proxmox_upid:
                raise RuntimeError("Proxmox start did not return a task identifier")
            await wait_for_task(
                proxmox,
                vm.proxmox_node,
                row.proxmox_upid,
                settings.operation_task_timeout_seconds,
            )
            vm.status = (await proxmox.get_vm_status(vm.proxmox_node, vm.vmid)).get(
                "status", vm.status
            )
            if vm.status != "running":
                raise RuntimeError("Proxmox did not observe the VM running after start")
        assignment = (
            db.query(LabAssignment).filter(LabAssignment.student_vm_id == vm.id).first()
        )
        if assignment:
            assignment.status = "ready"
        result = {
            "vm_id": vm.id,
            "vmid": vm.vmid,
            "status": vm.status,
            "node": vm.proxmox_node,
        }
    elif row.operation_type in {"vm.start", "vm.stop", "vm.reboot"}:
        if not vm:
            raise RuntimeError("VM record no longer exists")
        proxmox = ProxmoxClient(vm.proxmox_cluster_id)
        action = row.operation_type.split(".")[1]
        if not row.proxmox_upid:
            _validate_operation_authorization(db, row, vm, payload)
            response = await getattr(proxmox, f"{action}_vm")(vm.proxmox_node, vm.vmid)
            persist_task(response.get("data") if isinstance(response, dict) else None)
            if not row.proxmox_upid:
                raise RuntimeError(f"Proxmox {action} did not return a task identifier")
        await wait_for_task(
            proxmox,
            vm.proxmox_node,
            row.proxmox_upid,
            settings.operation_task_timeout_seconds,
        )
        vm.status = (await proxmox.get_vm_status(vm.proxmox_node, vm.vmid)).get(
            "status", vm.status
        )
        expected_status = "stopped" if action == "stop" else "running"
        if vm.status != expected_status:
            raise RuntimeError(
                f"Proxmox did not observe the VM {expected_status} after {action}"
            )
        result = {"vm_id": vm.id, "vmid": vm.vmid, "status": vm.status}
    elif row.operation_type == "vm.delete":
        if not vm:
            result = {"deleted": True, "already_absent": True}
        else:
            proxmox = ProxmoxClient(vm.proxmox_cluster_id)
            if await proxmox.vm_exists(vm.vmid):
                try:
                    phase = payload.get("_phase")
                    if (
                        phase in {"stop_submitted", "delete_submitted"}
                        and row.proxmox_upid
                    ):
                        timeout = (
                            settings.operation_delete_timeout_seconds
                            if phase == "delete_submitted"
                            else settings.operation_task_timeout_seconds
                        )
                        await wait_for_task(
                            proxmox, vm.proxmox_node, row.proxmox_upid, timeout
                        )
                        if phase == "stop_submitted":
                            stopped = await proxmox.get_vm_status(
                                vm.proxmox_node, vm.vmid
                            )
                            if stopped.get("status") != "stopped":
                                raise RuntimeError(
                                    "Proxmox did not observe the VM stopped before delete"
                                )
                            row.proxmox_upid = None
                            payload["_phase"] = "stopped"
                            row.payload_json = json.dumps(payload, sort_keys=True)
                            renew_lease()

                    live = await proxmox.get_vm_status(vm.proxmox_node, vm.vmid)
                    if (
                        live.get("status") == "running"
                        and payload.get("_phase") != "delete_submitted"
                    ):
                        _validate_operation_authorization(db, row, vm, payload)
                        stop = await proxmox.stop_vm(vm.proxmox_node, vm.vmid)
                        stop_upid = stop.get("data") if isinstance(stop, dict) else None
                        persist_task(stop_upid, "stop_submitted")
                        if not row.proxmox_upid:
                            raise RuntimeError(
                                "Proxmox stop did not return a task identifier before delete"
                            )
                        await wait_for_task(
                            proxmox,
                            vm.proxmox_node,
                            row.proxmox_upid,
                            settings.operation_task_timeout_seconds,
                        )
                        stopped = await proxmox.get_vm_status(vm.proxmox_node, vm.vmid)
                        if stopped.get("status") != "stopped":
                            raise RuntimeError(
                                "Proxmox did not observe the VM stopped before delete"
                            )
                        row.proxmox_upid = None
                        payload["_phase"] = "stopped"
                        row.payload_json = json.dumps(payload, sort_keys=True)
                        renew_lease()
                    if payload.get("_phase") != "delete_submitted":
                        _validate_operation_authorization(db, row, vm, payload)
                        response = await proxmox.delete_vm(vm.proxmox_node, vm.vmid)
                        persist_task(response.get("data"), "delete_submitted")
                        if not row.proxmox_upid:
                            raise RuntimeError(
                                "Proxmox delete did not return a task identifier"
                            )
                        await wait_for_task(
                            proxmox,
                            vm.proxmox_node,
                            row.proxmox_upid,
                            settings.operation_delete_timeout_seconds,
                        )
                    try:
                        await proxmox.get_vm_status(vm.proxmox_node, vm.vmid)
                        raise RuntimeError(
                            "Proxmox still reports the VM after deletion"
                        )
                    except Exception as exc:
                        if not _is_not_found(exc):
                            raise
                except Exception as exc:
                    if not (
                        _is_not_found(exc)
                        or (
                            isinstance(exc, httpx.HTTPStatusError)
                            and exc.response.status_code == 500
                        )
                    ):
                        raise
                    if await proxmox.vm_exists(vm.vmid):
                        raise
            assignment = (
                db.query(LabAssignment)
                .filter(LabAssignment.student_vm_id == vm.id)
                .first()
            )
            if assignment:
                assignment.student_vm_id = None
                assignment.status = (
                    "expired" if payload.get("expiration_cleanup") else "assigned"
                )
            result = {"deleted": True, "vm_id": vm.id, "vmid": vm.vmid}
            vm.deleted_at = utcnow()
            vm.status = "deleted"
    else:
        raise RuntimeError(f"Unsupported operation type: {row.operation_type}")

    if task_warnings:
        result["warnings"] = task_warnings
    row.state = "succeeded"
    row.result_json = json.dumps(result, sort_keys=True)
    row.error = None
    row.finished_at = utcnow()
    row.lease_owner = None
    row.lease_expires_at = None
    db.add(
        AuditLog(
            organization_id=row.organization_id,
            actor_id=row.requested_by,
            action=row.operation_type,
            target_type=row.target_type,
            target_id=row.target_id or "",
            outcome="success",
        )
    )
    db.commit()
    if row.operation_type == "vm.start":
        bus.publish(
            DomainEvent(
                name=VM_STARTED,
                payload={
                    "organization_id": row.organization_id,
                    "vm_id": int(row.target_id),
                    "actor_id": row.requested_by,
                },
            )
        )


def fail_or_retry(db: Session, row: DurableOperation, exc: Exception) -> None:
    row.error = str(exc)[:2048]
    row.lease_owner = None
    row.lease_expires_at = None
    if row.attempts < settings.operation_max_attempts:
        row.state = "queued"
        row.run_after = utcnow() + timedelta(seconds=min(60, 2**row.attempts))
    else:
        row.state = "failed"
        row.finished_at = utcnow()
        vm = (
            db.query(StudentVM).filter(StudentVM.id == int(row.target_id)).first()
            if row.target_type == "student_vm" and row.target_id
            else None
        )
        if vm and row.operation_type == "vm.create":
            vm.status = "error"
    db.add(
        AuditLog(
            organization_id=row.organization_id,
            actor_id=row.requested_by,
            action=row.operation_type,
            target_type=row.target_type,
            target_id=row.target_id or "",
            outcome="failure",
            message=row.error,
        )
    )
    db.commit()


def cancel_unauthorized_operation(
    db: Session, row: DurableOperation, exc: OperationAuthorizationError
) -> None:
    """Permanently cancel stale queued authority and audit the denial reason."""
    row.state = "cancelled"
    row.error = str(exc)[:2048]
    row.finished_at = utcnow()
    row.lease_owner = None
    row.lease_expires_at = None
    db.add(
        AuditLog(
            organization_id=row.organization_id,
            actor_id=row.requested_by,
            action=row.operation_type,
            target_type=row.target_type,
            target_id=row.target_id or "",
            outcome="failure",
            message=f"Execution authorization cancelled: {row.error}"[:512],
        )
    )
    db.commit()
