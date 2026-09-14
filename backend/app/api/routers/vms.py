from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.models import (
    AuditLog,
    Class,
    Lab,
    LabAssignment,
    LabRun,
    ProxmoxCluster,
    ProxmoxClusterDefault,
    ProxmoxNode,
    StudentVM,
    User,
    VMTemplate,
)
from app.schemas.vm import (
    VMResponse,
    VMCreateResponse,
    VMOperationResponse,
    CreateVMRequest,
)
from app.services.proxmox import ProxmoxClient
from app.services.placement import choose_cluster_node, PlacementError
from app.services.proxmox_bootstrap import ProxmoxBootstrapService
from app.services.organization_access import (
    OrganizationContext,
    enforce_organization_role,
    get_current_organization,
    organization_role_at_least,
)
from app.services.classroom_access import (
    active_assignment_for_vm,
    assignment_for_provisioning,
    enforce_student_vm_operation,
)
from app.services.operation_service import (
    allocate_vmid,
    enqueue_operation,
    safe_vm_name,
)
from app.services.operation_service import _is_not_found

router = APIRouter()


def _scope_instructor_vms(q, db: Session, user_id: int, organization_id: int):
    taught_vm_ids = (
        db.query(LabAssignment.student_vm_id)
        .join(LabRun, LabRun.id == LabAssignment.lab_run_id)
        .join(Lab, Lab.id == LabRun.lab_id)
        .join(Class, Class.id == Lab.class_id)
        .filter(
            LabAssignment.organization_id == organization_id,
            LabRun.organization_id == organization_id,
            Lab.organization_id == organization_id,
            Class.organization_id == organization_id,
            Class.instructor_id == user_id,
            LabAssignment.student_vm_id.is_not(None),
        )
    )
    return q.filter(StudentVM.id.in_(taught_vm_ids))


def _get_vm_for_user(
    db: Session,
    user: User,
    vm_id: int,
    organization: OrganizationContext,
    operation: str = "view",
):
    q = db.query(StudentVM).filter(
        StudentVM.id == vm_id,
        StudentVM.organization_id == organization.id,
        StudentVM.deleted_at.is_(None),
    )
    if organization.role == "student":
        q = q.filter(StudentVM.owner_id == user.id)
    elif organization.role == "instructor" and not organization.break_glass:
        q = _scope_instructor_vms(q, db, user.id, organization.id)
    elif not organization_role_at_least(organization, "instructor"):
        raise HTTPException(status_code=403, detail="A valid role is required")
    vm = q.first()
    if not vm:
        raise HTTPException(status_code=404, detail="VM not found")
    if organization.role == "student":
        enforce_student_vm_operation(
            db,
            user_id=user.id,
            organization_id=organization.id,
            vm=vm,
            operation=operation,
        )
    return vm


@router.get("/vms", response_model=list[VMResponse])
async def list_vms(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(get_current_organization),
):
    q = db.query(StudentVM).filter(
        StudentVM.organization_id == organization.id,
        StudentVM.deleted_at.is_(None),
    )
    if organization.role == "student":
        q = q.filter(StudentVM.owner_id == user.id)
    elif organization.role == "instructor" and not organization.break_glass:
        q = _scope_instructor_vms(q, db, user.id, organization.id)
    elif not organization_role_at_least(organization, "instructor"):
        raise HTTPException(status_code=403, detail="A valid role is required")
    rows = q.all()
    if organization.role == "student":
        visible = []
        for vm in rows:
            access = active_assignment_for_vm(
                db, user_id=user.id, organization_id=organization.id, vm_id=vm.id
            )
            if not access:
                continue
            assignment, _run, lab = access
            vm.allowed_stop = lab.student_can_power_off
            vm.allowed_delete = False
            vm.allowed_terminal = lab.terminal_enabled
            vm.allowed_console = lab.console_enabled
            vm.allowed_rdp = lab.rdp_enabled
            vm.allowed_spice = lab.console_enabled
            vm.assignment_expires_at = assignment.expires_at
            visible.append(vm)
        rows = visible
    for vm in rows:
        try:
            data = await ProxmoxClient(vm.proxmox_cluster_id).get_vm_status(
                vm.proxmox_node, vm.vmid
            )
            vm.status = data.get("status", vm.status)
        except Exception:
            vm.status = vm.status or "error"
    db.commit()
    return rows


@router.post(
    "/vms", response_model=VMCreateResponse, status_code=status.HTTP_202_ACCEPTED
)
async def create_vm(
    payload: CreateVMRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(get_current_organization),
):
    template = (
        db.query(VMTemplate)
        .filter(
            VMTemplate.id == payload.template_id,
            VMTemplate.organization_id == organization.id,
        )
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if not template.enabled:
        raise HTTPException(status_code=409, detail="Template is disabled")

    assignment = None
    if organization.role == "student":
        assignment, _run = assignment_for_provisioning(
            db,
            assignment_id=payload.assignment_id,
            user_id=user.id,
            organization_id=organization.id,
            template_id=template.id,
        )
    elif not organization_role_at_least(organization, "instructor"):
        raise HTTPException(status_code=403, detail="A valid role is required")

    selected_node = template.proxmox_node
    placement_reason = "template default node"

    active_cluster = (
        db.query(ProxmoxCluster).filter(ProxmoxCluster.is_active.is_(True)).first()
    )
    if not active_cluster:
        raise HTTPException(
            status_code=409, detail="No active Proxmox cluster configured"
        )
    if template.proxmox_cluster_id not in (None, active_cluster.id):
        raise HTTPException(
            status_code=409, detail="Template belongs to a different Proxmox cluster"
        )
    if active_cluster:
        defaults = (
            db.query(ProxmoxClusterDefault)
            .filter(ProxmoxClusterDefault.cluster_id == active_cluster.id)
            .first()
        )
        placement_policy = getattr(defaults, "placement_policy", None) or (
            "prefer_default_then_balance"
            if getattr(defaults, "default_node", None)
            else "balanced"
        )
        default_node = getattr(defaults, "default_node", None)
        default_storage = getattr(defaults, "default_storage", None)
        default_bridge = getattr(defaults, "default_bridge", None)

        nodes = (
            db.query(ProxmoxNode)
            .filter(ProxmoxNode.cluster_id == active_cluster.id)
            .all()
        )
        node_dicts = [
            {
                "node_name": n.node_name,
                "status": n.status,
                "memory_total": n.memory_total,
                "memory_used": n.memory_used,
                "cpu_total": n.cpu_total,
                "cpu_used": n.cpu_used,
            }
            for n in nodes
        ]
        running_counts = {
            n.node_name: db.query(StudentVM)
            .filter(
                StudentVM.proxmox_node == n.node_name, StudentVM.status == "running"
            )
            .count()
            for n in nodes
        }

        svc = ProxmoxBootstrapService(db)
        templates = await svc.discover_templates(active_cluster)
        template_nodes = {
            str(t.get("node"))
            for t in templates
            if t.get("vmid") == template.source_vmid and t.get("node")
        }
        if not template_nodes:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": f"Template VMID {template.source_vmid} was not found on any online node."
                },
            )

        if default_storage:
            storage_rows = await svc.discover_storage(active_cluster)
            storage_nodes = {
                str(s.get("node"))
                for s in storage_rows
                if s.get("storage") == default_storage
                and str(s.get("active")).lower() not in {"0", "false", "none"}
            }
            allowed_nodes = template_nodes & storage_nodes
            if not allowed_nodes:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "No online Proxmox node has the requested storage/template combination."
                    },
                )
        else:
            allowed_nodes = template_nodes
        if default_bridge:
            network_rows = await svc.discover_networks(active_cluster)
            bridge_nodes = {
                str(n.get("node"))
                for n in network_rows
                if n.get("bridge") == default_bridge
            }
            allowed_nodes = allowed_nodes & bridge_nodes
            if not allowed_nodes:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": f"No eligible node has required bridge {default_bridge} for template placement."
                    },
                )

        try:
            decision = choose_cluster_node(
                node_dicts,
                running_counts,
                placement_policy,
                default_node,
                allowed_nodes=allowed_nodes,
            )
        except PlacementError as exc:
            raise HTTPException(status_code=409, detail={"error": str(exc)})

        selected_node = decision.selected_node
        placement_reason = decision.reason

    vmid = allocate_vmid(
        db,
        scope=f"proxmox-cluster:{active_cluster.id}",
        proxmox_cluster_id=active_cluster.id,
    )
    vm_name = safe_vm_name(user.username, payload.lab_name, vmid)

    vm = StudentVM(
        organization_id=organization.id,
        proxmox_cluster_id=active_cluster.id,
        owner_id=user.id,
        template_id=template.id,
        vm_name=vm_name,
        vmid=vmid,
        proxmox_node=selected_node,
        status="provisioning",
        operating_system=None,
        access_protocols="novnc",
    )
    db.add(vm)
    db.flush()

    db.add(
        AuditLog(
            organization_id=organization.id,
            actor_id=user.id,
            action="vm.create.placement",
            target_type="student_vm",
            target_id=str(vm.id),
        )
    )
    if assignment:
        assignment.student_vm_id = vm.id
    operation = enqueue_operation(
        db,
        organization_id=organization.id,
        requested_by=user.id,
        operation_type="vm.create",
        target_type="student_vm",
        target_id=str(vm.id),
        payload={
            "auto_start": payload.auto_start,
            "placement_reason": placement_reason,
        },
        idempotency_key=f"vm.create:{vm.id}",
    )
    db.commit()
    db.refresh(vm)
    return VMCreateResponse(
        **vm.__dict__,
        operation_id=operation.id,
        operation_state=operation.state,
        message=f"Provisioning queued. Placement: {placement_reason} ({selected_node})",
    )


def _queue_vm_action(
    db: Session,
    vm: StudentVM,
    user: User,
    organization: OrganizationContext,
    action: str,
) -> VMOperationResponse:
    operation = enqueue_operation(
        db,
        organization_id=organization.id,
        requested_by=user.id,
        operation_type=f"vm.{action}",
        target_type="student_vm",
        target_id=str(vm.id),
        payload={},
    )
    db.commit()
    return VMOperationResponse(
        operation_id=operation.id,
        state=operation.state,
        vm_id=vm.id,
        message=f"{action.capitalize()} queued",
    )


@router.post(
    "/vms/{id}/start",
    response_model=VMOperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_vm(
    id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(get_current_organization),
):
    vm = _get_vm_for_user(db, user, id, organization, "start")
    return _queue_vm_action(db, vm, user, organization, "start")


@router.post(
    "/vms/{id}/stop",
    response_model=VMOperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def stop_vm(
    id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(get_current_organization),
):
    vm = _get_vm_for_user(db, user, id, organization, "stop")
    return _queue_vm_action(db, vm, user, organization, "stop")


@router.post(
    "/vms/{id}/reboot",
    response_model=VMOperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reboot_vm(
    id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(get_current_organization),
):
    vm = _get_vm_for_user(db, user, id, organization, "reboot")
    return _queue_vm_action(db, vm, user, organization, "reboot")


@router.get("/vms/{id}/status", response_model=VMResponse)
async def refresh_vm_status(
    id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(get_current_organization),
):
    vm = _get_vm_for_user(db, user, id, organization, "view")
    try:
        vm.status = (
            await ProxmoxClient(vm.proxmox_cluster_id).get_vm_status(
                vm.proxmox_node, vm.vmid
            )
        ).get("status", vm.status)
    except Exception as exc:
        if _is_not_found(exc):
            vm.status = "missing"
        else:
            raise HTTPException(
                status_code=502, detail="Unable to query Proxmox VM status"
            )
    db.commit()
    db.refresh(vm)
    return vm


@router.get("/vms/{id}/delete-preview")
def delete_vm_preview(
    id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(get_current_organization),
):
    vm = _get_vm_for_user(db, user, id, organization, "delete")
    return {
        "vm_id": vm.id,
        "vmid": vm.vmid,
        "vm_name": vm.vm_name,
        "proxmox_node": vm.proxmox_node,
        "effects": [
            "Stop the VM if it is running",
            "Delete the VM from Proxmox",
            "Verify it is absent",
            "Retain a historical tombstone",
        ],
        "confirmation": f"DELETE {vm.vmid}",
    }


@router.delete(
    "/vms/{id}",
    response_model=VMOperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def delete_vm_record(
    id: int,
    confirmation: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(get_current_organization),
):
    vm = _get_vm_for_user(db, user, id, organization, "delete")
    if confirmation != f"DELETE {vm.vmid}":
        raise HTTPException(
            status_code=422, detail=f"confirmation must equal DELETE {vm.vmid}"
        )
    return _queue_vm_action(db, vm, user, organization, "delete")


@router.delete("/admin/lab-vms/{id}/app-record", response_model=dict)
async def delete_app_record_admin(
    id: int,
    force: bool = False,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(get_current_organization),
):
    enforce_organization_role(organization, "admin")
    vm = (
        db.query(StudentVM)
        .filter(
            StudentVM.id == id,
            StudentVM.organization_id == organization.id,
            StudentVM.deleted_at.is_(None),
        )
        .first()
    )
    if not vm:
        raise HTTPException(status_code=404, detail="App VM record not found")

    try:
        await ProxmoxClient(vm.proxmox_cluster_id).get_vm_status(
            vm.proxmox_node, vm.vmid
        )
    except Exception as exc:
        if not _is_not_found(exc):
            raise HTTPException(
                status_code=502,
                detail="Unable to verify Proxmox VM state; refusing app-record delete until Proxmox check succeeds",
            )
    else:
        raise HTTPException(
            status_code=409,
            detail="VM still exists in Proxmox; app-record cleanup requires a fresh not-found verification",
        )

    db.add(
        AuditLog(
            organization_id=organization.id,
            actor_id=_user.id,
            action="vm.app_record.delete",
            target_type="student_vm",
            target_id=str(vm.id),
        )
    )
    assignment = (
        db.query(LabAssignment).filter(LabAssignment.student_vm_id == vm.id).first()
    )
    if assignment:
        assignment.student_vm_id = None
        if assignment.status == "ready":
            assignment.status = "assigned"
    vm.deleted_at = datetime.utcnow()
    vm.status = "deleted"
    db.commit()
    return {
        "ok": True,
        "deleted": True,
        "deleted_app_vm_id": id,
        "vmid": vm.vmid,
        "deleted_record_only": True,
        "proxmox_vm_deleted": False,
        "message": "Archived the app VM record. No Proxmox VM was deleted.",
    }
