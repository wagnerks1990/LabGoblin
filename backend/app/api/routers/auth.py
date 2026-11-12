from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.services.rbac import get_role_name
from app.db.session import get_db
from app.models.models import AuthSession
from app.schemas.auth import (
    BootstrapAdminRequest,
    LoginRequest,
    PasswordChangeRequest,
    SessionResponse,
    UserResponse,
)
from app.api.deps import get_authenticated_user, get_current_auth_session
from app.services.audit_service import record_audit_event
from app.services.auth_service import change_password, login_user, revoke_session
from app.services.bootstrap_service import bootstrap_required, create_first_admin
from app.core.config import settings

router = APIRouter()


@router.get("/bootstrap/status")
def bootstrap_status(db: Session = Depends(get_db)):
    return {
        "bootstrap_required": bootstrap_required(db),
        "token_configured": bool(settings.bootstrap_admin_token),
    }


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.auth_cookie_name,
        token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
        path="/",
    )


@router.post("/bootstrap/admin", status_code=204)
def bootstrap_admin(
    data: BootstrapAdminRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    _user, access_token = create_first_admin(
        db,
        token=data.token,
        username=data.username,
        email=data.email,
        password=data.password,
    )
    _set_session_cookie(response, access_token)
    return None


@router.post("/auth/login", status_code=204)
def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else None
    if bool(data.email) == bool(data.username):
        raise HTTPException(422, "Provide an email address or a legacy username")
    token = login_user(
        db,
        str(data.email) if data.email else data.username,
        data.password,
        client_ip=client_ip,
        user_agent=request.headers.get("user-agent"),
        request_id=getattr(request.state, "request_id", None),
    )
    _set_session_cookie(response, token)
    return None


@router.get("/auth/me", response_model=UserResponse)
def me(user=Depends(get_authenticated_user)):
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=get_role_name(user),
        role_id=getattr(user, "role_id", None),
        is_active=getattr(user, "is_active", True),
        force_password_change=getattr(user, "force_password_change", False),
    )


@router.post("/auth/change-password", status_code=204)
def update_password(
    data: PasswordChangeRequest,
    response: Response,
    user=Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    token = change_password(db, user, data.current_password, data.new_password)
    _set_session_cookie(response, token)
    return None


@router.post("/auth/logout", status_code=204)
def logout(
    response: Response,
    session: AuthSession = Depends(get_current_auth_session),
    db: Session = Depends(get_db),
):
    revoke_session(db, session, reason="logout")
    record_audit_event(
        db,
        actor_id=session.user_id,
        action="identity.logout",
        target_type="auth_session",
        target_id=str(session.id),
    )
    db.commit()
    response.delete_cookie(settings.auth_cookie_name, path="/", samesite="strict")


@router.get("/auth/sessions", response_model=list[SessionResponse])
def sessions(
    current: AuthSession = Depends(get_current_auth_session),
    user=Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(AuthSession)
        .filter(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .order_by(AuthSession.created_at.desc())
        .all()
    )
    return [
        SessionResponse(
            id=row.id,
            current=row.id == current.id,
            client_ip=row.client_ip,
            user_agent=row.user_agent,
            created_at=row.created_at.isoformat() if row.created_at else None,
            expires_at=row.expires_at.isoformat() if row.expires_at else None,
        )
        for row in rows
    ]


@router.delete("/auth/sessions/{session_id}", status_code=204)
def remove_session(
    session_id: int,
    current: AuthSession = Depends(get_current_auth_session),
    user=Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(AuthSession)
        .filter(AuthSession.id == session_id, AuthSession.user_id == user.id)
        .first()
    )
    if not row:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Session not found")
    revoke_session(db, row, reason="user_revoked")
    record_audit_event(
        db,
        actor_id=user.id,
        action="identity.session_revoked",
        target_type="auth_session",
        target_id=str(row.id),
        metadata={"current_session": row.id == current.id},
    )
    db.commit()
