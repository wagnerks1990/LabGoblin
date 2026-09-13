from fastapi.testclient import TestClient
import httpx
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
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
    Lab,
    LabAssignment,
    Organization,
    OrganizationMembership,
    ProxmoxCluster,
    ProxmoxNode,
    Role,
    StudentVM,
    User,
    VMTemplate,
)
from app.services.auth_service import issue_session
from app.services.classroom_access import (
    assignment_effectively_open,
    run_effectively_open,
)
from app.services import operation_service
from app.models.models import DurableOperation
import asyncio


class _FakeProxmox:
    exists = False

    def __init__(self, cluster_id=None):
        self.cluster_id = cluster_id

    async def vm_exists(self, _vmid):
        return self.exists

    async def clone_vm(self, _node, _source_vmid, _vmid, _name):
        self.exists = True
        return {"data": "UPID:clone"}

    async def get_vm_status(self, _node, _vmid):
        if not self.exists:
            request = httpx.Request("GET", "https://pve.test/status")
            response = httpx.Response(404, request=request)
            raise httpx.HTTPStatusError("not found", request=request, response=response)
        return {"status": "stopped"}

    async def wait_for_task(self, _node, _upid, **_kwargs):
        return {"status": "stopped", "exitstatus": "OK"}

    async def start_vm(self, _node, _vmid):
        return {"data": None}


def _headers(db, user, organization):
    token = issue_session(db, user)
    db.commit()
    return {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(organization.id),
    }


def test_scheduled_run_opens_and_expires_by_time_window():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    run = SimpleNamespace(
        state="scheduled",
        starts_at=now - timedelta(minutes=1),
        ends_at=now + timedelta(minutes=1),
    )
    assignment = SimpleNamespace(
        status="assigned", expires_at=now + timedelta(minutes=1)
    )
    assert run_effectively_open(run, now)
    assert assignment_effectively_open(assignment, run, now)
    assert not run_effectively_open(run, now + timedelta(minutes=2))
    assignment.status = "revoked"
    assert not assignment_effectively_open(assignment, run, now)


def test_assignment_gates_student_vm_lifecycle(monkeypatch):
    _FakeProxmox.exists = False
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(engine)
    db = TestingSession()
    role = Role(name="Student")
    db.add(role)
    db.flush()
    instructor = User(
        username="teacher",
        email="teacher@example.com",
        password_hash="unused",
        role_id=role.id,
        role="Student",
        is_active=True,
    )
    student = User(
        username="student",
        email="student@example.com",
        password_hash="unused",
        role_id=role.id,
        role="Student",
        is_active=True,
    )
    unassigned = User(
        username="unassigned",
        email="unassigned@example.com",
        password_hash="unused",
        role_id=role.id,
        role="Student",
        is_active=True,
    )
    db.add_all([instructor, student, unassigned])
    db.flush()
    organization = Organization(
        name="Networking Program", slug="networking", enabled=True
    )
    db.add(organization)
    db.flush()
    cluster = ProxmoxCluster(
        name="classroom-test",
        api_url="https://pve.test/api2/json",
        token_user="svc@pve",
        token_id="lab",
        encrypted_token_secret="unused",
        is_active=True,
    )
    db.add(cluster)
    db.flush()
    db.add(ProxmoxNode(cluster_id=cluster.id, node_name="pve-1", status="online"))
    db.add_all(
        [
            OrganizationMembership(
                organization_id=organization.id,
                user_id=instructor.id,
                role="instructor",
                is_active=True,
            ),
            OrganizationMembership(
                organization_id=organization.id,
                user_id=student.id,
                role="student",
                is_active=True,
            ),
            OrganizationMembership(
                organization_id=organization.id,
                user_id=unassigned.id,
                role="student",
                is_active=True,
            ),
        ]
    )
    template = VMTemplate(
        organization_id=organization.id,
        proxmox_cluster_id=cluster.id,
        name="Network Lab",
        proxmox_node="pve-1",
        source_vmid=9000,
        enabled=True,
    )
    db.add(template)
    db.flush()
    pool = DesktopPool(
        organization_id=organization.id,
        name="Networking Pool",
        pool_type="lab",
        template_vmid=9000,
        default_protocol="novnc",
        enabled=True,
        maintenance_mode=False,
    )
    classroom = Class(
        organization_id=organization.id, name="Network+", instructor_id=instructor.id
    )
    db.add_all([pool, classroom])
    db.flush()
    enrollment = Enrollment(
        class_id=classroom.id, user_id=student.id, role="student", is_active=True
    )
    lab = Lab(
        organization_id=organization.id,
        class_id=classroom.id,
        name="Routing Lab",
        default_pool_id=pool.id,
        student_can_power_off=False,
        terminal_enabled=True,
        console_enabled=True,
    )
    db.add_all([enrollment, lab])
    db.commit()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(vms, "ProxmoxClient", _FakeProxmox)
    monkeypatch.setattr(operation_service, "ProxmoxClient", _FakeProxmox)

    async def discover_templates(_self, _cluster):
        return [
            {"node": "pve-1", "vmid": 9000, "name": "Network Lab", "template": True}
        ]

    monkeypatch.setattr(
        vms.ProxmoxBootstrapService, "discover_templates", discover_templates
    )
    client = TestClient(app)
    instructor_headers = _headers(db, instructor, organization)
    student_headers = _headers(db, student, organization)
    unassigned_headers = _headers(db, unassigned, organization)
    try:
        created_run = client.post(
            "/api/admin/lab-runs",
            headers=instructor_headers,
            json={
                "lab_id": lab.id,
                "name": "Routing Lab - Period 2",
                "max_vms_per_student": 1,
            },
        )
        assert created_run.status_code == 201, created_run.text
        run_id = created_run.json()["data"]["id"]

        assigned = client.post(
            f"/api/admin/lab-runs/{run_id}/assignments",
            headers=instructor_headers,
            json={"user_id": student.id},
        )
        assert assigned.status_code == 201, assigned.text
        assignment_id = assigned.json()["data"]["id"]
        duplicate = client.post(
            f"/api/admin/lab-runs/{run_id}/assignments",
            headers=instructor_headers,
            json={"user_id": student.id, "slot_index": 1},
        )
        assert duplicate.status_code == 201
        assert duplicate.json()["data"]["id"] == assignment_id
        over_quota = client.post(
            f"/api/admin/lab-runs/{run_id}/assignments",
            headers=instructor_headers,
            json={"user_id": student.id, "slot_index": 2},
        )
        assert over_quota.status_code == 409

        activated = client.patch(
            f"/api/admin/lab-runs/{run_id}/state",
            headers=instructor_headers,
            json={"action": "activate"},
        )
        assert activated.status_code == 200
        assert activated.json()["data"]["effective_open"] is True

        catalog = client.get("/api/templates", headers=student_headers)
        assert [item["id"] for item in catalog.json()] == [template.id]
        assert client.get("/api/templates", headers=unassigned_headers).json() == []
        denied = client.post(
            "/api/vms",
            headers=unassigned_headers,
            json={
                "template_id": template.id,
                "lab_name": "routing",
                "auto_start": False,
            },
        )
        assert denied.status_code == 403

        provisioned = client.post(
            "/api/vms",
            headers=student_headers,
            json={
                "template_id": template.id,
                "assignment_id": assignment_id,
                "lab_name": "routing",
                "auto_start": False,
            },
        )
        assert provisioned.status_code == 202, provisioned.text
        vm_id = provisioned.json()["id"]
        operation = (
            db.query(DurableOperation)
            .filter(DurableOperation.id == provisioned.json()["operation_id"])
            .one()
        )
        asyncio.run(operation_service.execute_operation(db, operation))
        assignment = (
            db.query(LabAssignment).filter(LabAssignment.id == assignment_id).one()
        )
        assert assignment.status == "ready"
        assert assignment.student_vm_id == vm_id
        assert (
            db.query(StudentVM)
            .filter(StudentVM.id == vm_id, StudentVM.owner_id == student.id)
            .count()
            == 1
        )

        visible_vm = client.get("/api/vms", headers=student_headers).json()[0]
        assert visible_vm["allowed_stop"] is False
        assert visible_vm["allowed_delete"] is False
        assert visible_vm["allowed_terminal"] is True
        assert (
            client.post(f"/api/vms/{vm_id}/stop", headers=student_headers).status_code
            == 403
        )
        ended = client.patch(
            f"/api/admin/lab-runs/{run_id}/state",
            headers=instructor_headers,
            json={"action": "end", "confirmation": f"END {run_id}"},
        )
        assert ended.status_code == 200
        assert client.get("/api/vms", headers=student_headers).json() == []
        assert (
            client.get(f"/api/vms/{vm_id}/status", headers=student_headers).status_code
            == 403
        )
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(engine)
