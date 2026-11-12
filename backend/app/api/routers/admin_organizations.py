import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.session import get_db
from app.models.models import AuditLog, Organization, OrganizationMembership, User
from app.services.organization_access import normalize_organization_role


router = APIRouter()
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _organization_out(db: Session, organization: Organization) -> dict:
    return {
        "id": organization.id,
        "name": organization.name,
        "slug": organization.slug,
        "enabled": organization.enabled,
        "member_count": db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization.id,
            OrganizationMembership.is_active.is_(True),
        )
        .count(),
    }


def _organization_or_404(
    db: Session, organization_id: int, *, lock: bool = False
) -> Organization:
    query = db.query(Organization).filter(Organization.id == organization_id)
    organization = query.with_for_update().first() if lock else query.first()
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization


def _validate_slug(value: str | None) -> str:
    slug = (value or "").strip().lower()
    if not _SLUG_RE.fullmatch(slug):
        raise HTTPException(
            status_code=422,
            detail="slug must contain lowercase letters, numbers, and single hyphens",
        )
    return slug


def _audit(
    db: Session,
    actor_id: int,
    action: str,
    target_id: str,
    organization_id: int | None = None,
) -> None:
    db.add(
        AuditLog(
            organization_id=organization_id,
            actor_id=actor_id,
            action=action,
            target_type="organization",
            target_id=target_id,
        )
    )


def _ensure_another_active_owner(
    db: Session, organization_id: int, excluded_user_id: int
) -> None:
    remaining = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id != excluded_user_id,
            OrganizationMembership.role == "owner",
            OrganizationMembership.is_active.is_(True),
        )
        .count()
    )
    if remaining == 0:
        raise HTTPException(
            status_code=409,
            detail="An organization must retain at least one active owner",
        )


@router.get("/admin/organizations")
def list_organizations(
    _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    rows = db.query(Organization).order_by(Organization.name.asc()).all()
    return [_organization_out(db, row) for row in rows]


@router.post("/admin/organizations", status_code=201)
def create_organization(
    payload: dict, _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    name = (payload.get("name") or "").strip()
    slug = _validate_slug(payload.get("slug"))
    if not name:
        raise HTTPException(status_code=422, detail="name is required")
    if db.query(Organization).filter(Organization.slug == slug).first():
        raise HTTPException(status_code=409, detail="Organization slug already exists")
    organization = Organization(
        name=name, slug=slug, enabled=payload.get("enabled", True)
    )
    db.add(organization)
    db.flush()
    db.add(
        OrganizationMembership(
            organization_id=organization.id,
            user_id=_user.id,
            role="owner",
            is_active=True,
        )
    )
    _audit(db, _user.id, "organization.created", str(organization.id), organization.id)
    db.commit()
    db.refresh(organization)
    return _organization_out(db, organization)


@router.patch("/admin/organizations/{organization_id}")
def update_organization(
    organization_id: int,
    payload: dict,
    _user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    organization = _organization_or_404(db, organization_id)
    if "name" in payload:
        name = (payload.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=422, detail="name cannot be empty")
        organization.name = name
    if "slug" in payload:
        slug = _validate_slug(payload.get("slug"))
        conflict = (
            db.query(Organization)
            .filter(Organization.slug == slug, Organization.id != organization_id)
            .first()
        )
        if conflict:
            raise HTTPException(
                status_code=409, detail="Organization slug already exists"
            )
        organization.slug = slug
    if "enabled" in payload:
        organization.enabled = bool(payload["enabled"])
    _audit(db, _user.id, "organization.updated", str(organization.id), organization.id)
    db.commit()
    db.refresh(organization)
    return _organization_out(db, organization)


@router.get("/admin/organizations/{organization_id}/members")
def list_members(
    organization_id: int,
    _user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    _organization_or_404(db, organization_id)
    rows = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization_id,
        )
        .order_by(OrganizationMembership.id.asc())
        .all()
    )
    users = (
        {
            u.id: u
            for u in db.query(User).filter(User.id.in_([r.user_id for r in rows])).all()
        }
        if rows
        else {}
    )
    return [
        {
            "id": row.id,
            "user_id": row.user_id,
            "username": users[row.user_id].username if row.user_id in users else None,
            "email": users[row.user_id].email if row.user_id in users else None,
            "role": row.role,
            "is_active": row.is_active,
        }
        for row in rows
    ]


@router.put("/admin/organizations/{organization_id}/members/{user_id}")
def put_member(
    organization_id: int,
    user_id: int,
    payload: dict,
    _user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    _organization_or_404(db, organization_id, lock=True)
    if not db.query(User).filter(User.id == user_id).first():
        raise HTTPException(status_code=404, detail="User not found")
    role = normalize_organization_role(payload.get("role"))
    if role is None:
        raise HTTPException(
            status_code=422, detail="role must be student, instructor, admin, or owner"
        )
    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
        )
        .first()
    )
    if membership is None:
        membership = OrganizationMembership(
            organization_id=organization_id, user_id=user_id, role=role
        )
        db.add(membership)
    else:
        will_be_active = bool(payload.get("is_active", True))
        if membership.role == "owner" and (role != "owner" or not will_be_active):
            _ensure_another_active_owner(db, organization_id, user_id)
        membership.role = role
        membership.is_active = will_be_active
    db.flush()
    _audit(
        db,
        _user.id,
        "organization.membership.upserted",
        f"{organization_id}:{user_id}",
        organization_id,
    )
    db.commit()
    db.refresh(membership)
    return {
        "id": membership.id,
        "organization_id": organization_id,
        "user_id": user_id,
        "role": membership.role,
        "is_active": membership.is_active,
    }


@router.delete("/admin/organizations/{organization_id}/members/{user_id}")
def deactivate_member(
    organization_id: int,
    user_id: int,
    _user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    _organization_or_404(db, organization_id, lock=True)
    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
        )
        .first()
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Organization membership not found")
    if membership.role == "owner" and membership.is_active:
        _ensure_another_active_owner(db, organization_id, user_id)
    membership.is_active = False
    _audit(
        db,
        _user.id,
        "organization.membership.deactivated",
        f"{organization_id}:{user_id}",
        organization_id,
    )
    db.commit()
    return {"ok": True, "deactivated": True}
