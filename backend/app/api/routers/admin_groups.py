from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.models import (
    Group,
    GroupMembership,
    GroupTemplatePermission,
    OrganizationMembership,
    User,
    VMTemplate,
)
from app.services.organization_access import (
    OrganizationContext,
    require_organization_role,
)

router = APIRouter()


@router.get("/admin/groups")
def list_groups(
    _user=Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(require_organization_role("admin")),
):
    rows = (
        db.query(Group)
        .filter(Group.organization_id == organization.id)
        .order_by(Group.id.asc())
        .all()
    )
    out = []
    for g in rows:
        out.append(
            {
                "id": g.id,
                "name": g.name,
                "description": g.description,
                "enabled": g.enabled,
                "member_count": db.query(GroupMembership)
                .filter(GroupMembership.group_id == g.id)
                .count(),
                "template_permission_count": db.query(GroupTemplatePermission)
                .filter(GroupTemplatePermission.group_id == g.id)
                .count(),
            }
        )
    return out


@router.get("/admin/groups/{id}")
def get_group(
    id: int,
    _user=Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(require_organization_role("admin")),
):
    g = (
        db.query(Group)
        .filter(Group.id == id, Group.organization_id == organization.id)
        .first()
    )
    if not g:
        raise HTTPException(status_code=404, detail="Group not found")
    return {
        "id": g.id,
        "name": g.name,
        "description": g.description,
        "enabled": g.enabled,
    }


@router.post("/admin/groups")
def create_group(
    payload: dict,
    _user=Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(require_organization_role("admin")),
):
    if not payload.get("name"):
        raise HTTPException(status_code=422, detail="name is required")
    if (
        db.query(Group)
        .filter(Group.name == payload["name"], Group.organization_id == organization.id)
        .first()
    ):
        raise HTTPException(status_code=409, detail="Group already exists")
    g = Group(
        organization_id=organization.id,
        name=payload["name"],
        description=payload.get("description"),
        enabled=payload.get("enabled", True),
    )
    db.add(g)
    db.commit()
    db.refresh(g)
    return {
        "id": g.id,
        "name": g.name,
        "description": g.description,
        "enabled": g.enabled,
    }


@router.patch("/admin/groups/{id}")
def patch_group(
    id: int,
    payload: dict,
    _user=Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(require_organization_role("admin")),
):
    g = (
        db.query(Group)
        .filter(Group.id == id, Group.organization_id == organization.id)
        .first()
    )
    if not g:
        raise HTTPException(status_code=404, detail="Group not found")
    for k in ("name", "description", "enabled"):
        if k in payload:
            setattr(g, k, payload[k])
    db.commit()
    db.refresh(g)
    return {
        "id": g.id,
        "name": g.name,
        "description": g.description,
        "enabled": g.enabled,
    }


@router.delete("/admin/groups/{id}")
def delete_group(
    id: int,
    _user=Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(require_organization_role("admin")),
):
    g = (
        db.query(Group)
        .filter(Group.id == id, Group.organization_id == organization.id)
        .first()
    )
    if not g:
        raise HTTPException(status_code=404, detail="Group not found")
    db.query(GroupMembership).filter(GroupMembership.group_id == id).delete()
    db.query(GroupTemplatePermission).filter(
        GroupTemplatePermission.group_id == id
    ).delete()
    db.delete(g)
    db.commit()
    return {"ok": True, "deleted": True}


@router.get("/admin/groups/{id}/members")
def list_group_members(
    id: int,
    _user=Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(require_organization_role("admin")),
):
    if (
        not db.query(Group)
        .filter(Group.id == id, Group.organization_id == organization.id)
        .first()
    ):
        raise HTTPException(status_code=404, detail="Group not found")
    rows = db.query(GroupMembership).filter(GroupMembership.group_id == id).all()
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
            "user_id": r.user_id,
            "username": users.get(r.user_id).username if users.get(r.user_id) else None,
            "email": users.get(r.user_id).email if users.get(r.user_id) else None,
            "role_in_group": r.role_in_group,
        }
        for r in rows
    ]


@router.post("/admin/groups/{id}/members")
def add_group_member(
    id: int,
    payload: dict,
    _user=Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(require_organization_role("admin")),
):
    if (
        not db.query(Group)
        .filter(Group.id == id, Group.organization_id == organization.id)
        .first()
    ):
        raise HTTPException(status_code=404, detail="Group not found")
    uid = payload.get("user_id")
    if not uid or not db.query(User).filter(User.id == uid).first():
        raise HTTPException(status_code=422, detail="valid user_id is required")
    if (
        not db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization.id,
            OrganizationMembership.user_id == uid,
            OrganizationMembership.is_active.is_(True),
        )
        .first()
    ):
        raise HTTPException(
            status_code=422, detail="User must be an active member of this organization"
        )
    existing = (
        db.query(GroupMembership)
        .filter(GroupMembership.group_id == id, GroupMembership.user_id == uid)
        .first()
    )
    if not existing:
        db.add(
            GroupMembership(
                group_id=id, user_id=uid, role_in_group=payload.get("role_in_group")
            )
        )
        db.commit()
    return {"ok": True}


@router.delete("/admin/groups/{id}/members/{user_id}")
def remove_group_member(
    id: int,
    user_id: int,
    _user=Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(require_organization_role("admin")),
):
    group = (
        db.query(Group)
        .filter(Group.id == id, Group.organization_id == organization.id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    row = (
        db.query(GroupMembership)
        .filter(GroupMembership.group_id == id, GroupMembership.user_id == user_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Group membership not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.get("/admin/groups/{id}/template-permissions")
def list_group_template_permissions(
    id: int,
    _user=Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(require_organization_role("admin")),
):
    if (
        not db.query(Group)
        .filter(Group.id == id, Group.organization_id == organization.id)
        .first()
    ):
        raise HTTPException(status_code=404, detail="Group not found")
    rows = (
        db.query(GroupTemplatePermission)
        .filter(GroupTemplatePermission.group_id == id)
        .all()
    )
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
    return {
        "template_ids": template_ids,
        "templates": [
            {"id": t.id, "name": t.name, "source_vmid": t.source_vmid}
            for t in templates
        ],
    }


@router.patch("/admin/groups/{id}/template-permissions")
def patch_group_template_permissions(
    id: int,
    payload: dict,
    _user=Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(require_organization_role("admin")),
):
    if (
        not db.query(Group)
        .filter(Group.id == id, Group.organization_id == organization.id)
        .first()
    ):
        raise HTTPException(status_code=404, detail="Group not found")
    template_ids = [int(x) for x in (payload.get("template_ids") or [])]
    valid_template_ids = (
        {
            row.id
            for row in db.query(VMTemplate)
            .filter(
                VMTemplate.id.in_(template_ids),
                VMTemplate.organization_id == organization.id,
            )
            .all()
        }
        if template_ids
        else set()
    )
    if valid_template_ids != set(template_ids):
        raise HTTPException(
            status_code=422,
            detail="Every template must belong to the active organization",
        )
    db.query(GroupTemplatePermission).filter(
        GroupTemplatePermission.group_id == id
    ).delete()
    for tid in template_ids:
        db.add(GroupTemplatePermission(group_id=id, template_id=tid))
    db.commit()
    return {"ok": True, "template_ids": template_ids}
