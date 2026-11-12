"""Minimal notices, with authorization checked again immediately before sending."""

from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import String, cast, literal, or_

from app.models.models import (
    DurableOperation,
    EmailMessage,
    Enrollment,
    Lab,
    LabAssignment,
    LabRun,
    OrganizationMembership,
    User,
    VMTemplate,
)
from app.services.classroom_access import assignment_effectively_open
from app.services.email_service import enqueue, now
from app.services.organization_access import require_organization_access


def assignment_open(db, user, assignment):
    if not assignment or not user or assignment.user_id != user.id:
        return False
    run = db.get(LabRun, assignment.lab_run_id)
    if (
        not run
        or run.organization_id != assignment.organization_id
        or not assignment_effectively_open(assignment, run)
    ):
        return False
    lab = db.get(Lab, run.lab_id)
    template = db.get(VMTemplate, assignment.template_id)
    member = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == assignment.organization_id,
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.is_active.is_(True),
            OrganizationMembership.role.in_(
                ["student", "instructor", "admin", "owner"]
            ),
        )
        .first()
    )
    return bool(
        member
        and lab
        and lab.organization_id == assignment.organization_id
        and template
        and template.enabled
        and template.organization_id == assignment.organization_id
        and db.query(Enrollment)
        .filter(
            Enrollment.class_id == lab.class_id,
            Enrollment.user_id == user.id,
            Enrollment.is_active.is_(True),
        )
        .first()
    )


def notification_allowed(db, user, payload):
    if "assignment_id" in payload:
        return assignment_open(
            db, user, db.get(LabAssignment, payload["assignment_id"])
        )
    operation = db.get(DurableOperation, payload.get("operation_id"))
    if (
        not operation
        or operation.requested_by != user.id
        or operation.state not in {"succeeded", "failed"}
    ):
        return False
    if operation.organization_id:
        try:
            require_organization_access(db, user, operation.organization_id)
        except HTTPException:
            return False
    return True


def queue_notices(db, config):
    if not config.notifications_enabled or not config.notifications_since:
        return
    since = max(config.notifications_since, now() - timedelta(hours=23))
    operations = (
        db.query(DurableOperation)
        .filter(
            DurableOperation.finished_at >= since,
            DurableOperation.state.in_(["succeeded", "failed"]),
            DurableOperation.requested_by.is_not(None),
            ~db.query(EmailMessage.id)
            .filter(
                EmailMessage.dedupe_key
                == literal("operation:")
                + cast(DurableOperation.id, String)
                + literal(":")
                + DurableOperation.state
            )
            .exists(),
        )
        .order_by(DurableOperation.id.desc())
        .limit(200)
        .all()
    )
    for op in operations:
        user = db.get(User, op.requested_by)
        if not user or not user.is_active:
            continue
        enqueue(
            db,
            recipient=user.email,
            subject=f"LabGoblin operation {op.state}",
            text=f"Operation #{op.id} has {op.state}. Sign in at {config.public_origin} and open Operations to review the verified result. No VM action is performed by this email.",
            kind="notification",
            user_id=user.id,
            organization_id=op.organization_id,
            dedupe_key=f"operation:{op.id}:{op.state}",
            extra={"operation_id": op.id},
        )
    assignments_query = (
        db.query(LabAssignment)
        .join(LabRun, LabRun.id == LabAssignment.lab_run_id)
        .filter(
            LabAssignment.status.in_(["assigned", "ready"]),
            LabAssignment.created_at >= config.notifications_since,
            LabRun.state.in_(["scheduled", "active"]),
            or_(LabRun.starts_at.is_(None), LabRun.starts_at <= now()),
            or_(LabRun.ends_at.is_(None), LabRun.ends_at > now()),
            or_(LabAssignment.expires_at.is_(None), LabAssignment.expires_at > now()),
        )
    )
    candidates = []
    for notice_kind in ["available", "ending"]:
        query = assignments_query.filter(
            ~db.query(EmailMessage.id)
            .filter(
                EmailMessage.dedupe_key
                == literal("assignment:")
                + cast(LabAssignment.id, String)
                + literal(":" + notice_kind)
            )
            .exists()
        )
        if notice_kind == "ending":
            query = query.filter(
                or_(
                    LabRun.ends_at <= now() + timedelta(hours=1),
                    LabAssignment.expires_at <= now() + timedelta(hours=1),
                )
            )
        candidates.extend(
            (a, notice_kind) for a in query.order_by(LabAssignment.id).limit(250).all()
        )
    for assignment, kind in candidates:
        user = db.get(User, assignment.user_id)
        if not user or not user.is_active or not assignment_open(db, user, assignment):
            continue
        run = db.get(LabRun, assignment.lab_run_id)
        expiries = [value for value in [assignment.expires_at, run.ends_at] if value]
        ending = min(expiries) if expiries else None
        enqueue(
            db,
            recipient=user.email,
            subject="Your LabGoblin lab "
            + ("ends soon" if kind == "ending" else "is available"),
            text=f"Sign in at {config.public_origin} to review your lab assignment and its access window. "
            + (
                f"The window ends at {ending.isoformat()} UTC."
                if kind == "ending"
                else "Access remains subject to your enrollment and lab schedule."
            ),
            kind="notification",
            user_id=user.id,
            organization_id=assignment.organization_id,
            dedupe_key=f"assignment:{assignment.id}:{kind}",
            extra={"assignment_id": assignment.id},
        )
    db.commit()
