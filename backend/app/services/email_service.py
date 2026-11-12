"""Resend transport and encrypted, durable mail. Never log provider bodies."""

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from html.parser import HTMLParser
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException
from pydantic import EmailStr, TypeAdapter
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.models import (
    EmailActionToken,
    EmailMessage,
    EmailPreference,
    EmailSettings,
    EmailSuppression,
    EmailWebhookEvent,
    User,
)
from app.services.secret_crypto import decrypt_secret, encrypt_secret


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def address(value):
    return str(TypeAdapter(EmailStr).validate_python(parseaddr(value)[1])).lower()


def address_hash(value):
    return hashlib.sha256(address(value).encode()).hexdigest()


def get_settings(db: Session):
    row = db.get(EmailSettings, 1)
    if row is None:
        row = EmailSettings(id=1)
        db.add(row)
        db.flush()
    return row


def pack(value):
    return encrypt_secret(json.dumps(value, ensure_ascii=False))


def unpack(value):
    return json.loads(decrypt_secret(value)) if value else {}


def configuration_status(db):
    row = get_settings(db)
    return {
        **{
            key: getattr(row, key)
            for key in [
                "enabled",
                "receiving_enabled",
                "notifications_enabled",
                "public_origin",
                "sender",
                "support_address",
            ]
        },
        "api_key_configured": bool(row.encrypted_api_key),
        "webhook_secret_configured": bool(row.encrypted_webhook_secret),
        "webhook_url": f"{row.public_origin}/api/email/resend/webhook"
        if row.public_origin
        else None,
        "failed_webhooks": db.query(EmailWebhookEvent)
        .filter(EmailWebhookEvent.state == "failed")
        .count(),
    }


def save_configuration(db, payload):
    row = get_settings(db)
    for key in [
        "enabled",
        "receiving_enabled",
        "notifications_enabled",
        "public_origin",
        "sender",
        "support_address",
    ]:
        if (
            key == "notifications_enabled"
            and payload.notifications_enabled
            and not row.notifications_enabled
        ):
            row.notifications_since = now()
        setattr(
            row,
            key,
            str(getattr(payload, key))
            if key in {"sender", "support_address"}
            else getattr(payload, key),
        )
    for key in ["api_key", "webhook_secret"]:
        value = getattr(payload, key)
        if value is not None:
            value = value.get_secret_value().strip()
            if not value or len(value) > 1024 or any(c.isspace() for c in value):
                raise HTTPException(422, "Invalid email credential format")
            if key == "api_key" and not value.startswith("re_"):
                raise HTTPException(422, "Invalid Resend API key format")
            if key == "webhook_secret":
                try:
                    decoded = base64.b64decode(
                        value.removeprefix("whsec_"), validate=True
                    )
                    if len(decoded) < 16:
                        raise ValueError()
                except ValueError:
                    raise HTTPException(422, "Invalid webhook signing secret") from None
            setattr(row, "encrypted_" + key, encrypt_secret(value))
    if row.enabled and not row.encrypted_api_key:
        raise HTTPException(422, "Configure a Resend API key before enabling email")
    if row.receiving_enabled and not row.encrypted_webhook_secret:
        raise HTTPException(
            422, "Configure the webhook signing secret before receiving email"
        )
    return row


class ProviderError(Exception):
    def __init__(self, status=503):
        self.status = status
        super().__init__(f"Email provider unavailable (HTTP {status})")


def provider_request(config, method, path, *, body=None, idempotency_key=None):
    headers = {"Authorization": "Bearer " + decrypt_secret(config.encrypted_api_key)}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    try:
        with httpx.Client(
            base_url="https://api.resend.com", timeout=15, follow_redirects=False
        ) as client:
            with client.stream(method, path, headers=headers, json=body) as response:
                if response.status_code >= 300:
                    raise ProviderError(response.status_code)
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > 2_000_000:
                        raise ProviderError(502)
                return json.loads(data)
    except (httpx.HTTPError, ValueError):
        raise ProviderError() from None


def enqueue(
    db,
    *,
    recipient,
    subject,
    text,
    kind,
    user_id=None,
    organization_id=None,
    dedupe_key=None,
    extra=None,
):
    key = dedupe_key or str(uuid4())
    existing = db.query(EmailMessage).filter(EmailMessage.dedupe_key == key).first()
    if existing:
        return existing
    config = get_settings(db)
    if not config.enabled:
        raise HTTPException(503, "Email is not enabled")
    payload = {
        "to": address(recipient),
        "subject": subject[:200],
        "text": text,
        **(extra or {}),
    }
    row = EmailMessage(
        direction="outbound",
        kind=kind,
        state="queued",
        user_id=user_id,
        organization_id=organization_id,
        dedupe_key=key,
        encrypted_payload=pack(payload),
    )
    db.add(row)
    db.flush()
    return row


def message_summary(row):
    payload = unpack(row.encrypted_payload)
    return {
        "id": row.id,
        "direction": row.direction,
        "kind": row.kind,
        "state": row.state,
        "subject": payload.get("subject", "Content expired"),
        "address": payload.get("from" if row.direction == "inbound" else "to", ""),
        "created_at": row.created_at,
        "error": row.error,
    }


def verify_webhook(body, headers, secret):
    """Svix v1: authenticate the exact raw bytes and a five-minute timestamp."""
    try:
        event_id = headers["svix-id"]
        timestamp = headers["svix-timestamp"]
        if (
            not event_id
            or len(event_id) > 255
            or abs(time.time() - int(timestamp)) > 300
        ):
            raise ValueError()
        key = base64.b64decode(secret.removeprefix("whsec_"), validate=True)
        signature = base64.b64encode(
            hmac.new(
                key,
                event_id.encode() + b"." + timestamp.encode() + b"." + body,
                hashlib.sha256,
            ).digest()
        ).decode()
        if not any(
            hmac.compare_digest(part, "v1," + signature)
            for part in headers["svix-signature"].split()
        ):
            raise ValueError()
        event = json.loads(body)
        event_type = event["type"]
        provider_id = str(UUID(event["data"]["email_id"]))
        event_at = (
            datetime.fromisoformat(event["created_at"].replace("Z", "+00:00"))
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
        )
        if not isinstance(event_type, str) or len(event_type) > 64:
            raise ValueError()
        return event_id, event_type, provider_id, event_at
    except (KeyError, ValueError, TypeError, AttributeError, UnicodeError):
        raise HTTPException(400, "Invalid email webhook") from None


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "iframe"}:
            self.hidden += 1
        if tag in {"p", "div", "br", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "iframe"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def inbound_payload(data):
    text = data.get("text")
    if not isinstance(text, str):
        parser = PlainText()
        parser.feed(str(data.get("html") or "")[:500_000])
        text = "".join(parser.parts)
    return {
        "from": address(data["from"]),
        "to": [address(v) for v in data.get("to", [])],
        "subject": str(data.get("subject") or "(No subject)")[:200],
        "text": text[:100_000],
        "attachment_count": len(data.get("attachments") or []),
        "message_id": str(data.get("message_id") or "")[:255],
    }


DELIVERY_STATES = {
    "email.sent": "accepted",
    "email.delivered": "delivered",
    "email.bounced": "bounced",
    "email.complained": "complained",
    "email.failed": "failed",
    "email.delivery_delayed": "delayed",
    "email.suppressed": "suppressed",
}


def process_event(db, event, config):
    if event.event_type == "email.received":
        if not config.receiving_enabled:
            event.state = "ignored"
            return
        existing = (
            db.query(EmailMessage)
            .filter(EmailMessage.provider_id == event.provider_id)
            .first()
        )
        if not existing:
            data = provider_request(
                config, "GET", f"/emails/receiving/{UUID(event.provider_id)}"
            )
            payload = inbound_payload(data)
            if address(config.support_address) not in payload["to"]:
                event.state = "ignored"
                return
            db.add(
                EmailMessage(
                    direction="inbound",
                    kind="support",
                    state="received",
                    dedupe_key="inbound:" + event.provider_id,
                    provider_id=event.provider_id,
                    encrypted_payload=pack(payload),
                )
            )
    elif event.event_type in DELIVERY_STATES:
        row = (
            db.query(EmailMessage)
            .filter(
                EmailMessage.provider_id == event.provider_id,
                EmailMessage.direction == "outbound",
            )
            .with_for_update()
            .first()
        )
        if not row:
            if event.created_at > now() - timedelta(hours=1):
                raise ProviderError(503)
            event.state = "ignored"
            return
        payload = unpack(row.encrypted_payload)
        if event.event_type in {
            "email.bounced",
            "email.complained",
            "email.suppressed",
        } and payload.get("to"):
            key = address_hash(payload["to"])
            if not db.get(EmailSuppression, key):
                db.add(
                    EmailSuppression(
                        address_hash=key, reason=DELIVERY_STATES[event.event_type]
                    )
                )
        if (
            row.event_at is None or event.event_at >= row.event_at
        ) and row.state not in {"bounced", "complained", "suppressed"}:
            row.state = DELIVERY_STATES[event.event_type]
            row.event_at = event.event_at
    event.state = "processed"


def recipient_allowed(db, row, payload):
    user = db.get(User, row.user_id) if row.user_id else None
    if row.user_id and (
        not user
        or not user.is_active
        or address_hash(user.email) != address_hash(payload["to"])
    ):
        return False
    token_hash = payload.get("token_hash")
    if token_hash:
        token = db.get(EmailActionToken, token_hash)
        return bool(
            token
            and not token.used_at
            and token.expires_at > now()
            and token.token_version == user.token_version
            and token.email_hash == address_hash(user.email)
        )
    if row.kind == "notification":
        preference = db.get(EmailPreference, user.id)
        if preference and not preference.notifications_enabled:
            return False
        from app.services.email_notifications import notification_allowed

        return notification_allowed(db, user, payload)
    return True


def dispatch(db, row, config):
    payload = unpack(row.encrypted_payload)
    if (
        (row.kind == "notification" and not config.notifications_enabled)
        or row.created_at < now() - timedelta(hours=23)
        or not recipient_allowed(db, row, payload)
    ):
        row.state = "cancelled"
        row.encrypted_payload = (
            None if row.kind in {"recovery", "invitation"} else row.encrypted_payload
        )
        return
    if db.get(EmailSuppression, address_hash(payload["to"])):
        row.state = "suppressed"
        return
    sender = config.support_address if row.kind == "reply" else config.sender
    body = {
        "from": f"LabGoblin <{sender}>",
        "to": [payload["to"]],
        "subject": payload["subject"],
        "text": payload["text"],
        "reply_to": config.support_address,
    }
    if payload.get("in_reply_to"):
        body["headers"] = {
            "In-Reply-To": payload["in_reply_to"],
            "References": payload["in_reply_to"],
        }
    result = provider_request(
        config,
        "POST",
        "/emails",
        body=body,
        idempotency_key=f"labgoblin-email-{row.id}",
    )
    row.provider_id = str(UUID(result["id"]))
    row.state = "accepted"
    row.error = None
    if row.kind in {"recovery", "invitation"}:
        # The provider has accepted the message; remove the recoverable code.
        row.encrypted_payload = pack(
            {"to": payload["to"], "subject": payload["subject"]}
        )


def security_notice(db, user):
    if get_settings(db).enabled:
        enqueue(
            db,
            recipient=user.email,
            subject="Your LabGoblin password was changed",
            text="Your LabGoblin password was changed. Previous sessions were revoked. If this was not you, contact your administrator immediately.",
            kind="security",
            user_id=user.id,
        )


def claim(db, model):
    current = now()
    query = db.query(model).filter(
        or_(
            model.state == "queued",
            (model.state == "sending") & (model.lease_expires_at < current),
        )
    )
    if model is EmailMessage:
        query = query.filter(
            model.direction == "outbound",
            or_(model.run_after.is_(None), model.run_after <= current),
        )
    else:
        query = query.filter(
            or_(model.lease_expires_at.is_(None), model.lease_expires_at <= current)
        )
    row = (
        query.order_by(model.created_at, model.id)
        .with_for_update(skip_locked=True)
        .first()
    )
    if row:
        row.state = "sending"
        row.attempts += 1
        row.lease_expires_at = current + timedelta(minutes=2)
        db.commit()
    return row


def process_queue(db):
    expire_content(db)
    config = get_settings(db)
    if not config.enabled or not config.encrypted_api_key:
        db.rollback()
        return {"processed": 0}
    processed = 0
    for model, action in [(EmailMessage, dispatch), (EmailWebhookEvent, process_event)]:
        for _ in range(10):
            row = claim(db, model)
            if not row:
                break
            identity = row.id
            try:
                action(db, row, config)
                row.lease_expires_at = None
                db.commit()
                processed += 1
            except (ProviderError, ValueError, KeyError) as exc:
                db.rollback()
                row = db.get(model, identity)
                row.state = "queued" if row.attempts < 5 else "failed"
                row.lease_expires_at = now() + timedelta(
                    seconds=min(600, 30 * 2**row.attempts)
                )
                if model is EmailMessage:
                    row.error = (
                        f"Provider request failed (HTTP {exc.status})."
                        if isinstance(exc, ProviderError)
                        else "Invalid provider response."
                    )
                    row.run_after = row.lease_expires_at
                db.commit()
    db.commit()
    return {"processed": processed}


def expire_content(db):
    # Retain event IDs for deduplication; remove sensitive contents after 30 days.
    db.query(EmailMessage).filter(
        EmailMessage.created_at < now() - timedelta(days=30),
        EmailMessage.encrypted_payload.is_not(None),
    ).update({"encrypted_payload": None}, synchronize_session=False)
    db.query(EmailActionToken).filter(
        EmailActionToken.expires_at < now() - timedelta(days=1)
    ).delete(synchronize_session=False)
    db.commit()
