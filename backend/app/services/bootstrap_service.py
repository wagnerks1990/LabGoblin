from __future__ import annotations

import hmac

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import Organization, OrganizationMembership, Role, User
from app.services.audit_service import record_audit_event
from app.services.auth_service import issue_session
from app.services.security import hash_password, validate_password
from app.services.account_identity import (
    normalize_email,
    new_account_handle,
    ensure_email_available,
    flush_account,
)


def bootstrap_required(db: Session) -> bool:
    return (
        not db.query(User)
        .join(Role, Role.id == User.role_id)
        .filter(Role.name == "Admin", User.is_active.is_(True))
        .first()
    )


def create_first_admin(
    db: Session, *, token: str, username: str | None, email: str, password: str
) -> tuple[User, str]:
    configured = settings.bootstrap_admin_token or ""
    if not configured or not hmac.compare_digest(token, configured):
        raise HTTPException(status_code=403, detail="Invalid bootstrap token")

    admin_role = db.query(Role).filter(Role.name == "Admin").with_for_update().first()
    if not admin_role:
        raise HTTPException(
            status_code=503,
            detail="Required roles are not initialized; run database migrations",
        )
    if not bootstrap_required(db):
        raise HTTPException(
            status_code=409, detail="Administrator enrollment is already complete"
        )
    username = (username or "").strip() or new_account_handle()
    email = normalize_email(email)
    ensure_email_available(db, email)
    if (
        db.query(User)
        .filter((User.username == username) | (User.email == email))
        .first()
    ):
        raise HTTPException(status_code=409, detail="Username or email already exists")
    validate_password(password)

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        role_id=admin_role.id,
        role="Admin",
        is_active=True,
        force_password_change=False,
    )
    db.add(user)
    flush_account(db)
    organization = db.query(Organization).filter(Organization.slug == "default").first()
    if not organization:
        organization = Organization(
            name="Default Organization", slug="default", enabled=True
        )
        db.add(organization)
        db.flush()
    db.add(
        OrganizationMembership(
            organization_id=organization.id,
            user_id=user.id,
            role="owner",
            is_active=True,
        )
    )
    access_token = issue_session(db, user)
    record_audit_event(
        db,
        actor_id=user.id,
        organization_id=organization.id,
        action="identity.first_admin_enrolled",
        target_type="user",
        target_id=str(user.id),
    )
    db.commit()
    db.refresh(user)
    return user, access_token
