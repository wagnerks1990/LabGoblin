from datetime import datetime, timedelta, timezone
import hashlib

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.core.config import settings
from app.models.models import AuthLoginAttempt, AuthSession, User
from app.services.audit_service import record_audit_event
from app.services.account_identity import email_column
from app.services.security import (
    create_access_token,
    hash_password,
    new_token_id,
    validate_password,
    verify_password,
)

DUMMY_PASSWORD_HASH = "$2b$12$4YhPUD3t8f70JY7V2zNnD.8bhgXqqPp6j8cgqWOmXDVvw8O3krzxS"
LoginKey = str | tuple[str, int]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _attempt_key(username: LoginKey, client_ip: str | None) -> str:
    peer = (client_ip or "unknown").strip()
    raw = (
        f"labgoblin-account|{peer}|{username[1]}"
        if isinstance(username, tuple)
        else f"{peer}|{username.strip().lower()}"
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def _rate_limit_row(
    db: Session, username: LoginKey, client_ip: str | None
) -> AuthLoginAttempt | None:
    return (
        db.query(AuthLoginAttempt)
        .filter(AuthLoginAttempt.key_hash == _attempt_key(username, client_ip))
        .with_for_update()
        .first()
    )


def _check_login_allowed(
    db: Session, username: LoginKey, client_ip: str | None
) -> None:
    row = _rate_limit_row(db, username, client_ip)
    now = _utcnow()
    if row and row.blocked_until and row.blocked_until > now:
        retry_after = max(1, int((row.blocked_until - now).total_seconds()))
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )


def _record_login_failure(
    db: Session, username: LoginKey, client_ip: str | None
) -> None:
    now = _utcnow()
    row = _rate_limit_row(db, username, client_ip)
    window = timedelta(seconds=settings.login_failure_window_seconds)
    if not row:
        row = AuthLoginAttempt(
            key_hash=_attempt_key(username, client_ip), failures=0, first_failure_at=now
        )
        db.add(row)
    elif now - row.first_failure_at > window:
        row.failures = 0
        row.first_failure_at = now
        row.blocked_until = None
    row.failures += 1
    row.updated_at = now
    if row.failures >= settings.login_max_failures:
        row.blocked_until = now + timedelta(seconds=settings.login_lockout_seconds)


def _clear_login_failures(
    db: Session, username: LoginKey, client_ip: str | None
) -> None:
    row = _rate_limit_row(db, username, client_ip)
    if row:
        db.delete(row)


def issue_session(
    db: Session,
    user: User,
    *,
    client_ip: str | None = None,
    user_agent: str | None = None,
) -> str:
    now = _utcnow()
    token_id = new_token_id()
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    db.add(
        AuthSession(
            user_id=user.id,
            token_id=token_id,
            client_ip=(client_ip or "")[:64] or None,
            user_agent=(user_agent or "")[:255] or None,
            expires_at=expires_at,
        )
    )
    return create_access_token(
        user.username, token_id=token_id, token_version=user.token_version or 1
    )


def login_user(
    db: Session,
    username: str,
    password: str,
    *,
    client_ip: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
) -> str:
    identifier = username.strip()
    # Email-shaped identifiers never fall back to another account's handle.
    candidates = (
        db.query(User).filter(email_column() == identifier.lower()).limit(2).all()
        if "@" in identifier
        else db.query(User).filter(User.username == identifier).limit(2).all()
    )
    user = candidates[0] if len(candidates) == 1 else None
    login_key = ("account", user.id) if user else identifier.lower()
    _check_login_allowed(db, login_key, client_ip)
    if user:
        # Honor unexpired lockouts written by older username-keyed releases.
        for alias in {user.username, user.email}:
            _check_login_allowed(db, alias, client_ip)
    credentials_valid = verify_password(
        password, user.password_hash if user else DUMMY_PASSWORD_HASH
    )
    if not user or not credentials_valid:
        _record_login_failure(db, login_key, client_ip)
        record_audit_event(
            db,
            actor_id=user.id if user else None,
            action="identity.login",
            target_type="user",
            target_id=str(user.id) if user else "unknown",
            outcome="failure",
            message="Invalid credentials",
            request_id=request_id,
            source_ip=client_ip,
            metadata={
                "identifier_hash": hashlib.sha256(
                    identifier.lower().encode()
                ).hexdigest()
            },
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not getattr(user, "is_active", True):
        record_audit_event(
            db,
            actor_id=user.id,
            action="identity.login",
            target_type="user",
            target_id=str(user.id),
            outcome="denied",
            message="Account disabled",
            request_id=request_id,
            source_ip=client_ip,
        )
        db.commit()
        raise HTTPException(status_code=403, detail="User account is disabled")
    _clear_login_failures(db, login_key, client_ip)
    for alias in {user.username, user.email}:
        _clear_login_failures(db, alias, client_ip)
    user.last_login_at = _utcnow()
    token = issue_session(db, user, client_ip=client_ip, user_agent=user_agent)
    record_audit_event(
        db,
        actor_id=user.id,
        action="identity.login",
        target_type="auth_session",
        target_id="new",
        request_id=request_id,
        source_ip=client_ip,
    )
    db.commit()
    return token


def revoke_session(db: Session, session: AuthSession, *, reason: str) -> None:
    if not session.revoked_at:
        session.revoked_at = _utcnow()
        session.revoke_reason = reason


def revoke_all_sessions(db: Session, user: User, *, reason: str) -> int:
    now = _utcnow()
    rows = (
        db.query(AuthSession)
        .filter(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .all()
    )
    for row in rows:
        row.revoked_at = now
        row.revoke_reason = reason
    user.token_version = (user.token_version or 1) + 1
    return len(rows)


def change_password(
    db: Session, user: User, current_password: str, new_password: str
) -> str:
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    validate_password(new_password)
    if verify_password(new_password, user.password_hash):
        raise HTTPException(
            status_code=422,
            detail="New password must be different from the current password",
        )
    user.password_hash = hash_password(new_password)
    user.password_changed_at = _utcnow()
    user.force_password_change = False
    revoke_all_sessions(db, user, reason="password_changed")
    token = issue_session(db, user)
    record_audit_event(
        db,
        actor_id=user.id,
        action="identity.password_changed",
        target_type="user",
        target_id=str(user.id),
    )
    from app.services.email_service import security_notice

    security_notice(db, user)
    db.commit()
    return token
