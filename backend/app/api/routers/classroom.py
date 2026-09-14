from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routers.classes_labs import _class_or_404
from app.db.session import get_db
from app.models.models import (
    DesktopPool,
    Enrollment,
    Lab,
    LabAssignment,
    LabRun,
    OrganizationMembership,
    StudentVM,
    User,
    VMTemplate,
)
from app.schemas.classes_labs import (
    LabAssignmentBulkCreate,
    LabAssignmentCreate,
    LabAssignmentOut,
    LabRunCreate,
    LabRunOut,
    LabRunStateChange,
)
from app.schemas.common import ApiEnvelope
from app.services.audit_service import record_audit_event
from app.services.classroom_access import (
    as_utc_naive,
    assignment_effectively_open,
    run_effectively_open,
    utcnow,
)
from app.services.organization_access import (
    OrganizationContext,
    get_current_organization,
    require_organization_role,
)
from app.services.operation_service import enqueue_operation

router = APIRouter()

RUN_TRANSITIONS = {
    "draft": {"schedule": "scheduled", "activate": "active", "cancel": "cancelled"},
    "scheduled": {"activate": "active", "cancel": "cancelled"},
    "active": {"end": "ended", "cancel": "cancelled"},
    "ended": {},
    "cancelled": {},
}


def _lab_for_user(
    db: Session, lab_id: int, organization: OrganizationContext, user: User
) -> Lab:
    lab = (
        db.query(Lab)
        .filter(Lab.id == lab_id, Lab.organization_id == organization.id)
        .first()
    )
    if not lab:
        raise HTTPException(status_code=404, detail="Lab not found")
    _class_or_404(db, lab.class_id, organization, user)
    return lab


def _run_for_user(
    db: Session,
    run_id: int,
    organization: OrganizationContext,
    user: User,
    *,
    lock: bool = False,
) -> tuple[LabRun, Lab]:
    query = db.query(LabRun).filter(
        LabRun.id == run_id, LabRun.organization_id == organization.id
    )
    run = query.with_for_update().first() if lock else query.first()
    if not run:
        raise HTTPException(status_code=404, detail="Lab run not found")
    return run, _lab_for_user(db, run.lab_id, organization, user)


def _default_template(db: Session, lab: Lab) -> VMTemplate:
    pool = (
        db.query(DesktopPool)
        .filter(
            DesktopPool.id == lab.default_pool_id,
            DesktopPool.organization_id == lab.organization_id,
            DesktopPool.enabled.is_(True),
            DesktopPool.maintenance_mode.is_(False),
        )
        .first()
    )
    if not pool or not pool.template_vmid:
        raise HTTPException(
            status_code=409, detail="The lab pool does not have an enabled template"
        )
    template = (
        db.query(VMTemplate)
        .filter(
            VMTemplate.organization_id == lab.organization_id,
            VMTemplate.source_vmid == pool.template_vmid,
            VMTemplate.enabled.is_(True),
        )
        .first()
    )
    if not template:
        raise HTTPException(
            status_code=409, detail="The lab pool template is not imported and enabled"
        )
    return template


def _run_out(db: Session, run: LabRun) -> LabRun:
    run.effective_open = run_effectively_open(run)
    run.assignment_count = (
        db.query(LabAssignment).filter(LabAssignment.lab_run_id == run.id).count()
    )
    return run


def _assignment_out(db: Session, row: LabAssignment) -> LabAssignment:
    run = db.query(LabRun).filter(LabRun.id == row.lab_run_id).first()
    lab = db.query(Lab).filter(Lab.id == run.lab_id).first() if run else None
    template = db.query(VMTemplate).filter(VMTemplate.id == row.template_id).first()
    user = db.query(User).filter(User.id == row.user_id).first()
    row.run_name = run.name if run else None
    row.lab_name = lab.name if lab else None
    row.template_name = template.name if template else None
    row.username = user.username if user else None
    enrollment = (
        db.query(Enrollment)
        .filter(
            Enrollment.class_id == lab.class_id,
            Enrollment.user_id == row.user_id,
            Enrollment.is_active.is_(True),
        )
        .first()
        if lab
        else None
    )
    row.access_open = bool(run and enrollment and assignment_effectively_open(row, run))
    row.can_provision = bool(
        row.access_open
        and template
        and template.enabled
        and row.student_vm_id is None
        and row.status == "assigned"
    )
    row.instructions = lab.description if lab else None
    row.starts_at = run.starts_at if run else None
    row.ends_at = run.ends_at if run else None
    row.run_state = run.state if run else None
    return row


@router.get(
    "/classroom/assignments", response_model=ApiEnvelope[list[LabAssignmentOut]]
)
def my_assignments(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(get_current_organization),
):
    rows = (
        db.query(LabAssignment)
        .filter(
            LabAssignment.organization_id == organization.id,
            LabAssignment.user_id == user.id,
            LabAssignment.status.in_(["assigned", "ready"]),
        )
        .order_by(LabAssignment.id.desc())
        .all()
    )
    return ApiEnvelope(success=True, data=[_assignment_out(db, row) for row in rows])


@router.get("/admin/lab-runs", response_model=ApiEnvelope[list[LabRunOut]])
def list_lab_runs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(
        require_organization_role("instructor")
    ),
):
    rows = (
        db.query(LabRun)
        .filter(LabRun.organization_id == organization.id)
        .order_by(LabRun.id.desc())
        .all()
    )
    visible = []
    for row in rows:
        try:
            _lab_for_user(db, row.lab_id, organization, user)
            visible.append(_run_out(db, row))
        except HTTPException:
            continue
    return ApiEnvelope(success=True, data=visible)


@router.post(
    "/admin/lab-runs",
    response_model=ApiEnvelope[LabRunOut],
    status_code=status.HTTP_201_CREATED,
)
def create_lab_run(
    payload: LabRunCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(
        require_organization_role("instructor")
    ),
):
    lab = _lab_for_user(db, payload.lab_id, organization, user)
    if not payload.name.strip():
        raise HTTPException(status_code=422, detail="Run name is required")
    starts_at = as_utc_naive(payload.starts_at or lab.starts_at)
    ends_at = as_utc_naive(payload.ends_at or lab.ends_at)
    if starts_at and ends_at and starts_at >= ends_at:
        raise HTTPException(status_code=422, detail="starts_at must be before ends_at")
    if payload.max_vms_per_student < 1 or payload.max_vms_per_student > 10:
        raise HTTPException(
            status_code=422, detail="max_vms_per_student must be between 1 and 10"
        )
    row = LabRun(
        organization_id=organization.id,
        lab_id=lab.id,
        name=payload.name.strip(),
        starts_at=starts_at,
        ends_at=ends_at,
        max_vms_per_student=payload.max_vms_per_student,
        state="draft",
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    record_audit_event(
        db,
        actor_id=user.id,
        organization_id=organization.id,
        action="classroom.run_created",
        target_type="lab_run",
        target_id=str(row.id),
        metadata={"lab_id": lab.id},
    )
    db.commit()
    db.refresh(row)
    return ApiEnvelope(success=True, data=_run_out(db, row))


@router.patch("/admin/lab-runs/{run_id}/state", response_model=ApiEnvelope[LabRunOut])
def change_lab_run_state(
    run_id: int,
    payload: LabRunStateChange,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(
        require_organization_role("instructor")
    ),
):
    run, _lab = _run_for_user(db, run_id, organization, user, lock=True)
    action = payload.action.strip().lower()
    next_state = RUN_TRANSITIONS.get(run.state, {}).get(action)
    if not next_state:
        raise HTTPException(
            status_code=409, detail=f"Cannot {action or 'change'} a {run.state} lab run"
        )
    if (
        action in {"end", "cancel"}
        and payload.confirmation != f"{action.upper()} {run.id}"
    ):
        raise HTTPException(
            status_code=422, detail=f"confirmation must equal {action.upper()} {run.id}"
        )
    now = utcnow()
    if next_state == "scheduled" and not run.starts_at:
        raise HTTPException(
            status_code=409, detail="A scheduled lab run requires a start time"
        )
    if next_state == "active":
        if run.starts_at and now < run.starts_at:
            raise HTTPException(
                status_code=409,
                detail="Lab run cannot activate before its scheduled start",
            )
        if run.ends_at and now >= run.ends_at:
            raise HTTPException(status_code=409, detail="Lab run has already expired")
        run.activated_at = now
    if next_state in {"ended", "cancelled"}:
        run.ended_at = now
        for assignment in (
            db.query(LabAssignment)
            .filter(
                LabAssignment.lab_run_id == run.id,
                LabAssignment.status.in_(["assigned", "ready"]),
            )
            .all()
        ):
            assignment.status = "expired" if next_state == "ended" else "revoked"
            if assignment.student_vm_id:
                enqueue_operation(
                    db,
                    organization_id=organization.id,
                    requested_by=user.id,
                    operation_type="vm.delete",
                    target_type="student_vm",
                    target_id=str(assignment.student_vm_id),
                    payload={"expiration_cleanup": True, "lab_run_id": run.id},
                    idempotency_key=f"lab-run-close:{run.id}:vm:{assignment.student_vm_id}",
                )
    run.state = next_state
    record_audit_event(
        db,
        actor_id=user.id,
        organization_id=organization.id,
        action=f"classroom.run_{next_state}",
        target_type="lab_run",
        target_id=str(run.id),
    )
    db.commit()
    db.refresh(run)
    return ApiEnvelope(success=True, data=_run_out(db, run))


@router.get("/admin/lab-runs/{run_id}/close-preview", response_model=ApiEnvelope[dict])
def close_lab_run_preview(
    run_id: int,
    action: str = "end",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(
        require_organization_role("instructor")
    ),
):
    run, _lab = _run_for_user(db, run_id, organization, user)
    if action not in {"end", "cancel"}:
        raise HTTPException(status_code=422, detail="action must be end or cancel")
    assignments = (
        db.query(LabAssignment).filter(LabAssignment.lab_run_id == run.id).all()
    )
    vm_ids = [row.student_vm_id for row in assignments if row.student_vm_id]
    return ApiEnvelope(
        success=True,
        data={
            "run_id": run.id,
            "current_state": run.state,
            "assignments_affected": len(assignments),
            "vm_deletions_to_queue": len(vm_ids),
            "student_vm_ids": vm_ids,
            "confirmation": f"{action.upper()} {run.id}",
        },
    )


def _create_assignment(
    db: Session, run: LabRun, lab: Lab, payload: LabAssignmentCreate
) -> tuple[LabAssignment, bool]:
    enrollment = (
        db.query(Enrollment)
        .filter(
            Enrollment.class_id == lab.class_id,
            Enrollment.user_id == payload.user_id,
            Enrollment.is_active.is_(True),
        )
        .first()
    )
    if not enrollment:
        raise HTTPException(
            status_code=422,
            detail="Student must have an active enrollment in this class",
        )
    if (enrollment.role or "student").lower() != "student":
        raise HTTPException(
            status_code=422, detail="Only student enrollments receive VM assignments"
        )
    if (
        not db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == run.organization_id,
            OrganizationMembership.user_id == payload.user_id,
            OrganizationMembership.is_active.is_(True),
        )
        .first()
    ):
        raise HTTPException(
            status_code=422,
            detail="Student must be an active member of this organization",
        )
    template = (
        _default_template(db, lab)
        if payload.template_id is None
        else db.query(VMTemplate)
        .filter(
            VMTemplate.id == payload.template_id,
            VMTemplate.organization_id == run.organization_id,
            VMTemplate.enabled.is_(True),
        )
        .first()
    )
    if not template:
        raise HTTPException(
            status_code=422, detail="Template is not enabled in this organization"
        )
    existing_count = (
        db.query(LabAssignment)
        .filter(
            LabAssignment.lab_run_id == run.id,
            LabAssignment.user_id == payload.user_id,
            LabAssignment.status != "revoked",
        )
        .count()
    )
    slot = payload.slot_index or existing_count + 1
    if slot < 1 or slot > run.max_vms_per_student:
        raise HTTPException(
            status_code=409, detail="Student assignment quota reached for this lab run"
        )
    existing = (
        db.query(LabAssignment)
        .filter(
            LabAssignment.lab_run_id == run.id,
            LabAssignment.user_id == payload.user_id,
            LabAssignment.slot_index == slot,
        )
        .first()
    )
    if existing:
        if existing.status == "revoked" and existing.student_vm_id is None:
            existing.template_id = template.id
            existing.status = "assigned"
            existing.expires_at = run.ends_at
            return existing, True
        return existing, False
    row = LabAssignment(
        organization_id=run.organization_id,
        lab_run_id=run.id,
        user_id=payload.user_id,
        template_id=template.id,
        slot_index=slot,
        status="assigned",
        expires_at=run.ends_at,
    )
    db.add(row)
    db.flush()
    return row, True


@router.get(
    "/admin/lab-runs/{run_id}/assignments",
    response_model=ApiEnvelope[list[LabAssignmentOut]],
)
def list_run_assignments(
    run_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(
        require_organization_role("instructor")
    ),
):
    _run_for_user(db, run_id, organization, user)
    rows = (
        db.query(LabAssignment)
        .filter(
            LabAssignment.lab_run_id == run_id,
            LabAssignment.organization_id == organization.id,
        )
        .order_by(LabAssignment.user_id, LabAssignment.slot_index)
        .all()
    )
    return ApiEnvelope(success=True, data=[_assignment_out(db, row) for row in rows])


@router.post(
    "/admin/lab-runs/{run_id}/assignments",
    response_model=ApiEnvelope[LabAssignmentOut],
    status_code=status.HTTP_201_CREATED,
)
def create_run_assignment(
    run_id: int,
    payload: LabAssignmentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(
        require_organization_role("instructor")
    ),
):
    run, lab = _run_for_user(db, run_id, organization, user, lock=True)
    if run.state in {"ended", "cancelled"}:
        raise HTTPException(
            status_code=409, detail="Cannot assign an ended or cancelled lab run"
        )
    row, created = _create_assignment(db, run, lab, payload)
    if created:
        record_audit_event(
            db,
            actor_id=user.id,
            organization_id=organization.id,
            action="classroom.assignment_created",
            target_type="lab_assignment",
            target_id=str(row.id),
            metadata={"lab_run_id": run.id, "user_id": row.user_id},
        )
    db.commit()
    db.refresh(row)
    return ApiEnvelope(success=True, data=_assignment_out(db, row))


@router.post(
    "/admin/lab-runs/{run_id}/assignments/bulk", response_model=ApiEnvelope[dict]
)
def bulk_create_run_assignments(
    run_id: int,
    payload: LabAssignmentBulkCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(
        require_organization_role("instructor")
    ),
):
    run, lab = _run_for_user(db, run_id, organization, user, lock=True)
    if run.state in {"ended", "cancelled"}:
        raise HTTPException(
            status_code=409, detail="Cannot assign an ended or cancelled lab run"
        )
    if (
        payload.slots_per_student < 1
        or payload.slots_per_student > run.max_vms_per_student
    ):
        raise HTTPException(
            status_code=422, detail="slots_per_student exceeds the lab run quota"
        )
    enrollments = [
        row
        for row in db.query(Enrollment)
        .filter(Enrollment.class_id == lab.class_id, Enrollment.is_active.is_(True))
        .all()
        if (row.role or "student").lower() == "student"
    ]
    created = 0
    for enrollment in enrollments:
        for slot in range(1, payload.slots_per_student + 1):
            _row, was_created = _create_assignment(
                db,
                run,
                lab,
                LabAssignmentCreate(user_id=enrollment.user_id, slot_index=slot),
            )
            created += int(was_created)
    record_audit_event(
        db,
        actor_id=user.id,
        organization_id=organization.id,
        action="classroom.assignments_bulk_created",
        target_type="lab_run",
        target_id=str(run.id),
        metadata={"created": created, "enrollments": len(enrollments)},
    )
    db.commit()
    return ApiEnvelope(
        success=True,
        data={
            "created": created,
            "enrollments": len(enrollments),
            "slots_per_student": payload.slots_per_student,
        },
    )


@router.post(
    "/admin/lab-runs/{run_id}/vms/{action}",
    response_model=ApiEnvelope[dict],
    status_code=status.HTTP_202_ACCEPTED,
)
def bulk_vm_action(
    run_id: int,
    action: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(
        require_organization_role("instructor")
    ),
):
    _run_for_user(db, run_id, organization, user)
    if action not in {"start", "stop", "reboot", "delete"}:
        raise HTTPException(
            status_code=422, detail="Action must be start, stop, reboot, or delete"
        )
    assignments = (
        db.query(LabAssignment)
        .filter(
            LabAssignment.lab_run_id == run_id,
            LabAssignment.organization_id == organization.id,
            LabAssignment.student_vm_id.is_not(None),
        )
        .all()
    )
    operation_ids = []
    for assignment in assignments:
        vm = (
            db.query(StudentVM).filter(StudentVM.id == assignment.student_vm_id).first()
        )
        if not vm:
            continue
        operation = enqueue_operation(
            db,
            organization_id=organization.id,
            requested_by=user.id,
            operation_type=f"vm.{action}",
            target_type="student_vm",
            target_id=str(vm.id),
            payload={"lab_run_id": run_id, "expiration_cleanup": action == "delete"},
        )
        operation_ids.append(operation.id)
    record_audit_event(
        db,
        actor_id=user.id,
        organization_id=organization.id,
        action=f"classroom.bulk_{action}",
        target_type="lab_run",
        target_id=str(run_id),
        metadata={"operation_ids": operation_ids},
    )
    db.commit()
    return ApiEnvelope(
        success=True,
        data={
            "queued": len(operation_ids),
            "operation_ids": operation_ids,
            "action": action,
        },
    )


@router.delete(
    "/admin/lab-runs/{run_id}/assignments/{assignment_id}",
    response_model=ApiEnvelope[dict],
)
def revoke_run_assignment(
    run_id: int,
    assignment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(
        require_organization_role("instructor")
    ),
):
    _run_for_user(db, run_id, organization, user, lock=True)
    row = (
        db.query(LabAssignment)
        .filter(
            LabAssignment.id == assignment_id,
            LabAssignment.lab_run_id == run_id,
            LabAssignment.organization_id == organization.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Lab assignment not found")
    row.status = "revoked"
    record_audit_event(
        db,
        actor_id=user.id,
        organization_id=organization.id,
        action="classroom.assignment_revoked",
        target_type="lab_assignment",
        target_id=str(row.id),
        metadata={"student_vm_id": row.student_vm_id},
    )
    db.commit()
    return ApiEnvelope(
        success=True,
        data={"revoked": True, "id": row.id, "student_vm_id": row.student_vm_id},
    )
