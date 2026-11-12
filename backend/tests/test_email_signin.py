import pytest
from sqlalchemy.exc import IntegrityError

import test_email
from test_email import code_from
from app.core.config import settings
from app.models.models import AuditLog, AuthSession, EmailMessage, User
from app.services.security import hash_password


@pytest.fixture
def context(monkeypatch):
    yield from test_email.context.__wrapped__(monkeypatch)


@pytest.mark.parametrize(
    "identifier", ["admin@example.com", "ADMIN@EXAMPLE.COM", "  Admin@Example.com  "]
)
def test_email_signin_normalizes_case_and_whitespace_and_issues_live_session(
    context, identifier
):
    db, user, config, client = context
    response = client.post(
        "/api/auth/login", json={"email": identifier, "password": "OriginalPass1!"}
    )
    assert response.status_code == 204
    assert "httponly" in response.headers["set-cookie"].lower()
    assert client.get("/api/auth/me").json()["id"] == user.id
    assert db.query(AuthSession).filter(AuthSession.user_id == user.id).count() == 1
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_email_shaped_legacy_handle_cannot_shadow_another_email(context):
    db, user, config, client = context
    shadow = User(
        username=user.email,
        email="other@example.com",
        password_hash=hash_password("ShadowPassword9!"),
        role_id=user.role_id,
        role="Admin",
        is_active=True,
    )
    db.add(shadow)
    db.commit()
    assert (
        client.post(
            "/api/auth/login",
            json={"username": user.email, "password": "ShadowPassword9!"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"username": user.email, "password": "OriginalPass1!"},
        ).status_code
        == 204
    )
    assert client.get("/api/auth/me").json()["id"] == user.id


def test_legacy_handle_login_remains_compatible_and_conflicting_payload_is_denied(
    context,
):
    db, user, config, client = context
    assert (
        client.post(
            "/api/auth/login",
            json={"username": user.username, "password": "OriginalPass1!"},
        ).status_code
        == 204
    )
    response = client.post(
        "/api/auth/login",
        json={
            "email": user.email,
            "username": user.username,
            "password": "OriginalPass1!",
        },
    )
    assert response.status_code == 422 and "OriginalPass1!" not in response.text
    assert (
        client.post("/api/auth/login", json={"password": "OriginalPass1!"}).status_code
        == 422
    )


def test_email_and_handle_aliases_share_the_same_lockout(context, monkeypatch):
    db, user, config, client = context
    monkeypatch.setattr(settings, "login_max_failures", 3)
    for fields in [
        {"username": user.username},
        {"email": user.email.upper()},
        {"email": user.email},
    ]:
        assert (
            client.post(
                "/api/auth/login", json={**fields, "password": "WrongPassword9!"}
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/auth/login", json={"email": user.email, "password": "OriginalPass1!"}
        ).status_code
        == 429
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"username": user.username, "password": "OriginalPass1!"},
        ).status_code
        == 429
    )
    for audit in db.query(AuditLog).all():
        assert user.email not in (audit.metadata_json or "")
        assert "WrongPassword9!" not in (audit.metadata_json or "")


def test_case_and_whitespace_duplicate_emails_are_denied_by_database(context):
    db, user, config, client = context
    db.add(
        User(
            username="different-handle",
            email=" ADMIN@EXAMPLE.COM ",
            password_hash="unused",
            role_id=user.role_id,
            is_active=True,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_account_creation_uses_email_without_requiring_a_handle(context):
    db, user, config, client = context
    assert (
        client.post(
            "/api/auth/login", json={"email": user.email, "password": "OriginalPass1!"}
        ).status_code
        == 204
    )
    response = client.post(
        "/api/admin/users",
        json={
            "email": "New.Learner@Example.com",
            "role_id": user.role_id,
            "send_invitation": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["email"] == "new.learner@example.com"
    assert response.json()["username"].startswith("user-")
    assert db.query(EmailMessage).filter(EmailMessage.kind == "invitation").count() == 1
    duplicate = client.post(
        "/api/admin/users",
        json={
            "email": "NEW.LEARNER@example.com",
            "role_id": user.role_id,
            "password": "OriginalPass1!",
        },
    )
    assert duplicate.status_code == 409
    assert (
        client.post(
            "/api/admin/users",
            json={
                "email": "not-an-email",
                "role_id": user.role_id,
                "password": "OriginalPass1!",
            },
        ).status_code
        == 422
    )


def test_email_recovery_roundtrip_returns_to_email_signin(context):
    db, user, config, client = context
    assert (
        client.post(
            "/api/auth/login", json={"email": user.email, "password": "OriginalPass1!"}
        ).status_code
        == 204
    )
    assert (
        client.post(
            "/api/auth/email/request", json={"email": user.email.upper()}
        ).status_code
        == 202
    )
    code = code_from(db)
    assert (
        client.post(
            "/api/auth/email/complete",
            json={
                "email": user.email,
                "code": code,
                "new_password": "RecoveredPassword9!",
            },
        ).status_code
        == 204
    )
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.clear()
    assert (
        client.post(
            "/api/auth/login",
            json={"email": user.email.upper(), "password": "RecoveredPassword9!"},
        ).status_code
        == 204
    )


def test_email_change_revokes_sessions_and_old_codes_even_if_address_is_restored(
    context,
):
    db, user, config, client = context
    assert (
        client.post(
            "/api/auth/login", json={"email": user.email, "password": "OriginalPass1!"}
        ).status_code
        == 204
    )
    assert (
        client.post("/api/auth/email/request", json={"email": user.email}).status_code
        == 202
    )
    code = code_from(db)
    changed = client.patch(
        f"/api/admin/users/{user.id}", json={"email": "New.Admin@Example.com"}
    )
    assert changed.status_code == 200 and user.email == "new.admin@example.com"
    assert user.token_version == 2
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.clear()
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "OriginalPass1!"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "new.admin@example.com", "password": "OriginalPass1!"},
        ).status_code
        == 204
    )
    assert (
        client.patch(
            f"/api/admin/users/{user.id}", json={"email": "admin@example.com"}
        ).status_code
        == 200
    )
    assert user.token_version == 3
    assert (
        client.post(
            "/api/auth/email/complete",
            json={
                "email": "admin@example.com",
                "code": code,
                "new_password": "RecoveredPassword9!",
            },
        ).status_code
        == 400
    )


def test_first_admin_can_enroll_with_email_only(context, monkeypatch):
    db, user, config, client = context
    user.is_active = False
    db.commit()
    monkeypatch.setattr(settings, "bootstrap_admin_token", "synthetic-bootstrap-token")
    response = client.post(
        "/api/bootstrap/admin",
        json={
            "token": "synthetic-bootstrap-token",
            "email": "first@example.com",
            "password": "OriginalPass1!",
        },
    )
    assert response.status_code == 204
    assert client.get("/api/auth/me").json()["email"] == "first@example.com"


def test_unexpired_legacy_lockout_is_preserved_for_email_signin(context):
    from datetime import timedelta
    from app.models.models import AuthLoginAttempt
    from app.services.auth_service import _attempt_key
    from app.services.email_service import now

    db, user, config, client = context
    db.add(
        AuthLoginAttempt(
            key_hash=_attempt_key(user.username, "testclient"),
            failures=5,
            first_failure_at=now(),
            blocked_until=now() + timedelta(minutes=15),
        )
    )
    db.commit()
    assert (
        client.post(
            "/api/auth/login", json={"email": user.email, "password": "OriginalPass1!"}
        ).status_code
        == 429
    )


def test_long_email_is_not_stored_in_the_legacy_username_column(context):
    db, user, config, client = context
    assert (
        client.post(
            "/api/auth/login", json={"email": user.email, "password": "OriginalPass1!"}
        ).status_code
        == 204
    )

    email = "a" * 60 + "@example.com"
    result = client.post(
        "/api/admin/users",
        json={"email": email, "password": "OriginalPass1!", "role_id": user.role_id},
    )
    assert result.status_code == 200 and result.json()["email"] == email
    assert len(result.json()["username"]) <= 50
    client.cookies.clear()
    assert (
        client.post(
            "/api/auth/login", json={"email": email, "password": "OriginalPass1!"}
        ).status_code
        == 204
    )


def test_unknown_identifier_cannot_alias_the_internal_account_lockout_key(
    context, monkeypatch
):
    db, user, config, client = context
    monkeypatch.setattr(settings, "login_max_failures", 3)
    for _ in range(3):
        assert (
            client.post(
                "/api/auth/login",
                json={"username": f"account:{user.id}", "password": "WrongPassword9!"},
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/auth/login", json={"email": user.email, "password": "OriginalPass1!"}
        ).status_code
        == 204
    )
