from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.models import EmailMessage, EmailPreference, EmailWebhookEvent, User
from app.schemas.email import (
    EmailConfiguration,
    EmailPreferences,
    EmailReply,
    InboxState,
    InvitationRequest,
    RecoveryComplete,
    RecoveryRequest,
)
from app.services.audit_service import record_audit_event
from app.services.email_identity import complete_recovery, issue_code, request_recovery
from app.services.email_service import (
    address,
    configuration_status,
    enqueue,
    get_settings,
    message_summary,
    save_configuration,
    unpack,
    verify_webhook,
)
from app.services.secret_crypto import decrypt_secret

router = APIRouter()


def no_store(response):
    response.headers["Cache-Control"] = "no-store"


@router.get("/admin/email/settings")
def email_settings(
    response: Response,
    _user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    no_store(response)
    result = configuration_status(db)
    db.commit()
    return result


@router.put("/admin/email/settings")
def update_email_settings(
    payload: EmailConfiguration,
    response: Response,
    user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    no_store(response)
    save_configuration(db, payload)
    record_audit_event(
        db,
        actor_id=user.id,
        action="email.settings_updated",
        target_type="email_settings",
        target_id="1",
    )
    db.commit()
    return configuration_status(db)


@router.post("/admin/email/test", status_code=202)
def test_email(
    response: Response,
    user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    no_store(response)
    row = enqueue(
        db,
        recipient=user.email,
        subject="LabGoblin email test",
        text="LabGoblin has connected to Resend. This is a delivery test, not a confirmation that all messages will reach an inbox.",
        kind="test",
        user_id=user.id,
    )
    record_audit_event(
        db,
        actor_id=user.id,
        action="email.test_queued",
        target_type="email_message",
        target_id=str(row.id),
    )
    db.commit()
    return {"id": row.id, "state": row.state}


@router.post("/admin/email/invitations", status_code=202)
def invite_account(
    payload: InvitationRequest,
    response: Response,
    user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    no_store(response)
    target = (
        db.query(User)
        .filter(User.id == payload.user_id, User.is_active.is_(True))
        .with_for_update()
        .first()
    )
    if not target:
        raise HTTPException(404, "Active account not found")
    issue_code(db, target, purpose="invitation", actor_id=user.id)
    db.commit()
    return {"state": "queued"}


@router.post("/admin/email/retry-webhooks", status_code=202)
def retry_webhooks(
    response: Response,
    user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    no_store(response)
    count = (
        db.query(EmailWebhookEvent)
        .filter(EmailWebhookEvent.state == "failed")
        .update(
            {"state": "queued", "attempts": 0, "lease_expires_at": None},
            synchronize_session=False,
        )
    )
    record_audit_event(
        db,
        actor_id=user.id,
        action="email.webhooks_retried",
        target_type="email_settings",
        target_id="1",
        metadata={"count": count},
    )
    db.commit()
    return {"queued": count}


@router.post("/auth/email/request", status_code=202)
def recovery_request(
    payload: RecoveryRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    no_store(response)
    try:
        request_recovery(
            db, payload.email, request.client.host if request.client else None
        )
    except IntegrityError:
        db.rollback()
    return {
        "message": "If an active account matches and email is enabled, a code will be sent. Check spam or contact your administrator."
    }


@router.post("/auth/email/complete", status_code=204)
def recovery_complete(
    payload: RecoveryComplete,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    no_store(response)
    code = payload.code.get_secret_value()
    if not 32 <= len(code) <= 128:
        raise HTTPException(400, "Invalid or expired email code")
    password = payload.new_password.get_secret_value()
    if not 12 <= len(password.encode()) <= 72:
        raise HTTPException(422, "Password must contain 12 to 72 bytes")
    complete_recovery(
        db,
        payload.email,
        code,
        password,
        request.client.host if request.client else None,
    )


@router.get("/email/preferences", response_model=EmailPreferences)
def email_preferences(
    response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    no_store(response)
    row = db.get(EmailPreference, user.id)
    return {"notifications_enabled": row.notifications_enabled if row else True}


@router.put("/email/preferences", response_model=EmailPreferences)
def set_preferences(
    payload: EmailPreferences,
    response: Response,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    no_store(response)
    row = db.get(EmailPreference, user.id)
    if not row:
        row = EmailPreference(user_id=user.id)
        db.add(row)
    row.notifications_enabled = payload.notifications_enabled
    db.commit()
    return {"notifications_enabled": row.notifications_enabled}


@router.get("/admin/email/messages")
def list_messages(
    response: Response,
    direction: str = Query("inbound", pattern="^(inbound|outbound)$"),
    before: int | None = Query(None, gt=0),
    _user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    no_store(response)
    query = db.query(EmailMessage).filter(EmailMessage.direction == direction)
    if before:
        query = query.filter(EmailMessage.id < before)
    rows = query.order_by(EmailMessage.id.desc()).limit(50).all()
    return {
        "items": [message_summary(row) for row in rows],
        "next_before": rows[-1].id if len(rows) == 50 else None,
    }


def inbound_or_404(db, message_id):
    row = (
        db.query(EmailMessage)
        .filter(EmailMessage.id == message_id, EmailMessage.direction == "inbound")
        .first()
    )
    if not row:
        raise HTTPException(404, "Support message not found")
    return row


@router.get("/admin/email/messages/{message_id}")
def read_message(
    message_id: int,
    response: Response,
    user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    no_store(response)
    row = inbound_or_404(db, message_id)
    record_audit_event(
        db,
        actor_id=user.id,
        action="email.support_read",
        target_type="email_message",
        target_id=str(row.id),
    )
    db.commit()
    payload = unpack(row.encrypted_payload)
    return {
        **message_summary(row),
        "text": payload.get("text", "Content expired"),
        "attachment_count": payload.get("attachment_count", 0),
    }


@router.patch("/admin/email/messages/{message_id}")
def archive_message(
    message_id: int,
    payload: InboxState,
    response: Response,
    user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    no_store(response)
    row = inbound_or_404(db, message_id)
    row.state = payload.state
    record_audit_event(
        db,
        actor_id=user.id,
        action="email.support_status",
        target_type="email_message",
        target_id=str(row.id),
        metadata={"state": row.state},
    )
    db.commit()
    return message_summary(row)


@router.post("/admin/email/messages/{message_id}/reply", status_code=202)
def reply_message(
    message_id: int,
    payload: EmailReply,
    response: Response,
    user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    no_store(response)
    row = inbound_or_404(db, message_id)
    content = unpack(row.encrypted_payload)
    if not content:
        raise HTTPException(409, "Message content has expired")
    if address(content["from"]) in {
        address(get_settings(db).sender),
        address(get_settings(db).support_address),
    }:
        raise HTTPException(422, "Cannot reply to the application's own addresses")
    message_id_header = content.get("message_id", "")
    if "\r" in message_id_header or "\n" in message_id_header:
        message_id_header = ""
    reply = enqueue(
        db,
        recipient=content["from"],
        subject="Re: " + content.get("subject", "Support"),
        text=payload.text,
        kind="reply",
        dedupe_key=f"reply:{row.id}:{payload.request_id}",
        extra={"in_reply_to": message_id_header},
    )
    record_audit_event(
        db,
        actor_id=user.id,
        action="email.support_reply_queued",
        target_type="email_message",
        target_id=str(reply.id),
    )
    db.commit()
    return {"id": reply.id, "state": reply.state}


@router.post("/email/resend/webhook", status_code=202)
async def resend_webhook(
    request: Request, response: Response, db: Session = Depends(get_db)
):
    no_store(response)
    config = get_settings(db)
    if not config.enabled or not config.encrypted_webhook_secret:
        raise HTTPException(503, "Email webhooks are not configured")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 262144:
            raise HTTPException(413, "Webhook payload too large")
    event_id, event_type, provider_id, event_at = verify_webhook(
        bytes(body), request.headers, decrypt_secret(config.encrypted_webhook_secret)
    )
    if not db.get(EmailWebhookEvent, event_id):
        db.add(
            EmailWebhookEvent(
                id=event_id,
                event_type=event_type,
                provider_id=provider_id,
                event_at=event_at,
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    return {"accepted": True}
