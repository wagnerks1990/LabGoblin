import base64
import hashlib
import hmac
import json
import time
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.session import Base, get_db
from app.main import app
from app.models.models import (
    AuthSession,
    EmailActionToken,
    EmailMessage,
    EmailPreference,
    EmailSettings,
    EmailSuppression,
    EmailWebhookEvent,
    Role,
    User,
)
from app.services import email_service as mail
from app.services.email_identity import issue_code
from app.services.security import hash_password


@pytest.fixture
def context(monkeypatch):
    monkeypatch.setattr(
        settings, "config_encryption_key", "unit-test-encryption-key-for-email"
    )
    monkeypatch.setattr(settings, "worker_scheduler_enabled", False)
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, autoflush=False)()
    role = Role(name="Admin")
    db.add(role)
    db.flush()
    user = User(
        username="mail-admin",
        email="admin@example.com",
        password_hash=hash_password("OriginalPass1!"),
        role_id=role.id,
        role="Admin",
        is_active=True,
    )
    db.add(user)
    db.flush()
    config = EmailSettings(
        id=1,
        enabled=True,
        receiving_enabled=True,
        notifications_enabled=True,
        notifications_since=mail.now(),
        public_origin="https://lab.example.com",
        sender="notifications@lab.example.com",
        support_address="support@lab.example.com",
        encrypted_api_key=mail.encrypt_secret("re_unit_test"),
        encrypted_webhook_secret=mail.encrypt_secret(
            "whsec_" + base64.b64encode(b"test-signing-key-for-email-32bytes").decode()
        ),
    )
    db.add(config)
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(
        app, headers={"Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"}
    )
    try:
        yield db, user, config, client
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def login(client):
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "mail-admin", "password": "OriginalPass1!"},
        ).status_code
        == 204
    )


def code_from(db):
    payload = mail.unpack(
        db.query(EmailMessage)
        .filter(EmailMessage.kind.in_(["recovery", "invitation"]))
        .order_by(EmailMessage.id.desc())
        .first()
        .encrypted_payload
    )
    return payload["text"].split("single-use code:\n")[1].split("\n")[0]


def signed(
    config, *, event_type="email.received", email_id=None, event_id=None, timestamp=None
):
    body = json.dumps(
        {
            "type": event_type,
            "created_at": mail.now().isoformat() + "Z",
            "data": {"email_id": email_id or str(uuid4())},
        }
    ).encode()
    stamp = str(timestamp if timestamp is not None else int(time.time()))
    event_id = event_id or "msg_" + uuid4().hex
    key = base64.b64decode(
        mail.decrypt_secret(config.encrypted_webhook_secret).removeprefix("whsec_")
    )
    signature = base64.b64encode(
        hmac.new(
            key, event_id.encode() + b"." + stamp.encode() + b"." + body, hashlib.sha256
        ).digest()
    ).decode()
    return body, {
        "svix-id": event_id,
        "svix-timestamp": stamp,
        "svix-signature": "v1," + signature,
        "Content-Type": "application/json",
    }


def test_recovery_is_generic_throttled_encrypted_and_no_store(context):
    db, user, config, client = context
    known = client.post("/api/auth/email/request", json={"email": user.email})
    unknown = client.post(
        "/api/auth/email/request", json={"email": "absent@example.com"}
    )
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert known.headers["cache-control"] == "no-store"
    code = code_from(db)
    assert code not in known.text
    assert code not in db.query(EmailMessage).one().encrypted_payload
    assert (
        db.query(EmailActionToken).one().token_hash
        == hashlib.sha256(code.encode()).hexdigest()
    )
    for _ in range(5):
        assert (
            client.post(
                "/api/auth/email/request", json={"email": user.email}
            ).status_code
            == 202
        )
    assert db.query(EmailMessage).count() == 3
    config.enabled = False
    db.commit()
    assert (
        client.post("/api/auth/email/request", json={"email": user.email}).json()
        == known.json()
    )
    assert db.query(EmailMessage).count() == 3


def test_recovery_consumes_code_once_and_revokes_all_sessions(context):
    db, user, config, client = context
    login(client)
    assert (
        client.post("/api/auth/email/request", json={"email": user.email}).status_code
        == 202
    )
    code = code_from(db)
    request = {"email": user.email, "code": code, "new_password": "ChangedPassword7!"}
    assert client.post("/api/auth/email/complete", json=request).status_code == 204
    assert user.token_version == 2
    assert db.query(AuthSession).filter(AuthSession.revoked_at.is_(None)).count() == 0
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/email/complete", json=request).status_code == 400
    client.cookies.clear()
    assert (
        client.post(
            "/api/auth/login",
            json={"username": user.username, "password": "ChangedPassword7!"},
        ).status_code
        == 204
    )


@pytest.mark.parametrize(
    "change", ["email", "version", "inactive", "expiry", "reissued"]
)
def test_changed_identity_and_stale_codes_are_denied(context, change):
    db, user, config, client = context
    client.post("/api/auth/email/request", json={"email": user.email})
    code = code_from(db)
    if change == "email":
        user.email = "changed@example.com"
    if change == "version":
        user.token_version += 1
    if change == "inactive":
        user.is_active = False
    if change == "expiry":
        db.query(EmailActionToken).one().expires_at = mail.now() - timedelta(seconds=1)
    if change == "reissued":
        issue_code(db, user)
    db.commit()
    result = client.post(
        "/api/auth/email/complete",
        json={
            "email": "admin@example.com",
            "code": code,
            "new_password": "ChangedPassword7!",
        },
    )
    assert result.status_code == 400
    assert code not in result.text


@pytest.mark.parametrize("role_name", ["Student", "Teacher", "Unrecognized"])
def test_admin_settings_and_support_are_denied_to_non_admins(context, role_name):
    db, user, config, client = context
    assert client.get("/api/admin/email/settings").status_code == 401
    login(client)
    role = Role(name=role_name)
    db.add(role)
    db.flush()
    user.role_id = role.id
    user.role = role_name
    db.commit()
    for path in [
        "/api/admin/email/settings",
        "/api/admin/email/messages",
        "/api/admin/email/messages/1",
    ]:
        assert client.get(path).status_code == 403
    assert client.post("/api/admin/email/test").status_code == 403
    assert (
        client.post(
            "/api/admin/email/invitations", json={"user_id": user.id}
        ).status_code
        == 403
    )


def test_credentials_never_returned_and_invalid_origin_does_not_reflect_key(context):
    db, user, config, client = context
    login(client)
    result = client.get("/api/admin/email/settings")
    assert result.json()["api_key_configured"] is True
    assert "re_unit_test" not in result.text and "encrypted_" not in result.text
    payload = {
        "enabled": True,
        "receiving_enabled": True,
        "public_origin": "https://lab.example.com/path",
        "sender": config.sender,
        "support_address": config.support_address,
        "api_key": "re_private_key",
    }
    invalid = client.put("/api/admin/email/settings", json=payload)
    assert invalid.status_code == 422 and "re_private_key" not in invalid.text
    invalid_password = client.post(
        "/api/auth/email/complete",
        json={"email": user.email, "code": "x" * 40, "new_password": "tiny-secret"},
    )
    assert (
        invalid_password.status_code == 422
        and "tiny-secret" not in invalid_password.text
    )


def test_verified_webhooks_are_deduplicated_and_forged_payloads_rejected(context):
    db, user, config, client = context
    body, headers = signed(config)
    for _ in range(2):
        assert (
            client.post(
                "/api/email/resend/webhook", content=body, headers=headers
            ).status_code
            == 202
        )
    assert db.query(EmailWebhookEvent).count() == 1
    assert (
        client.post(
            "/api/email/resend/webhook", content=body + b" ", headers=headers
        ).status_code
        == 400
    )
    assert client.post("/api/email/resend/webhook", content=body).status_code == 400
    for age in [-301, 301]:
        stale, h = signed(config, timestamp=int(time.time()) + age)
        assert (
            client.post(
                "/api/email/resend/webhook", content=stale, headers=h
            ).status_code
            == 400
        )
    assert (
        client.post("/api/email/resend/webhook", content=b"x" * 262145).status_code
        == 413
    )


def test_queue_retries_with_same_idempotency_and_never_claims_delivery(
    context, monkeypatch
):
    db, user, config, client = context
    row = mail.enqueue(
        db,
        recipient=user.email,
        subject="Test",
        text="Test",
        kind="test",
        user_id=user.id,
    )
    db.commit()
    keys = []

    def send(*args, **kwargs):
        keys.append(kwargs["idempotency_key"])
        if len(keys) == 1:
            raise mail.ProviderError(429)
        return {"id": str(uuid4())}

    monkeypatch.setattr(mail, "provider_request", send)
    mail.process_queue(db)
    assert row.state == "queued" and row.error and row.attempts == 1
    row.run_after = mail.now() - timedelta(seconds=1)
    db.commit()
    mail.process_queue(db)
    assert row.state == "accepted" and row.attempts == 2
    assert keys[0] == keys[1]


def test_late_delivery_cannot_override_complaint_and_future_sends_are_suppressed(
    context,
):
    db, user, config, client = context
    row = mail.enqueue(
        db,
        recipient=user.email,
        subject="Test",
        text="Test",
        kind="test",
        user_id=user.id,
    )
    row.provider_id = str(uuid4())
    row.state = "accepted"
    db.commit()
    for index, kind in enumerate(["email.complained", "email.delivered"]):
        event = EmailWebhookEvent(
            id=str(uuid4()),
            event_type=kind,
            provider_id=row.provider_id,
            event_at=mail.now() + timedelta(seconds=index),
        )
        db.add(event)
        mail.process_event(db, event, config)
        db.commit()
    assert row.state == "complained"
    assert db.get(EmailSuppression, mail.address_hash(user.email))
    next_row = mail.enqueue(
        db,
        recipient=user.email,
        subject="Test",
        text="Test",
        kind="test",
        user_id=user.id,
    )
    db.commit()
    mail.dispatch(db, next_row, config)
    assert next_row.state == "suppressed"


def test_inbound_only_accepts_support_address_and_renders_plain_text(
    context, monkeypatch
):
    db, user, config, client = context
    data = {
        "from": "Sender <sender@example.com>",
        "to": [config.support_address],
        "subject": "<img src=x onerror=alert(1)>",
        "html": "<p>Hello</p><script>evil()</script>",
        "attachments": [{"filename": "unsafe.exe"}],
    }
    monkeypatch.setattr(mail, "provider_request", lambda *args, **kwargs: data)
    event = EmailWebhookEvent(
        id="valid-support",
        event_type="email.received",
        provider_id=str(uuid4()),
        event_at=mail.now(),
    )
    db.add(event)
    mail.process_event(db, event, config)
    db.commit()
    row = db.query(EmailMessage).one()
    assert "<script>" not in mail.unpack(row.encrypted_payload)["text"]
    assert "evil()" not in mail.unpack(row.encrypted_payload)["text"]
    login(client)
    result = client.get(f"/api/admin/email/messages/{row.id}")
    assert result.status_code == 200 and result.headers["cache-control"] == "no-store"
    assert (
        result.json()["attachment_count"] == 1
        and result.json()["text"].strip() == "Hello"
    )
    data["to"] = ["unrelated@example.com"]
    other = EmailWebhookEvent(
        id="other-address",
        event_type="email.received",
        provider_id=str(uuid4()),
        event_at=mail.now(),
    )
    db.add(other)
    mail.process_event(db, other, config)
    db.commit()
    assert other.state == "ignored" and db.query(EmailMessage).count() == 1


def test_recovery_code_scrubbed_after_acceptance_and_never_listed(context, monkeypatch):
    db, user, config, client = context
    issue_code(db, user)
    db.commit()
    code = code_from(db)
    login(client)
    assert code not in client.get("/api/admin/email/messages?direction=outbound").text
    monkeypatch.setattr(
        mail, "provider_request", lambda *args, **kwargs: {"id": str(uuid4())}
    )
    mail.process_queue(db)
    assert code not in str(
        mail.unpack(
            db.query(EmailMessage)
            .filter(EmailMessage.kind == "recovery")
            .one()
            .encrypted_payload
        )
    )


def test_notifications_preferences_and_revoked_recipient_cancel_queued_mail(context):
    db, user, config, client = context
    login(client)
    result = client.put("/api/email/preferences", json={"notifications_enabled": False})
    assert (
        result.status_code == 200
        and not db.get(EmailPreference, user.id).notifications_enabled
    )
    row = mail.enqueue(
        db,
        recipient=user.email,
        subject="Notice",
        text="Notice",
        kind="notification",
        user_id=user.id,
    )
    db.commit()
    mail.dispatch(db, row, config)
    assert row.state == "cancelled"
    row = mail.enqueue(
        db,
        recipient=user.email,
        subject="Notice",
        text="Notice",
        kind="test",
        user_id=user.id,
    )
    user.email = "new@example.com"
    db.commit()
    mail.dispatch(db, row, config)
    assert row.state == "cancelled"


def test_reply_is_queued_once_and_cannot_read_outbound_bodies(context):
    db, user, config, client = context
    row = EmailMessage(
        direction="inbound",
        kind="support",
        state="received",
        dedupe_key="support-test",
        encrypted_payload=mail.pack(
            {
                "from": "sender@example.com",
                "to": [config.support_address],
                "text": "Help",
                "subject": "Help",
            }
        ),
    )
    db.add(row)
    db.commit()
    login(client)
    payload = {"text": "Here is help", "request_id": str(uuid4())}
    first = client.post(f"/api/admin/email/messages/{row.id}/reply", json=payload)
    again = client.post(f"/api/admin/email/messages/{row.id}/reply", json=payload)
    assert (
        first.status_code == again.status_code == 202
        and first.json()["id"] == again.json()["id"]
    )
    assert db.query(EmailMessage).filter(EmailMessage.kind == "reply").count() == 1
    assert (
        client.get(f"/api/admin/email/messages/{first.json()['id']}").status_code == 404
    )


def test_invitation_creates_account_without_emailing_password_or_granting_membership(
    context,
):
    db, user, config, client = context
    login(client)
    role = Role(name="Student")
    db.add(role)
    db.commit()
    result = client.post(
        "/api/admin/users",
        json={
            "username": "invited",
            "email": "invited@example.com",
            "role_id": role.id,
            "send_invitation": True,
        },
    )
    assert result.status_code == 200
    assert "password" not in result.json()
    token = db.query(EmailActionToken).one()
    assert token.purpose == "invitation" and token.expires_at > mail.now() + timedelta(
        hours=23
    )
    payload = mail.unpack(
        db.query(EmailMessage)
        .filter(EmailMessage.kind == "invitation")
        .one()
        .encrypted_payload
    )
    assert "password_hash" not in str(payload)


def test_expired_lease_retries_same_message_and_retention_runs_while_disabled(
    context, monkeypatch
):
    db, user, config, client = context
    row = mail.enqueue(
        db,
        recipient=user.email,
        subject="Lease",
        text="Private contents",
        kind="test",
        user_id=user.id,
    )
    db.commit()
    assert mail.claim(db, EmailMessage).id == row.id
    assert mail.claim(db, EmailMessage) is None
    row.lease_expires_at = mail.now() - timedelta(seconds=1)
    db.commit()
    assert mail.claim(db, EmailMessage).id == row.id and row.attempts == 2
    config.enabled = False
    row.created_at = mail.now() - timedelta(days=31)
    db.commit()
    mail.process_queue(db)
    db.refresh(row)
    assert row.encrypted_payload is None


def test_outbox_catches_delivery_webhook_race_without_losing_receipt(
    context, monkeypatch
):
    db, user, config, client = context
    provider_id = str(uuid4())
    event = EmailWebhookEvent(
        id="early-delivery",
        event_type="email.delivered",
        provider_id=provider_id,
        event_at=mail.now(),
    )
    db.add(event)
    db.commit()
    mail.process_queue(db)
    assert event.state == "queued"
    row = mail.enqueue(
        db,
        recipient=user.email,
        subject="Race",
        text="Race",
        kind="test",
        user_id=user.id,
    )
    db.commit()
    monkeypatch.setattr(
        mail, "provider_request", lambda *args, **kwargs: {"id": provider_id}
    )
    event.lease_expires_at = None
    db.commit()
    mail.process_queue(db)
    assert row.state == "delivered" and event.state == "processed"


def test_notification_batch_continues_past_already_queued_rows(context):
    from app.models.models import DurableOperation
    from app.services.email_notifications import queue_notices

    db, user, config, client = context
    for i in range(205):
        db.add(
            DurableOperation(
                requested_by=user.id,
                operation_type="vm.start",
                target_type="student_vm",
                target_id=str(i),
                idempotency_key=f"notice-batch-{i}",
                state="succeeded",
                finished_at=mail.now(),
            )
        )
    db.commit()
    queue_notices(db, config)
    assert db.query(EmailMessage).count() == 200
    queue_notices(db, config)
    assert db.query(EmailMessage).count() == 205
    queue_notices(db, config)
    assert db.query(EmailMessage).count() == 205


@pytest.mark.parametrize("revoked", ["membership", "enrollment", "template", "run"])
def test_assignment_notification_rechecks_tenant_and_window(context, revoked):
    from app.models.models import (
        Class,
        DesktopPool,
        Enrollment,
        Lab,
        LabAssignment,
        LabRun,
        Organization,
        OrganizationMembership,
        VMTemplate,
    )
    from app.services.email_notifications import queue_notices

    db, user, config, client = context
    org = Organization(name="Example", slug="example", enabled=True)
    db.add(org)
    db.flush()
    group = Class(organization_id=org.id, name="Example", instructor_id=user.id)
    db.add(group)
    db.flush()
    pool = DesktopPool(
        organization_id=org.id,
        name="Example",
        pool_type="dynamic",
        default_protocol="vnc",
    )
    db.add(pool)
    db.flush()
    lab = Lab(
        organization_id=org.id,
        class_id=group.id,
        default_pool_id=pool.id,
        name="Example",
    )
    db.add(lab)
    db.flush()
    run = LabRun(
        organization_id=org.id,
        lab_id=lab.id,
        name="Example",
        state="active",
        created_by=user.id,
        ends_at=mail.now() + timedelta(minutes=30),
    )
    db.add(run)
    db.flush()
    template = VMTemplate(
        organization_id=org.id,
        name="Example",
        proxmox_node="simulator",
        source_vmid=100,
        enabled=True,
    )
    db.add(template)
    db.flush()
    assignment = LabAssignment(
        organization_id=org.id,
        lab_run_id=run.id,
        user_id=user.id,
        template_id=template.id,
        status="assigned",
        created_at=mail.now(),
    )
    db.add(assignment)
    member = OrganizationMembership(
        organization_id=org.id, user_id=user.id, role="student", is_active=True
    )
    db.add(member)
    enrollment = Enrollment(class_id=group.id, user_id=user.id, is_active=True)
    db.add(enrollment)
    db.commit()
    queue_notices(db, config)
    assert db.query(EmailMessage).count() == 2
    if revoked == "membership":
        member.is_active = False
    if revoked == "enrollment":
        enrollment.is_active = False
    if revoked == "template":
        template.enabled = False
    if revoked == "run":
        run.ends_at = mail.now() - timedelta(seconds=1)
    db.commit()
    for row in db.query(EmailMessage).all():
        mail.dispatch(db, row, config)
        assert row.state == "cancelled"
