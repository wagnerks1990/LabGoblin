"""Single-use emailed account codes; no passwords or tokens in URLs or audits."""

import hashlib
import secrets
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.models.models import AuthLoginAttempt, EmailActionToken, User
from app.services.audit_service import record_audit_event
from app.services.auth_service import revoke_all_sessions
from app.services.email_service import address_hash, enqueue, get_settings, now
from app.services.security import hash_password, validate_password
from app.services.account_identity import email_column


def throttle(db, identifier, *, limit):
    key = hashlib.sha256(("email-recovery:" + identifier).encode()).hexdigest()
    current = now()
    # An upsert also serializes concurrent *first* attempts, before a row exists.
    table = AuthLoginAttempt.__table__
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    expired = table.c.first_failure_at < current - timedelta(minutes=15)
    statement = insert(table).values(
        key_hash=key, failures=1, first_failure_at=current, updated_at=current
    )
    statement = statement.on_conflict_do_update(
        index_elements=[table.c.key_hash],
        set_={
            "failures": case((expired, 1), else_=table.c.failures + 1),
            "first_failure_at": case(
                (expired, current), else_=table.c.first_failure_at
            ),
            "updated_at": current,
        },
    ).returning(table.c.failures)
    return db.execute(statement).scalar_one() <= limit


def issue_code(db, user, *, purpose="recovery", actor_id=None):
    # Caller holds the user row lock. Reissuing invalidates every previous code.
    db.query(EmailActionToken).filter(
        EmailActionToken.user_id == user.id, EmailActionToken.used_at.is_(None)
    ).update({"used_at": now()}, synchronize_session=False)
    code = secrets.token_urlsafe(32)
    digest = hashlib.sha256(code.encode()).hexdigest()
    expiry = now() + (
        timedelta(hours=24) if purpose == "invitation" else timedelta(minutes=30)
    )
    db.add(
        EmailActionToken(
            token_hash=digest,
            user_id=user.id,
            email_hash=address_hash(user.email),
            token_version=user.token_version or 1,
            purpose=purpose,
            expires_at=expiry,
        )
    )
    config = get_settings(db)
    subject = (
        "Set up your LabGoblin password"
        if purpose == "invitation"
        else "Reset your LabGoblin password"
    )
    text = f"{subject}\n\nOpen {config.public_origin} and choose Use an email code under Need help signing in.\n\nYour single-use code:\n{code}\n\nExpires at {expiry.isoformat()} UTC. This message does not grant classroom or VM access. If you did not request this, ignore it. Never share this code."
    enqueue(
        db,
        recipient=user.email,
        subject=subject,
        text=text,
        kind=purpose,
        user_id=user.id,
        extra={"token_hash": digest},
    )
    record_audit_event(
        db,
        actor_id=actor_id,
        action="identity.email_code_issued",
        target_type="user",
        target_id=str(user.id),
        metadata={"purpose": purpose},
    )


def request_recovery(db, email, client_ip):
    # Equal response for absent, inactive, suppressed, disabled, and valid accounts.
    ip_allowed = throttle(db, "ip:" + (client_ip or "unknown"), limit=100)
    email_allowed = throttle(db, "address:" + address_hash(email), limit=3)
    config = get_settings(db)
    if ip_allowed and email_allowed and config.enabled:
        user = (
            db.query(User)
            .filter(
                email_column() == str(email).strip().lower(), User.is_active.is_(True)
            )
            .with_for_update()
            .first()
        )
        if user:
            issue_code(db, user)
    db.commit()


def complete_recovery(db, email, code, password, client_ip):
    if not throttle(db, "redeem:" + (client_ip or "unknown"), limit=20):
        db.commit()
        raise HTTPException(429, "Too many attempts. Try again later.")
    # Commit attempt before validating so rejected requests remain rate limited.
    db.commit()
    digest = hashlib.sha256(code.encode()).hexdigest()
    token = db.get(EmailActionToken, digest)
    user = (
        db.query(User).filter(User.id == token.user_id).with_for_update().first()
        if token
        else None
    )
    if token:
        token = (
            db.query(EmailActionToken)
            .filter(EmailActionToken.token_hash == digest)
            .populate_existing()
            .with_for_update()
            .first()
        )
    if (
        not token
        or token.used_at
        or token.expires_at <= now()
        or not user
        or not user.is_active
        or token.email_hash != address_hash(email)
        or token.email_hash != address_hash(user.email)
        or token.token_version != user.token_version
    ):
        raise HTTPException(400, "Invalid or expired email code")
    validate_password(password)
    user.password_hash = hash_password(password)
    user.force_password_change = False
    user.password_changed_at = now()
    token.used_at = now()
    revoked = revoke_all_sessions(db, user, reason="email_password_reset")
    db.query(EmailActionToken).filter(
        EmailActionToken.user_id == user.id, EmailActionToken.used_at.is_(None)
    ).update({"used_at": now()}, synchronize_session=False)
    record_audit_event(
        db,
        actor_id=user.id,
        action="identity.email_password_reset",
        target_type="user",
        target_id=str(user.id),
        metadata={"sessions_revoked": revoked},
    )
    if get_settings(db).enabled:
        enqueue(
            db,
            recipient=user.email,
            subject="Your LabGoblin password was changed",
            text="Your LabGoblin password was changed using an email code. All previous sessions were revoked. If this was not you, contact your administrator immediately.",
            kind="security",
            user_id=user.id,
        )
    db.commit()
