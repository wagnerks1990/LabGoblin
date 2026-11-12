from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routers import vms
from app.db.session import Base, get_db
from app.main import app
from app.models.models import (
    Class,
    DesktopPool,
    Enrollment,
    Group,
    Lab,
    LabAssignment,
    LabRun,
    Organization,
    OrganizationMembership,
    Role,
    StudentVM,
    User,
    VMTemplate,
)
from app.services.auth_service import issue_session


class _FakeProxmox:
    async def get_vm_status(self, _node, _vmid):
        return {"status": "stopped"}


def _token(db, username: str) -> str:
    user = db.query(User).filter(User.username == username).first()
    token = issue_session(db, user)
    db.commit()
    return token


def _headers(db, username: str, organization_id: int) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_token(db, username)}",
        "X-Organization-ID": str(organization_id),
    }


def _auth_headers(db, username: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(db, username)}"}


def test_two_organization_http_authorization_matrix(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(engine)
    db = TestingSession()

    student_role = Role(name="Student")
    admin_role = Role(name="Admin")
    db.add_all([student_role, admin_role])
    db.flush()
    student_a = User(
        username="student-a",
        email="a@example.test",
        password_hash="unused",
        role_id=student_role.id,
        role="Student",
        is_active=True,
    )
    student_b = User(
        username="student-b",
        email="b@example.test",
        password_hash="unused",
        role_id=student_role.id,
        role="Student",
        is_active=True,
    )
    instructor_b = User(
        username="instructor-b",
        email="instructor-b@example.test",
        password_hash="unused",
        role_id=student_role.id,
        role="Student",
        is_active=True,
    )
    owner = User(
        username="owner",
        email="owner@example.test",
        password_hash="unused",
        role_id=student_role.id,
        role="Student",
        is_active=True,
    )
    platform_admin = User(
        username="platform-admin",
        email="platform-admin@example.test",
        password_hash="unused",
        role_id=admin_role.id,
        role="Admin",
        is_active=True,
    )
    db.add_all([student_a, student_b, instructor_b, owner, platform_admin])
    db.flush()

    organization_a = Organization(
        name="Organization A", slug="organization-a", enabled=True
    )
    organization_b = Organization(
        name="Organization B", slug="organization-b", enabled=True
    )
    organization_c = Organization(
        name="Organization C", slug="organization-c", enabled=True
    )
    db.add_all([organization_a, organization_b, organization_c])
    db.flush()
    db.add_all(
        [
            OrganizationMembership(
                organization_id=organization_a.id,
                user_id=student_a.id,
                role="student",
                is_active=True,
            ),
            OrganizationMembership(
                organization_id=organization_a.id,
                user_id=student_b.id,
                role="student",
                is_active=True,
            ),
            OrganizationMembership(
                organization_id=organization_b.id,
                user_id=student_a.id,
                role="instructor",
                is_active=True,
            ),
            OrganizationMembership(
                organization_id=organization_b.id,
                user_id=instructor_b.id,
                role="instructor",
                is_active=True,
            ),
            OrganizationMembership(
                organization_id=organization_b.id,
                user_id=owner.id,
                role="owner",
                is_active=True,
            ),
        ]
    )

    template_a = VMTemplate(
        organization_id=organization_a.id,
        name="A template",
        proxmox_node="pve-a",
        source_vmid=100,
    )
    template_b = VMTemplate(
        organization_id=organization_b.id,
        name="B template",
        proxmox_node="pve-b",
        source_vmid=200,
    )
    db.add_all([template_a, template_b])
    db.flush()
    own_vm = StudentVM(
        organization_id=organization_a.id,
        owner_id=student_a.id,
        template_id=template_a.id,
        vm_name="a-own",
        vmid=1001,
        proxmox_node="pve-a",
    )
    db.add_all(
        [
            own_vm,
            StudentVM(
                organization_id=organization_a.id,
                owner_id=student_b.id,
                template_id=template_a.id,
                vm_name="a-other",
                vmid=1002,
                proxmox_node="pve-a",
            ),
            StudentVM(
                organization_id=organization_b.id,
                owner_id=instructor_b.id,
                template_id=template_b.id,
                vm_name="b-visible-to-instructor",
                vmid=2001,
                proxmox_node="pve-b",
            ),
        ]
    )
    db.add_all(
        [
            Class(
                organization_id=organization_b.id,
                name="A instructor class",
                instructor_id=student_a.id,
            ),
            Class(
                organization_id=organization_b.id,
                name="B instructor class",
                instructor_id=instructor_b.id,
            ),
            Group(organization_id=organization_b.id, name="B administrators group"),
        ]
    )
    db.flush()
    class_a = Class(organization_id=organization_a.id, name="Organization A class")
    pool_a = DesktopPool(
        organization_id=organization_a.id,
        name="Organization A pool",
        pool_type="lab",
        template_vmid=template_a.source_vmid,
        default_protocol="novnc",
        enabled=True,
        maintenance_mode=False,
    )
    db.add_all([class_a, pool_a])
    db.flush()
    enrollment_a = Enrollment(
        class_id=class_a.id, user_id=student_a.id, role="student", is_active=True
    )
    lab_a = Lab(
        organization_id=organization_a.id,
        class_id=class_a.id,
        name="Organization A lab",
        default_pool_id=pool_a.id,
        console_enabled=True,
        terminal_enabled=True,
    )
    db.add_all([enrollment_a, lab_a])
    db.flush()
    run_a = LabRun(
        organization_id=organization_a.id,
        lab_id=lab_a.id,
        name="Active run",
        state="active",
        max_vms_per_student=1,
        created_by=owner.id,
    )
    db.add(run_a)
    db.flush()
    db.add(
        LabAssignment(
            organization_id=organization_a.id,
            lab_run_id=run_a.id,
            user_id=student_a.id,
            template_id=template_a.id,
            slot_index=1,
            status="ready",
            student_vm_id=own_vm.id,
        )
    )
    db.commit()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(vms, "ProxmoxClient", _FakeProxmox)
    client = TestClient(app)
    try:
        own_vms = client.get(
            "/api/vms", headers=_headers(db, "student-a", organization_a.id)
        )
        assert own_vms.status_code == 200
        assert [row["vm_name"] for row in own_vms.json()] == ["a-own"]

        instructor_vms = client.get(
            "/api/vms", headers=_headers(db, "student-a", organization_b.id)
        )
        assert instructor_vms.status_code == 200
        # Organization-level instructor membership does not grant access to a
        # VM belonging to another instructor's class.
        assert instructor_vms.json() == []

        assert (
            client.get(
                "/api/vms", headers=_headers(db, "student-a", organization_c.id)
            ).status_code
            == 403
        )
        assert (
            client.get(
                "/api/admin/templates",
                headers=_headers(db, "student-a", organization_a.id),
            ).status_code
            == 403
        )
        assert (
            client.get(
                "/api/admin/templates",
                headers=_headers(db, "student-a", organization_b.id),
            ).status_code
            == 200
        )

        own_classes = client.get(
            "/api/admin/classes", headers=_headers(db, "student-a", organization_b.id)
        )
        assert own_classes.status_code == 200
        assert [row["name"] for row in own_classes.json()["data"]] == [
            "A instructor class"
        ]

        assert (
            client.get(
                "/api/admin/groups",
                headers=_headers(db, "student-a", organization_b.id),
            ).status_code
            == 403
        )
        assert (
            client.get(
                "/api/admin/groups", headers=_headers(db, "owner", organization_b.id)
            ).status_code
            == 200
        )

        created = client.post(
            "/api/admin/organizations",
            headers=_auth_headers(db, "platform-admin"),
            json={"name": "New School", "slug": "new-school"},
        )
        assert created.status_code == 201
        new_organization_id = created.json()["id"]
        members = client.get(
            f"/api/admin/organizations/{new_organization_id}/members",
            headers=_auth_headers(db, "platform-admin"),
        )
        assert members.status_code == 200
        assert members.json() == [
            {
                "id": members.json()[0]["id"],
                "user_id": platform_admin.id,
                "username": "platform-admin",
                "email": platform_admin.email,
                "role": "owner",
                "is_active": True,
            }
        ]
        last_owner_delete = client.delete(
            f"/api/admin/organizations/{new_organization_id}/members/{platform_admin.id}",
            headers=_auth_headers(db, "platform-admin"),
        )
        assert last_owner_delete.status_code == 409
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(engine)
