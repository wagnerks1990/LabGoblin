from fastapi import APIRouter, Depends, HTTPException
import json
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.schemas.vm import (
    TemplateResponse,
    TemplateCreateRequest,
    TemplateUpdateRequest,
)
from app.services import template_service
from app.models.models import VMTemplate, TemplateGuestCredential, AuditLog
from app.schemas.template_credentials import (
    TemplateCredentialWrite,
    TemplateCredentialPolicy,
    TemplateCredentialStatus,
)
from app.services.secret_crypto import encrypt_secret
from app.db.tx import safe_commit
from app.services.organization_access import (
    OrganizationContext,
    get_current_organization,
    require_organization_role,
)

router = APIRouter()


def _credential_template(db, id, organization):
    from app.services.organization_access import enforce_organization_role

    enforce_organization_role(organization, "admin")
    template = (
        db.query(VMTemplate)
        .filter(VMTemplate.id == id, VMTemplate.organization_id == organization.id)
        .first()
    )
    if not template:
        raise HTTPException(404, "Template not found")
    return template


def _credential_status(credential):
    return {
        "configured": credential is not None,
        "auto_connect": bool(credential and credential.auto_connect),
        "student_visible": bool(credential and credential.student_visible),
    }


def _credential_audit(db, user, organization, id, action):
    db.add(
        AuditLog(
            organization_id=organization.id,
            actor_id=user.id,
            action=action,
            target_type="vm_template",
            target_id=str(id),
            message="Template guest credential settings updated",
        )
    )
    safe_commit(db)


@router.get(
    "/admin/templates/{id}/guest-credentials", response_model=TemplateCredentialStatus
)
def guest_credential_status(
    id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(require_organization_role("admin")),
):
    _credential_template(db, id, organization)
    return _credential_status(db.get(TemplateGuestCredential, id))


@router.put(
    "/admin/templates/{id}/guest-credentials", response_model=TemplateCredentialStatus
)
def save_guest_credentials(
    id: int,
    payload: TemplateCredentialWrite,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(require_organization_role("admin")),
):
    _credential_template(db, id, organization)
    credential = db.get(TemplateGuestCredential, id)
    if credential is None:
        credential = TemplateGuestCredential(template_id=id, revision=0)
        db.add(credential)
    credential.encrypted_credentials = encrypt_secret(
        json.dumps(
            {
                "username": payload.username,
                "password": payload.password.get_secret_value(),
                "domain": payload.domain,
            }
        )
    )
    credential.auto_connect, credential.student_visible = (
        payload.auto_connect,
        payload.student_visible,
    )
    credential.revision += 1
    _credential_audit(db, user, organization, id, "template_guest_credentials_saved")
    return _credential_status(credential)


@router.patch(
    "/admin/templates/{id}/guest-credentials", response_model=TemplateCredentialStatus
)
def change_guest_credential_policy(
    id: int,
    payload: TemplateCredentialPolicy,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(require_organization_role("admin")),
):
    _credential_template(db, id, organization)
    credential = db.get(TemplateGuestCredential, id)
    if credential is None:
        raise HTTPException(409, "Save guest credentials first")
    credential.auto_connect, credential.student_visible = (
        payload.auto_connect,
        payload.student_visible,
    )
    credential.revision += 1
    _credential_audit(
        db, user, organization, id, "template_guest_credentials_policy_changed"
    )
    return _credential_status(credential)


@router.delete(
    "/admin/templates/{id}/guest-credentials", response_model=TemplateCredentialStatus
)
def remove_guest_credentials(
    id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(require_organization_role("admin")),
):
    _credential_template(db, id, organization)
    credential = db.get(TemplateGuestCredential, id)
    if credential:
        db.delete(credential)
        _credential_audit(
            db, user, organization, id, "template_guest_credentials_removed"
        )
    return _credential_status(None)


@router.get("/templates", response_model=list[TemplateResponse])
def templates(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(get_current_organization),
):
    return template_service.list_templates(db, user, organization.id, organization.role)


@router.get("/admin/templates", response_model=list[TemplateResponse])
def admin_templates(
    _user=Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(
        require_organization_role("instructor")
    ),
):
    return (
        db.query(VMTemplate).filter(VMTemplate.organization_id == organization.id).all()
    )


@router.post("/admin/templates", response_model=TemplateResponse)
def create_template(
    payload: TemplateCreateRequest,
    _user=Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(
        require_organization_role("instructor")
    ),
):
    return template_service.create_template(db, payload, organization.id)


@router.patch("/admin/templates/{id}", response_model=TemplateResponse)
def patch_template(
    id: int,
    payload: TemplateUpdateRequest,
    _user=Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(
        require_organization_role("instructor")
    ),
):
    return template_service.patch_template(db, id, payload, organization.id)
