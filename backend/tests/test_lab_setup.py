from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from app.models.models import (
    AuditLog,
    Class,
    DesktopPool,
    Enrollment,
    LabAssignment,
    LabRun,
    LabSetupReceipt,
    Organization,
    OrganizationMembership,
    Role,
    StudentVM,
    User,
    VMTemplate,
)
from app.services.auth_service import issue_session
from app.services.security import verify_password


@pytest.fixture
def setup_context():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, autoflush=False)()
    role = Role(name="Student")
    admin_role = Role(name="Admin")
    db.add(admin_role)
    db.add(role)
    db.flush()
    org = Organization(name="Setup school", slug="setup-school", enabled=True)
    other = Organization(name="Other school", slug="other-school", enabled=True)
    db.add_all([org, other])
    db.flush()
    users = []
    for name, tenant_role in [
        ("admin", "admin"),
        ("teacher", "instructor"),
        ("other-teacher", "instructor"),
        ("student", "student"),
    ]:
        user = User(
            username=name,
            email=f"{name}@example.test",
            password_hash="unused",
            role_id=admin_role.id if name == "admin" else role.id,
            role="Admin" if name == "admin" else "Student",
            is_active=True,
            force_password_change=False,
        )
        db.add(user)
        db.flush()
        db.add(
            OrganizationMembership(
                organization_id=org.id,
                user_id=user.id,
                role=tenant_role,
                is_active=True,
            )
        )
        users.append(user)
    template = VMTemplate(
        organization_id=org.id,
        name="Linux lab",
        source_vmid=9000,
        proxmox_node="pve1",
        enabled=True,
    )
    other_template = VMTemplate(
        organization_id=other.id,
        name="Private",
        source_vmid=9001,
        proxmox_node="pve1",
        enabled=True,
    )
    db.add_all([template, other_template])
    db.commit()
    headers = []
    for user in users:
        token = issue_session(db, user)
        db.commit()
        headers.append(
            {"Authorization": f"Bearer {token}", "X-Organization-ID": str(org.id)}
        )
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    try:
        yield db, client, users, headers, template, other_template
    finally:
        client.close()
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def payload(template, student, **changes):
    return dict(
        request_id=str(uuid4()),
        name="Networking lesson",
        class_name="Network class",
        template_id=template.id,
        student_ids=[student.id],
        reviewed=True,
        **changes,
    )


def test_one_save_creates_all_records_and_replay_is_safe(setup_context):
    db, client, users, headers, template, _ = setup_context
    body = payload(template, users[3], state="active", slots=2)
    response = client.post("/api/admin/lab-setups", json=body, headers=headers[1])
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["assignment_count"] == 2
    assert (
        db.query(Class).count()
        == db.query(DesktopPool).count()
        == db.query(LabRun).count()
        == 1
    )
    assert db.query(Enrollment).count() == 1
    assert (
        client.post("/api/admin/lab-setups", json=body, headers=headers[1]).json()[
            "run_id"
        ]
        == saved["run_id"]
    )
    assert db.query(LabAssignment).count() == 2
    body["name"] = "Changed replay"
    assert (
        client.post("/api/admin/lab-setups", json=body, headers=headers[1]).status_code
        == 409
    )
    assignments = client.get("/api/classroom/assignments", headers=headers[3]).json()[
        "data"
    ]
    assert all(row["access_open"] and row["can_provision"] for row in assignments)
    enrollment = db.query(Enrollment).first()
    enrollment.is_active = False
    db.commit()
    assert not client.get("/api/classroom/assignments", headers=headers[3]).json()[
        "data"
    ][0]["can_provision"]


def test_failed_save_rolls_back_class_pool_and_accounts(setup_context):
    db, client, users, headers, template, other_template = setup_context
    body = payload(other_template, users[3])
    assert (
        client.post("/api/admin/lab-setups", json=body, headers=headers[1]).status_code
        == 422
    )
    assert (
        db.query(Class).count()
        == db.query(DesktopPool).count()
        == db.query(LabSetupReceipt).count()
        == 0
    )
    body = payload(
        template,
        users[3],
        new_students=[
            {
                "username": "new-learner",
                "email": "new@example.test",
                "password": "Example-Only-1234!",
            },
            {
                "username": "student",
                "email": "duplicate@example.test",
                "password": "Example-Only-1234!",
            },
        ],
    )
    response = client.post("/api/admin/lab-setups", json=body, headers=headers[0])
    assert response.status_code == 409, response.text
    assert db.query(User).count() == 4
    assert db.query(Class).count() == db.query(DesktopPool).count() == 0


def test_account_creation_is_platform_admin_only_and_secrets_are_not_returned(
    setup_context,
):
    db, client, users, headers, template, _ = setup_context
    body = payload(
        template,
        users[3],
        new_students=[
            {
                "username": "new-learner",
                "email": "new@example.test",
                "password": "Example-Only-1234!",
            }
        ],
    )
    assert (
        client.post("/api/admin/lab-setups", json=body, headers=headers[1]).status_code
        == 403
    )
    response = client.post("/api/admin/lab-setups", json=body, headers=headers[0])
    assert response.status_code == 200, response.text
    assert "Example-Only" not in response.text
    created = db.query(User).filter(User.username == "new-learner").one()
    assert created.force_password_change and verify_password(
        "Example-Only-1234!", created.password_hash
    )
    assert (
        db.query(OrganizationMembership)
        .filter(OrganizationMembership.user_id == created.id)
        .one()
        .role
        == "student"
    )
    assert all("Example-Only" not in str(row.__dict__) for row in db.query(AuditLog))


def test_edit_checks_scope_stale_changes_and_preserves_bindings(setup_context):
    db, client, users, headers, template, _ = setup_context
    saved = client.post(
        "/api/admin/lab-setups", json=payload(template, users[3]), headers=headers[1]
    ).json()
    path = f"/api/admin/lab-setups/{saved['run_id']}"
    assert client.get(path, headers=headers[2]).status_code == 404
    assert client.get(path, headers=headers[3]).status_code == 403
    body = payload(template, users[3])
    body.update(
        template_id=None,
        pool_id=saved["pool_id"],
        class_id=saved["class_id"],
        expected_etag=saved["etag"],
        name="Edited lab",
    )
    response = client.put(path, json=body, headers=headers[1])
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Edited lab"
    stale = {**body, "request_id": str(uuid4()), "name": "Stale overwrite"}
    assert client.put(path, json=stale, headers=headers[1]).status_code == 409
    vm = StudentVM(
        organization_id=template.organization_id,
        owner_id=users[3].id,
        template_id=template.id,
        vm_name="existing-vm",
        vmid=200000,
        proxmox_node="pve1",
        status="running",
    )
    db.add(vm)
    db.flush()
    assignment = db.query(LabAssignment).one()
    assignment.student_vm_id = vm.id
    assignment.status = "ready"
    db.commit()
    current = client.get(path, headers=headers[1]).json()
    body.update(request_id=str(uuid4()), expected_etag=current["etag"], student_ids=[])
    assert client.put(path, json=body, headers=headers[1]).status_code == 409
    assert db.query(LabAssignment).one().student_vm_id == vm.id


def test_catalog_and_mutations_deny_students_and_other_tenants(setup_context):
    db, client, users, headers, template, other_template = setup_context
    assert (
        client.get("/api/admin/lab-setups/catalog", headers=headers[3]).status_code
        == 403
    )
    catalog = client.get("/api/admin/lab-setups/catalog", headers=headers[1])
    assert catalog.status_code == 200, catalog.text
    assert [row["id"] for row in catalog.json()["templates"]] == [template.id]
    body = payload(template, users[3])
    assert (
        client.post("/api/admin/lab-setups", json=body, headers=headers[3]).status_code
        == 403
    )
    assert client.post("/api/admin/lab-setups", json=body).status_code == 401
    headers[1]["X-Organization-ID"] = str(other_template.organization_id)
    assert (
        client.post("/api/admin/lab-setups", json=body, headers=headers[1]).status_code
        == 403
    )


def test_stale_compatibility_role_cannot_create_accounts(setup_context):
    db, client, users, headers, template, _ = setup_context
    users[1].role = "Admin"  # Deprecated text must not override canonical Student role.
    db.commit()
    body = payload(
        template,
        users[3],
        new_students=[
            {
                "username": "new-learner",
                "email": "new@example.test",
                "password": "Example-Only-1234!",
            }
        ],
    )
    assert (
        client.post("/api/admin/lab-setups", json=body, headers=headers[1]).status_code
        == 403
    )
    assert db.query(User).count() == 4


def test_cookie_setup_requires_same_origin_and_live_session(setup_context):
    from app.core.config import settings
    from app.models.models import AuthSession

    db, client, users, headers, template, _ = setup_context
    token = headers[1]["Authorization"].split(" ", 1)[1]
    client.cookies.set(settings.auth_cookie_name, token)
    scope = {"X-Organization-ID": headers[1]["X-Organization-ID"]}
    body = payload(template, users[3])
    assert (
        client.post(
            "/api/admin/lab-setups",
            json=body,
            headers={**scope, "Origin": "https://untrusted.example"},
        ).status_code
        == 403
    )
    response = client.post(
        "/api/admin/lab-setups",
        json=body,
        headers={
            **scope,
            "Origin": "http://testserver",
            "Sec-Fetch-Site": "same-origin",
        },
    )
    assert response.status_code == 200, response.text
    for session in db.query(AuthSession).filter(AuthSession.user_id == users[1].id):
        db.delete(session)
    db.commit()
    assert client.get("/api/admin/lab-setups/catalog", headers=scope).status_code == 401
