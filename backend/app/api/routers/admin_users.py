from datetime import datetime, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.session import get_db
from app.models.models import (
    AuthSession,
    User,
    Role,
    Permission,
    VMTemplate,
    StudentVM,
    VMSession,
    AuditLog,
)
from app.services.audit_service import record_audit_event
from app.services.auth_service import revoke_all_sessions
from app.services.security import hash_password, validate_password
from app.services.organization_access import (
    OrganizationContext,
    get_current_organization,
)

router = APIRouter()


def _normalize_template_ids(values) -> list[int]:
    return list(dict.fromkeys(int(value) for value in (values or [])))


def _role_or_422(db: Session, role_id: int) -> Role:
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=422, detail="role_id not found")
    return role


def _protect_last_platform_admin(
    db: Session, user: User, *, deactivating: bool = False, new_role: Role | None = None
) -> None:
    current_role = db.query(Role).filter(Role.id == user.role_id).first()
    removes_admin = deactivating or (new_role is not None and new_role.name != "Admin")
    if (
        not user.is_active
        or getattr(current_role, "name", None) != "Admin"
        or not removes_admin
    ):
        return
    active_admins = (
        db.query(User)
        .join(Role, User.role_id == Role.id)
        .filter(User.is_active.is_(True), Role.name == "Admin")
        .count()
    )
    if active_admins <= 1:
        raise HTTPException(
            status_code=409,
            detail="Cannot remove the last active platform administrator",
        )


def _user_out(u: User, role_name: str | None = None):
    return {
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "display_name": u.display_name,
        "role_id": u.role_id,
        "role": role_name
        or getattr(getattr(u, "role_rel", None), "name", None)
        or u.role,
        "is_active": u.is_active,
        "force_password_change": u.force_password_change,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


@router.get("/admin/users")
def list_admin_users(
    q: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    _user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    query = db.query(User)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (User.username.ilike(like))
            | (User.email.ilike(like))
            | (User.display_name.ilike(like))
        )
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    rows = query.order_by(User.id.asc()).all()
    roles = {r.id: r.name for r in db.query(Role).all()}
    if role:
        rows = [u for u in rows if (roles.get(u.role_id, "")).lower() == role.lower()]
    return [_user_out(u, roles.get(u.role_id)) for u in rows]


@router.post("/admin/users")
def create_admin_user(
    payload: dict, _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    invitation = payload.get("send_invitation") is True
    if invitation:
        payload = {**payload, "password": secrets.token_urlsafe(32) + "aA1!"}
    for f in ("username", "email", "password"):
        if not payload.get(f):
            raise HTTPException(status_code=422, detail=f"{f} is required")
    role_name = payload.get("role")
    role_id = payload.get("role_id")
    if not role_id and role_name:
        rr = db.query(Role).filter(Role.name.ilike(role_name)).first()
        role_id = rr.id if rr else None
    if not role_id:
        raise HTTPException(status_code=422, detail="role_id or role is required")
    selected_role = _role_or_422(db, int(role_id))
    validate_password(payload["password"])
    if db.query(User).filter(User.username == payload["username"]).first():
        raise HTTPException(status_code=409, detail="username already exists")
    if db.query(User).filter(User.email == payload["email"]).first():
        raise HTTPException(status_code=409, detail="email already exists")
    u = User(
        username=payload["username"],
        email=payload["email"],
        password_hash=hash_password(payload["password"]),
        role_id=selected_role.id,
        role=selected_role.name,
        display_name=payload.get("display_name"),
        is_active=payload.get("is_active", True),
        force_password_change=payload.get("force_password_change", True),
    )
    db.add(u)
    db.flush()
    if invitation:
        if not u.is_active:
            raise HTTPException(
                status_code=422, detail="Invitations require an active account"
            )
        from app.services.email_identity import issue_code

        issue_code(db, u, purpose="invitation", actor_id=_user.id)
    record_audit_event(
        db,
        actor_id=_user.id,
        action="identity.user_created",
        target_type="user",
        target_id=str(u.id),
        metadata={"role": selected_role.name},
    )
    db.commit()
    db.refresh(u)
    return _user_out(u)


@router.patch("/admin/users/{id}")
def patch_admin_user(
    id: int,
    payload: dict,
    _user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    u = db.query(User).filter(User.id == id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    if u.id == _user.id and payload.get("is_active") is False:
        raise HTTPException(
            status_code=400, detail="Cannot deactivate the current user"
        )
    selected_role = None
    if "role_id" in payload:
        selected_role = _role_or_422(db, int(payload["role_id"]))
    _protect_last_platform_admin(
        db,
        u,
        deactivating=payload.get("is_active") is False,
        new_role=selected_role,
    )
    previous_username = u.username
    was_active = u.is_active
    for k in (
        "username",
        "email",
        "display_name",
        "is_active",
        "force_password_change",
    ):
        if k in payload:
            setattr(u, k, payload[k])
    if selected_role is not None:
        u.role_id = selected_role.id
        u.role = selected_role.name
    if previous_username != u.username or (was_active and not u.is_active):
        revoke_all_sessions(db, u, reason="account_updated")
    record_audit_event(
        db,
        actor_id=_user.id,
        action="identity.user_updated",
        target_type="user",
        target_id=str(u.id),
        metadata={"changed_fields": sorted(payload.keys())},
    )
    db.commit()
    db.refresh(u)
    return _user_out(u)


@router.patch("/admin/users/{id}/password")
def reset_user_password(
    id: int,
    payload: dict,
    _user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    u = db.query(User).filter(User.id == id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    if not payload.get("password"):
        raise HTTPException(status_code=422, detail="password is required")
    validate_password(payload["password"])
    u.password_hash = hash_password(payload["password"])
    u.force_password_change = payload.get("force_password_change", True)
    u.password_changed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    revoked = revoke_all_sessions(db, u, reason="admin_password_reset")
    record_audit_event(
        db,
        actor_id=_user.id,
        action="identity.password_reset",
        target_type="user",
        target_id=str(u.id),
        metadata={"sessions_revoked": revoked},
    )
    from app.services.email_service import security_notice

    security_notice(db, u)
    db.commit()
    return {"ok": True, "message": "Password updated."}


@router.patch("/admin/users/{id}/activate")
def activate_user(
    id: int,
    payload: dict,
    _user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    u = db.query(User).filter(User.id == id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    if u.id == _user.id and payload.get("is_active") is False:
        raise HTTPException(
            status_code=400, detail="Cannot deactivate the current user"
        )
    _protect_last_platform_admin(db, u, deactivating=payload.get("is_active") is False)
    u.is_active = bool(payload.get("is_active", True))
    if not u.is_active:
        revoke_all_sessions(db, u, reason="account_disabled")
    record_audit_event(
        db,
        actor_id=_user.id,
        action="identity.account_enabled"
        if u.is_active
        else "identity.account_disabled",
        target_type="user",
        target_id=str(u.id),
    )
    db.commit()
    db.refresh(u)
    return _user_out(u)


@router.patch("/admin/users/{id}/role")
def change_user_role(
    id: int,
    payload: dict,
    _user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    u = db.query(User).filter(User.id == id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    role_id = payload.get("role_id")
    if not role_id:
        raise HTTPException(status_code=422, detail="role_id is required")
    selected_role = _role_or_422(db, int(role_id))
    _protect_last_platform_admin(db, u, new_role=selected_role)
    u.role_id = selected_role.id
    u.role = selected_role.name
    record_audit_event(
        db,
        actor_id=_user.id,
        action="identity.platform_role_changed",
        target_type="user",
        target_id=str(u.id),
        metadata={"role": selected_role.name},
    )
    db.commit()
    db.refresh(u)
    return _user_out(u)


@router.delete("/admin/users/{id}")
def delete_admin_user(
    id: int,
    force: bool = False,
    _user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    if id == _user.id:
        raise HTTPException(status_code=400, detail="Cannot delete the current user")
    u = db.query(User).filter(User.id == id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    _protect_last_platform_admin(db, u, deactivating=True)
    deps = {
        "vms": db.query(StudentVM).filter(StudentVM.owner_id == id).count(),
        "sessions": db.query(VMSession).filter(VMSession.user_id == id).count(),
        "audit_logs": db.query(AuditLog).filter(AuditLog.actor_id == id).count(),
        "auth_sessions": db.query(AuthSession)
        .filter(AuthSession.user_id == id)
        .count(),
    }
    u.is_active = False
    revoke_all_sessions(db, u, reason="account_disabled")
    record_audit_event(
        db,
        actor_id=_user.id,
        action="identity.account_disabled",
        target_type="user",
        target_id=str(u.id),
        message="User deactivated; historical records retained",
    )
    db.commit()
    return {
        "ok": True,
        "deleted": False,
        "deactivated": True,
        "message": "User was deactivated and history was retained.",
        "dependencies": deps,
    }


@router.post("/admin/users/{id}/revoke-sessions")
def revoke_user_sessions(
    id: int, _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    u = db.query(User).filter(User.id == id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    revoked = revoke_all_sessions(db, u, reason="admin_revoked")
    record_audit_event(
        db,
        actor_id=_user.id,
        action="identity.sessions_revoked",
        target_type="user",
        target_id=str(u.id),
        metadata={"sessions_revoked": revoked},
    )
    db.commit()
    return {"ok": True, "sessions_revoked": revoked}


@router.get("/admin/users/{id}/permissions")
def user_permissions(
    id: int,
    _user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(get_current_organization),
):
    if not db.query(User).filter(User.id == id).first():
        raise HTTPException(status_code=404, detail="User not found")
    rows = db.query(Permission).filter(Permission.user_id == id).all()
    template_ids = [r.template_id for r in rows]
    templates = (
        db.query(VMTemplate)
        .filter(
            VMTemplate.id.in_(template_ids),
            VMTemplate.organization_id == organization.id,
        )
        .all()
        if template_ids
        else []
    )
    scoped_ids = [template.id for template in templates]
    return {
        "direct_template_ids": scoped_ids,
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "source_vmid": t.source_vmid,
                "proxmox_node": t.proxmox_node,
            }
            for t in templates
        ],
    }


@router.patch("/admin/users/{id}/permissions")
def patch_user_permissions(
    id: int,
    payload: dict,
    _user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(get_current_organization),
):
    if not db.query(User).filter(User.id == id).first():
        raise HTTPException(status_code=404, detail="User not found")
    template_ids = _normalize_template_ids(payload.get("template_ids"))
    templates = (
        db.query(VMTemplate)
        .filter(
            VMTemplate.id.in_(template_ids),
            VMTemplate.organization_id == organization.id,
        )
        .all()
        if template_ids
        else []
    )
    valid_ids = {template.id for template in templates}
    if valid_ids != set(template_ids):
        raise HTTPException(
            status_code=422,
            detail="All templates must belong to the selected organization",
        )
    scoped_template_ids = [
        row.id
        for row in db.query(VMTemplate)
        .filter(VMTemplate.organization_id == organization.id)
        .all()
    ]
    if scoped_template_ids:
        db.query(Permission).filter(
            Permission.user_id == id, Permission.template_id.in_(scoped_template_ids)
        ).delete()
    for tid in template_ids:
        db.add(Permission(user_id=id, template_id=tid))
    db.commit()
    return {"ok": True, "template_ids": template_ids}


@router.get("/admin/users/{id}/activity")
def user_activity(
    id: int,
    _user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(get_current_organization),
):
    u = db.query(User).filter(User.id == id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_id": id,
        "username": u.username,
        "vm_count": db.query(StudentVM)
        .filter(StudentVM.owner_id == id, StudentVM.organization_id == organization.id)
        .count(),
        "session_count": db.query(VMSession)
        .filter(VMSession.user_id == id, VMSession.organization_id == organization.id)
        .count(),
        "audit_log_count": db.query(AuditLog)
        .filter(AuditLog.actor_id == id, AuditLog.organization_id == organization.id)
        .count(),
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
    }
