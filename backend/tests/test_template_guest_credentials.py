from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routers.console import reveal_guest_credentials
from app.api.routers.templates import (
    save_guest_credentials,
    guest_credential_status,
    change_guest_credential_policy,
    remove_guest_credentials,
)
from app.db.session import Base
from app.models.models import (
    AuditLog,
    Enrollment,
    Class,
    User,
    TemplateGuestCredential,
    LabRun,
)
from app.schemas.template_credentials import (
    TemplateCredentialWrite,
    TemplateCredentialPolicy,
)
from app.services.organization_access import OrganizationContext
from app.services.template_credentials import (
    connection_credentials,
    template_connection_revision,
)
from test_console_security import _two_instructor_console_data


@pytest.fixture
def context():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        organization, instructors, vms = _two_instructor_console_data(db)
        student = db.get(User, vms[0].owner_id)
        for classroom in db.query(Class).all():
            db.add(
                Enrollment(
                    class_id=classroom.id,
                    user_id=student.id,
                    role="student",
                    is_active=True,
                )
            )
        db.commit()
        admin = OrganizationContext(organization.id, organization.slug, "admin")
        learner = OrganizationContext(organization.id, organization.slug, "student")
        yield db, instructors, vms, student, admin, learner
    engine.dispose()


def save(db, user, vm, admin, visible=True):
    return save_guest_credentials(
        vm.template_id,
        TemplateCredentialWrite(
            username="lab-user",
            password="test-only-guest-login",
            domain="",
            auto_connect=True,
            student_visible=visible,
        ),
        user,
        db,
        admin,
    )


def test_saved_template_login_is_encrypted_and_status_is_secret_free(context):
    db, instructors, vms, student, admin, learner = context
    status = save(db, instructors[0], vms[0], admin)
    credential = db.get(TemplateGuestCredential, vms[0].template_id)
    assert "test-only-guest-login" not in credential.encrypted_credentials
    assert set(status) == {"configured", "auto_connect", "student_visible"}
    assert (
        guest_credential_status(vms[0].template_id, instructors[0], db, admin) == status
    )
    response = Response()
    result = reveal_guest_credentials(vms[0].id, response, student, db, learner)
    assert result["password"] == "test-only-guest-login"
    assert response.headers["cache-control"] == "no-store, private"
    audits = db.query(AuditLog).all()
    assert any(row.action == "guest_credentials_revealed" for row in audits)
    assert all("test-only-guest-login" not in str(row.message) for row in audits)


def test_reveal_requires_sharing_ownership_scope_and_active_assignment(context):
    db, instructors, vms, student, admin, learner = context
    save(db, instructors[0], vms[0], admin, visible=False)
    with pytest.raises(HTTPException) as denied:
        reveal_guest_credentials(vms[0].id, Response(), student, db, learner)
    assert denied.value.status_code == 403
    change_guest_credential_policy(
        vms[0].template_id,
        TemplateCredentialPolicy(auto_connect=True, student_visible=True),
        instructors[0],
        db,
        admin,
    )
    for user, scope in [
        (instructors[1], learner),
        (student, OrganizationContext(999, "other", "admin")),
    ]:
        with pytest.raises(HTTPException) as denied:
            reveal_guest_credentials(vms[0].id, Response(), user, db, scope)
        assert denied.value.status_code == 404
    for run in db.query(LabRun).all():
        run.state = "ended"
    db.commit()
    with pytest.raises(HTTPException):
        reveal_guest_credentials(vms[0].id, Response(), student, db, learner)


def test_students_cannot_change_template_credentials(context):
    db, instructors, vms, student, admin, learner = context
    with pytest.raises(HTTPException) as denied:
        save(db, student, vms[0], learner)
    assert denied.value.status_code == 403
    assert db.query(TemplateGuestCredential).count() == 0


def test_inherited_connections_follow_policy_revision_and_removal(context):
    db, instructors, vms, student, admin, learner = context
    save(db, instructors[0], vms[0], admin)
    profile = SimpleNamespace(encrypted_credentials="")
    assert connection_credentials(db, vms[0], profile)["username"] == "lab-user"
    revision = template_connection_revision(db, vms[0], profile)
    change_guest_credential_policy(
        vms[0].template_id,
        TemplateCredentialPolicy(auto_connect=False, student_visible=True),
        instructors[0],
        db,
        admin,
    )
    assert template_connection_revision(db, vms[0], profile) != revision
    with pytest.raises(HTTPException):
        connection_credentials(db, vms[0], profile)
    remove_guest_credentials(vms[0].template_id, instructors[0], db, admin)
    with pytest.raises(HTTPException):
        connection_credentials(db, vms[0], profile)
