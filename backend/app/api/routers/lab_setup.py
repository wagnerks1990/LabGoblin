"""One reviewed transaction for classroom setup; no hypervisor side effects."""

import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routers.classes_labs import _class_or_404, _class_query
from app.api.routers.classroom import (
    _create_assignment,
    _default_template,
    _run_for_user,
)
from app.db.session import get_db
from app.models.models import (
    Class,
    DesktopPool,
    Enrollment,
    Lab,
    LabAssignment,
    LabRun,
    LabSetupReceipt,
    OrganizationMembership,
    Role,
    User,
    VMTemplate,
)
from app.schemas.classes_labs import LabAssignmentCreate
from app.schemas.lab_setup import LabSetupOut, LabSetupWrite, LabSetupCatalog
from app.services.audit_service import record_audit_event
from app.services.classroom_access import as_utc_naive, utcnow
from app.services.organization_access import (
    OrganizationContext,
    enforce_organization_role,
    require_organization_role,
)
from app.services.security import hash_password, validate_password
from app.services.rbac import get_role_name, ROLE_ADMIN

router = APIRouter()
FLAGS = (
    "console_enabled",
    "rdp_enabled",
    "terminal_enabled",
    "student_can_power_off",
    "student_can_reset",
)


@router.get("/admin/lab-setups/catalog", response_model=LabSetupCatalog)
def setup_catalog(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(
        require_organization_role("instructor")
    ),
):
    classes = _class_query(db, organization, user).order_by(Class.name).all()
    class_ids = [row.id for row in classes]
    labs = (
        db.query(Lab)
        .filter(Lab.organization_id == organization.id, Lab.class_id.in_(class_ids))
        .all()
    )
    runs = (
        db.query(LabRun)
        .filter(
            LabRun.organization_id == organization.id,
            LabRun.lab_id.in_([row.id for row in labs]),
        )
        .order_by(LabRun.id.desc())
        .all()
    )
    pools = (
        db.query(DesktopPool)
        .filter(DesktopPool.organization_id == organization.id)
        .order_by(DesktopPool.name)
        .all()
    )
    templates = (
        db.query(VMTemplate)
        .filter(
            VMTemplate.organization_id == organization.id, VMTemplate.enabled.is_(True)
        )
        .order_by(VMTemplate.name)
        .all()
    )
    memberships = (
        db.query(OrganizationMembership, User)
        .join(User, User.id == OrganizationMembership.user_id)
        .filter(
            OrganizationMembership.organization_id == organization.id,
            OrganizationMembership.is_active.is_(True),
            User.is_active.is_(True),
        )
        .order_by(User.username)
        .all()
    )
    return {
        "classes": [{"id": r.id, "name": r.name, "term": r.term} for r in classes],
        "pools": [
            {
                "id": r.id,
                "name": r.name,
                "enabled": r.enabled,
                "template_vmid": r.template_vmid,
                "maintenance_mode": r.maintenance_mode,
            }
            for r in pools
        ],
        "templates": [
            {
                "id": r.id,
                "name": r.name,
                "enabled": r.enabled,
                "source_vmid": r.source_vmid,
            }
            for r in templates
        ],
        "members": [
            {
                "user_id": u.id,
                "username": u.username,
                "role": m.role,
                "is_active": m.is_active,
            }
            for m, u in memberships
        ],
        "runs": [
            {
                "id": r.id,
                "name": r.name,
                "state": r.state,
                "max_vms_per_student": r.max_vms_per_student,
                "assignment_count": db.query(LabAssignment)
                .filter(
                    LabAssignment.lab_run_id == r.id, LabAssignment.status != "revoked"
                )
                .count(),
            }
            for r in runs
        ],
    }


def _snapshot(db, run, lab):
    classroom = db.get(Class, lab.class_id)
    pool = db.get(DesktopPool, lab.default_pool_id)
    rows = (
        db.query(LabAssignment)
        .filter(LabAssignment.lab_run_id == run.id)
        .order_by(LabAssignment.id)
        .all()
    )
    current = [r for r in rows if r.status != "revoked"]
    data = dict(
        run_id=run.id,
        lab_id=lab.id,
        name=run.name,
        description=lab.description or "",
        class_id=lab.class_id,
        class_name=classroom.name,
        term=classroom.term or "",
        pool_id=lab.default_pool_id,
        pool_name=pool.name if pool else "Unavailable",
        student_ids=sorted({r.user_id for r in current}),
        starts_at=run.starts_at,
        ends_at=run.ends_at,
        slots=run.max_vms_per_student,
        state=run.state,
        assignment_count=len(current),
        **{flag: bool(getattr(lab, flag)) for flag in FLAGS},
    )
    # Include assignment bindings so a concurrent provision/revoke invalidates an edit.
    version = [
        data,
        [(r.id, r.student_vm_id, r.status, str(r.expires_at)) for r in rows],
    ]
    data["etag"] = hashlib.sha256(
        json.dumps(version, sort_keys=True, default=str).encode()
    ).hexdigest()
    return data


@router.get("/admin/lab-setups/{run_id}", response_model=LabSetupOut)
def get_setup(
    run_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(
        require_organization_role("instructor")
    ),
):
    run, lab = _run_for_user(db, run_id, organization, user)
    return _snapshot(db, run, lab)


def _new_students(db, payload, user, organization):
    if payload.new_students and get_role_name(user) != ROLE_ADMIN:
        raise HTTPException(
            403,
            "Only a platform administrator can create login accounts. Select existing organization members.",
        )
    ids = set(payload.student_ids)
    for user_id in ids:
        membership = (
            db.query(OrganizationMembership)
            .join(User, User.id == OrganizationMembership.user_id)
            .filter(
                OrganizationMembership.organization_id == organization.id,
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.is_active.is_(True),
                OrganizationMembership.role == "student",
                User.is_active.is_(True),
            )
            .first()
        )
        if not membership:
            raise HTTPException(
                422, "Choose active student members of this organization."
            )
    role = db.query(Role).filter(Role.name.ilike("student")).first()
    if payload.new_students and not role:
        raise HTTPException(409, "The student role is not configured.")
    for item in payload.new_students:
        username, email = item.username.strip(), item.email.strip()
        if not username or "@" not in email:
            raise HTTPException(422, "Each new student needs a username and email.")
        password = item.password.get_secret_value()
        validate_password(password)
        if len(password.encode("utf-8")) > 72:
            raise HTTPException(
                422, "Initial passwords must fit within 72 UTF-8 bytes."
            )
        if (
            db.query(User)
            .filter(or_(User.username == username, User.email == email))
            .first()
        ):
            raise HTTPException(
                409,
                "A requested account already exists. Select its organization membership instead.",
            )
        account = User(
            username=username,
            email=email,
            display_name=item.display_name,
            password_hash=hash_password(password),
            role_id=role.id,
            role=role.name,
            is_active=True,
            force_password_change=True,
        )
        db.add(account)
        db.flush()
        db.add(
            OrganizationMembership(
                organization_id=organization.id,
                user_id=account.id,
                role="student",
                is_active=True,
            )
        )
        ids.add(account.id)
        record_audit_event(
            db,
            actor_id=user.id,
            organization_id=organization.id,
            action="identity.user_created",
            target_type="user",
            target_id=str(account.id),
            metadata={"role": "Student"},
        )
    return ids


def _apply(db, payload, user, organization, run_id=None):
    enforce_organization_role(organization, "instructor")
    fingerprint = hashlib.sha256(
        payload.model_dump_json(exclude={"request_id"}).encode()
    ).hexdigest()
    receipt = db.get(LabSetupReceipt, str(payload.request_id))
    if receipt:
        if (
            receipt.actor_id != user.id
            or receipt.organization_id != organization.id
            or (run_id is not None and receipt.run_id != run_id)
        ):
            raise HTTPException(404, "Setup submission not found")
        if receipt.fingerprint != fingerprint:
            raise HTTPException(
                409,
                "This submission was already saved with different settings. Reload before editing.",
            )
        run, lab = _run_for_user(db, receipt.run_id, organization, user)
        return _snapshot(db, run, lab)
    starts, ends = as_utc_naive(payload.starts_at), as_utc_naive(payload.ends_at)
    if starts and ends and starts >= ends:
        raise HTTPException(422, "The end must be after the start.")
    if payload.state != "draft" and ends and ends <= utcnow():
        raise HTTPException(422, "Choose a future end time before opening the lab.")
    if payload.state == "scheduled" and not starts:
        raise HTTPException(422, "A scheduled lab needs a start time.")
    if payload.state == "active" and starts and starts > utcnow():
        raise HTTPException(422, "Use Scheduled for a future start time.")
    run, lab = (None, None)
    if run_id is not None:
        run, lab = _run_for_user(db, run_id, organization, user, lock=True)
        if run.state in {"ended", "cancelled"}:
            raise HTTPException(409, "Ended labs are read-only. Create a new setup.")
        db.query(LabAssignment).filter(
            LabAssignment.lab_run_id == run.id
        ).with_for_update().populate_existing().all()
        if payload.expected_etag != _snapshot(db, run, lab)["etag"]:
            raise HTTPException(
                409, "This lab changed since you opened it. Reload before saving."
            )
        if lab.class_id != payload.class_id:
            raise HTTPException(422, "An existing lab must remain in its class.")
        if (
            db.query(LabRun)
            .filter(LabRun.lab_id == lab.id, LabRun.id != run.id)
            .first()
        ):
            raise HTTPException(
                409,
                "This blueprint is shared by several runs. Edit it in detailed management.",
            )
        if run.state == "active" and payload.state != "active":
            raise HTTPException(
                409, "Use the reviewed End run action to close an active lab."
            )
    classroom = (
        _class_or_404(db, payload.class_id, organization, user)
        if payload.class_id
        else None
    )
    if classroom is None:
        classroom = Class(
            organization_id=organization.id,
            name=payload.class_name.strip(),
            term=payload.term,
            instructor_id=user.id,
        )
        db.add(classroom)
        db.flush()
    pool = None
    if payload.pool_id:
        pool = (
            db.query(DesktopPool)
            .filter(
                DesktopPool.id == payload.pool_id,
                DesktopPool.organization_id == organization.id,
                DesktopPool.enabled.is_(True),
                DesktopPool.maintenance_mode.is_(False),
            )
            .first()
        )
        if not pool:
            raise HTTPException(422, "Choose an enabled pool in this organization.")
    else:
        template = (
            db.query(VMTemplate)
            .filter(
                VMTemplate.id == payload.template_id,
                VMTemplate.organization_id == organization.id,
                VMTemplate.enabled.is_(True),
            )
            .first()
        )
        if not template or not template.source_vmid or not template.proxmox_node:
            raise HTTPException(
                422, "Choose an imported, enabled template with a source node."
            )
        pool = DesktopPool(
            organization_id=organization.id,
            name=payload.name.strip()[:115] + " pool",
            pool_type="persistent",
            template_vmid=template.source_vmid,
            template_node=template.proxmox_node,
            default_protocol="NOVNC",
            desired_size=0,
            enabled=True,
            maintenance_mode=False,
        )
        db.add(pool)
        db.flush()
    students = _new_students(db, payload, user, organization)
    if payload.state != "draft" and not students:
        raise HTTPException(422, "Add at least one student before opening the lab.")
    if lab is None:
        lab = Lab(
            organization_id=organization.id,
            class_id=classroom.id,
            name=payload.name.strip(),
            default_pool_id=pool.id,
        )
        db.add(lab)
        db.flush()
        run = LabRun(
            organization_id=organization.id,
            lab_id=lab.id,
            name=payload.name.strip(),
            state="draft",
            max_vms_per_student=payload.slots,
            created_by=user.id,
        )
        db.add(run)
        db.flush()
    assignments = (
        db.query(LabAssignment)
        .filter(LabAssignment.lab_run_id == run.id)
        .with_for_update()
        .all()
    )
    for row in assignments:
        if row.student_vm_id and (
            row.user_id not in students
            or row.slot_index > payload.slots
            or lab.default_pool_id != pool.id
        ):
            raise HTTPException(
                409,
                "A linked VM would be affected. Manage its assignment and verified cleanup before changing the roster, quota, or pool.",
            )
    lab.name, lab.description, lab.default_pool_id = (
        payload.name.strip(),
        payload.description,
        pool.id,
    )
    for flag in FLAGS:
        setattr(lab, flag, getattr(payload, flag))
    template = _default_template(db, lab)
    run.name, run.starts_at, run.ends_at = payload.name.strip(), starts, ends
    run.max_vms_per_student = payload.slots
    run.state = payload.state
    if run.state == "active" and not run.activated_at:
        run.activated_at = utcnow()
    run.updated_at = utcnow()
    for row in assignments:
        if row.user_id not in students or row.slot_index > payload.slots:
            row.status = "revoked"
        elif row.status != "revoked":
            row.expires_at = ends
            if not row.student_vm_id:
                row.template_id = template.id
    for student_id in sorted(students):
        enrollment = (
            db.query(Enrollment)
            .filter(
                Enrollment.class_id == classroom.id, Enrollment.user_id == student_id
            )
            .first()
        )
        if enrollment and (
            not enrollment.is_active
            or (enrollment.role or "student").lower() != "student"
        ):
            raise HTTPException(
                409,
                "A selected student has an inactive or non-student class enrollment. Review the roster first.",
            )
        if not enrollment:
            db.add(
                Enrollment(
                    class_id=classroom.id,
                    user_id=student_id,
                    role="student",
                    is_active=True,
                )
            )
            db.flush()
        for slot in range(1, payload.slots + 1):
            _create_assignment(
                db,
                run,
                lab,
                LabAssignmentCreate(
                    user_id=student_id, template_id=template.id, slot_index=slot
                ),
            )
    db.add(
        LabSetupReceipt(
            request_id=str(payload.request_id),
            organization_id=organization.id,
            actor_id=user.id,
            run_id=run.id,
            fingerprint=fingerprint,
        )
    )
    record_audit_event(
        db,
        actor_id=user.id,
        organization_id=organization.id,
        action="classroom.setup_saved",
        target_type="lab_run",
        target_id=str(run.id),
        metadata={
            "state": run.state,
            "students": len(students),
            "slots": payload.slots,
        },
    )
    db.flush()
    result = _snapshot(db, run, lab)
    db.commit()
    return result


def _save(db, payload, user, organization, run_id=None):
    try:
        return _apply(db, payload, user, organization, run_id)
    except IntegrityError as exc:
        db.rollback()
        # A simultaneous retry can race the first insertion. Re-read its receipt.
        if db.get(LabSetupReceipt, str(payload.request_id)):
            return _apply(db, payload, user, organization, run_id)
        raise HTTPException(
            409,
            "A class, pool, or account conflicts with an existing record. Reload and choose the existing resource.",
        ) from exc
    except Exception:
        db.rollback()
        raise


@router.post("/admin/lab-setups", response_model=LabSetupOut)
def create_setup(
    payload: LabSetupWrite,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(
        require_organization_role("instructor")
    ),
):
    return _save(db, payload, user, organization)


@router.put("/admin/lab-setups/{run_id}", response_model=LabSetupOut)
def edit_setup(
    run_id: int,
    payload: LabSetupWrite,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(
        require_organization_role("instructor")
    ),
):
    return _save(db, payload, user, organization, run_id)
