import asyncio
from datetime import datetime, timedelta

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routers import vms
from app.db.session import Base
from app.models.models import (
    AuditLog,
    Class,
    DesktopPool,
    DurableOperation,
    Enrollment,
    Lab,
    LabAssignment,
    LabRun,
    Organization,
    OrganizationMembership,
    ProxmoxCluster,
    Role,
    StudentVM,
    User,
    VMTemplate,
)
from app.services.classroom_access import enforce_student_vm_operation
from app.services.operation_service import (
    OperationAuthorizationError,
    allocate_vmid,
    cancel_unauthorized_operation,
    execute_operation,
)
from app.services.organization_access import OrganizationContext
from app.workers import reconciliation_worker


def _database():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, autocommit=False, autoflush=False)()


def _not_found():
    request = httpx.Request("GET", "https://pve.test/status")
    response = httpx.Response(404, request=request)
    return httpx.HTTPStatusError("not found", request=request, response=response)


def _classroom(db):
    role = Role(name="Student")
    db.add(role)
    db.flush()
    instructor_a = User(
        username="instructor-a",
        email="a@example.test",
        password_hash="unused",
        role_id=role.id,
        is_active=True,
    )
    instructor_b = User(
        username="instructor-b",
        email="b@example.test",
        password_hash="unused",
        role_id=role.id,
        is_active=True,
    )
    student = User(
        username="student",
        email="student@example.test",
        password_hash="unused",
        role_id=role.id,
        is_active=True,
    )
    db.add_all([instructor_a, instructor_b, student])
    db.flush()
    organization = Organization(name="Org", slug="org", enabled=True)
    db.add(organization)
    db.flush()
    for user, member_role in (
        (instructor_a, "instructor"),
        (instructor_b, "instructor"),
        (student, "student"),
    ):
        db.add(
            OrganizationMembership(
                organization_id=organization.id,
                user_id=user.id,
                role=member_role,
                is_active=True,
            )
        )
    cluster = ProxmoxCluster(
        name="pve", api_url="https://pve.test/api2/json", is_active=True
    )
    db.add(cluster)
    db.flush()
    template = VMTemplate(
        organization_id=organization.id,
        proxmox_cluster_id=cluster.id,
        name="template",
        proxmox_node="pve-1",
        source_vmid=9000,
        enabled=True,
    )
    pool = DesktopPool(
        organization_id=organization.id,
        name="pool",
        pool_type="lab",
        default_protocol="novnc",
        enabled=True,
    )
    db.add_all([template, pool])
    db.flush()
    classes = [
        Class(
            organization_id=organization.id,
            name="A",
            instructor_id=instructor_a.id,
        ),
        Class(
            organization_id=organization.id,
            name="B",
            instructor_id=instructor_b.id,
        ),
    ]
    db.add_all(classes)
    db.flush()
    db.add_all(
        [
            Enrollment(class_id=item.id, user_id=student.id, is_active=True)
            for item in classes
        ]
    )
    labs = [
        Lab(
            organization_id=organization.id,
            class_id=item.id,
            name=f"Lab {item.name}",
            default_pool_id=pool.id,
            student_can_reset=False,
            student_can_power_off=True,
        )
        for item in classes
    ]
    db.add_all(labs)
    db.flush()
    now = datetime.utcnow()
    runs = [
        LabRun(
            organization_id=organization.id,
            lab_id=item.id,
            name=f"Run {item.name}",
            state="active",
            starts_at=now - timedelta(minutes=5),
            ends_at=now + timedelta(hours=1),
            created_by=(instructor_a.id if index == 0 else instructor_b.id),
        )
        for index, item in enumerate(labs)
    ]
    db.add_all(runs)
    db.flush()
    vms = [
        StudentVM(
            organization_id=organization.id,
            proxmox_cluster_id=cluster.id,
            owner_id=student.id,
            template_id=template.id,
            vm_name=f"vm-{index}",
            vmid=200000 + index,
            proxmox_node="pve-1",
            status="stopped",
        )
        for index in range(2)
    ]
    db.add_all(vms)
    db.flush()
    assignments = [
        LabAssignment(
            organization_id=organization.id,
            lab_run_id=runs[index].id,
            user_id=student.id,
            template_id=template.id,
            slot_index=1,
            status="ready",
            student_vm_id=vms[index].id,
            expires_at=now + timedelta(hours=1),
        )
        for index in range(2)
    ]
    db.add_all(assignments)
    db.commit()
    return {
        "organization": organization,
        "instructors": (instructor_a, instructor_b),
        "student": student,
        "labs": labs,
        "runs": runs,
        "vms": vms,
    }


class _StatusClient:
    calls = []
    modes = {}

    def __init__(self, cluster_id=None):
        self.cluster_id = cluster_id

    async def get_vm_status(self, _node, vmid):
        self.calls.append((self.cluster_id, vmid))
        mode = self.modes.get(vmid, "running")
        if mode == "404":
            raise _not_found()
        if mode == "error":
            raise RuntimeError("temporary TLS or API failure")
        return {"status": mode}


def test_reconciliation_uses_vm_cluster_and_only_404_marks_missing(monkeypatch):
    engine, db = _database()
    try:
        now = datetime.utcnow()
        db.add_all(
            [
                StudentVM(
                    id=1,
                    organization_id=1,
                    proxmox_cluster_id=11,
                    owner_id=1,
                    template_id=1,
                    vm_name="a",
                    vmid=101,
                    proxmox_node="n",
                    status="running",
                ),
                StudentVM(
                    id=2,
                    organization_id=1,
                    proxmox_cluster_id=22,
                    owner_id=1,
                    template_id=1,
                    vm_name="b",
                    vmid=102,
                    proxmox_node="n",
                    status="running",
                ),
                StudentVM(
                    id=3,
                    organization_id=1,
                    proxmox_cluster_id=22,
                    owner_id=1,
                    template_id=1,
                    vm_name="c",
                    vmid=103,
                    proxmox_node="n",
                    status="running",
                ),
                StudentVM(
                    id=4,
                    organization_id=1,
                    proxmox_cluster_id=11,
                    owner_id=1,
                    template_id=1,
                    vm_name="deleted",
                    vmid=104,
                    proxmox_node="n",
                    status="deleted",
                    deleted_at=now,
                ),
            ]
        )
        db.commit()
        _StatusClient.calls = []
        _StatusClient.modes = {101: "stopped", 102: "404", 103: "error"}
        monkeypatch.setattr(reconciliation_worker, "ProxmoxClient", _StatusClient)

        result = asyncio.run(reconciliation_worker._reconcile(db))

        assert result == {
            "checked": 3,
            "matched": 1,
            "missing": 1,
            "observation_errors": 1,
            "status_updated": 2,
        }
        assert _StatusClient.calls == [(11, 101), (22, 102), (22, 103)]
        assert db.get(StudentVM, 2).status == "missing"
        assert db.get(StudentVM, 3).status == "running"
        assert db.get(StudentVM, 4).status == "deleted"
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_app_record_cleanup_requires_fresh_explicit_404(monkeypatch):
    engine, db = _database()
    try:
        role = Role(name="Student")
        org = Organization(name="Org", slug="org", enabled=True)
        db.add_all([role, org])
        db.flush()
        actor = User(
            username="admin",
            email="admin@example.test",
            password_hash="x",
            role_id=role.id,
            is_active=True,
        )
        db.add(actor)
        db.flush()
        vm = StudentVM(
            organization_id=org.id,
            proxmox_cluster_id=9,
            owner_id=actor.id,
            template_id=1,
            vm_name="vm",
            vmid=200000,
            proxmox_node="n",
            status="missing",
        )
        db.add(vm)
        db.commit()
        context = OrganizationContext(org.id, org.slug, "admin")
        _StatusClient.calls = []
        _StatusClient.modes = {vm.vmid: "running"}
        monkeypatch.setattr(vms, "ProxmoxClient", _StatusClient)
        with pytest.raises(HTTPException) as present:
            asyncio.run(vms.delete_app_record_admin(vm.id, True, actor, db, context))
        assert present.value.status_code == 409
        assert db.get(StudentVM, vm.id).deleted_at is None

        _StatusClient.modes = {vm.vmid: "404"}
        result = asyncio.run(
            vms.delete_app_record_admin(vm.id, False, actor, db, context)
        )
        assert result["deleted"] is True
        assert db.get(StudentVM, vm.id).status == "deleted"
        assert len(_StatusClient.calls) == 2
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_student_reset_flag_and_two_instructor_scope(monkeypatch):
    engine, db = _database()
    try:
        data = _classroom(db)
        org = data["organization"]
        instructor_a, _instructor_b = data["instructors"]
        student = data["student"]
        vm_a, vm_b = data["vms"]
        with pytest.raises(HTTPException) as denied:
            enforce_student_vm_operation(
                db,
                user_id=student.id,
                organization_id=org.id,
                vm=vm_a,
                operation="reboot",
            )
        assert denied.value.status_code == 403
        data["labs"][0].student_can_reset = True
        db.commit()
        enforce_student_vm_operation(
            db, user_id=student.id, organization_id=org.id, vm=vm_a, operation="reset"
        )

        _StatusClient.calls = []
        _StatusClient.modes = {vm_a.vmid: "stopped", vm_b.vmid: "stopped"}
        monkeypatch.setattr(vms, "ProxmoxClient", _StatusClient)
        context = OrganizationContext(org.id, org.slug, "instructor")
        visible = asyncio.run(vms.list_vms(instructor_a, db, context))
        assert [item.id for item in visible] == [vm_a.id]
        with pytest.raises(HTTPException) as foreign:
            asyncio.run(vms.start_vm(vm_b.id, instructor_a, db, context))
        assert foreign.value.status_code == 404
        preview = vms.delete_vm_preview(vm_a.id, instructor_a, db, context)
        assert preview["vm_id"] == vm_a.id
    finally:
        db.close()
        Base.metadata.drop_all(engine)


class _LifecycleClient:
    calls = 0
    upid = "UPID:start"
    status = "running"

    def __init__(self, _cluster_id=None):
        pass

    async def start_vm(self, _node, _vmid):
        type(self).calls += 1
        return {"data": self.upid}

    async def wait_for_task(self, _node, _upid, **_kwargs):
        return {"exitstatus": "OK"}

    async def get_vm_status(self, _node, _vmid):
        return {"status": self.status}


class _DeleteClient:
    async def vm_exists(self, _vmid):
        return True

    stop_upid = None
    status = "running"
    delete_calls = 0

    def __init__(self, _cluster_id=None):
        pass

    async def get_vm_status(self, _node, _vmid):
        return {"status": self.status}

    async def stop_vm(self, _node, _vmid):
        return {"data": self.stop_upid}

    async def delete_vm(self, _node, _vmid):
        type(self).delete_calls += 1
        return {"data": "UPID:delete"}

    async def wait_for_task(self, _node, _upid, **_kwargs):
        return {"exitstatus": "OK"}


def _operation(db, data, *, requested_by, operation_type="vm.start"):
    row = DurableOperation(
        organization_id=data["organization"].id,
        requested_by=requested_by,
        operation_type=operation_type,
        target_type="student_vm",
        target_id=str(data["vms"][0].id),
        idempotency_key=f"{operation_type}:{requested_by}:{datetime.utcnow().timestamp()}",
        payload_json="{}",
        state="running",
        attempts=1,
    )
    db.add(row)
    db.commit()
    return row


def test_execution_revalidates_revoked_or_expired_classroom_access(monkeypatch):
    engine, db = _database()
    try:
        data = _classroom(db)
        _LifecycleClient.calls = 0
        monkeypatch.setattr(
            "app.services.operation_service.ProxmoxClient", _LifecycleClient
        )
        row = _operation(db, data, requested_by=data["student"].id)
        data["runs"][0].ends_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
        with pytest.raises(OperationAuthorizationError):
            asyncio.run(execute_operation(db, row))
        assert _LifecycleClient.calls == 0
        cancel_unauthorized_operation(
            db, row, OperationAuthorizationError("run expired after queueing")
        )
        assert row.state == "cancelled"
        assert (
            "run expired"
            in db.query(AuditLog).order_by(AuditLog.id.desc()).first().message
        )

        data["runs"][0].ends_at = datetime.utcnow() + timedelta(hours=1)
        membership = (
            db.query(OrganizationMembership)
            .filter(OrganizationMembership.user_id == data["student"].id)
            .one()
        )
        membership.is_active = False
        db.commit()
        second = _operation(
            db, data, requested_by=data["student"].id, operation_type="vm.reboot"
        )
        with pytest.raises(OperationAuthorizationError):
            asyncio.run(execute_operation(db, second))
        assert _LifecycleClient.calls == 0
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_lifecycle_requires_upid_and_observed_desired_state(monkeypatch):
    engine, db = _database()
    try:
        data = _classroom(db)
        actor = data["instructors"][0]
        monkeypatch.setattr(
            "app.services.operation_service.ProxmoxClient", _LifecycleClient
        )

        _LifecycleClient.upid = None
        missing = _operation(db, data, requested_by=actor.id)
        with pytest.raises(RuntimeError, match="task identifier"):
            asyncio.run(execute_operation(db, missing))
        assert missing.state != "succeeded"

        _LifecycleClient.upid = "UPID:start"
        _LifecycleClient.status = "stopped"
        stale = _operation(db, data, requested_by=actor.id)
        with pytest.raises(RuntimeError, match="did not observe"):
            asyncio.run(execute_operation(db, stale))
        assert stale.proxmox_upid == "UPID:start"
        assert stale.state != "succeeded"

        _LifecycleClient.status = "running"
        success = _operation(db, data, requested_by=actor.id)
        asyncio.run(execute_operation(db, success))
        assert success.state == "succeeded"
        assert success.proxmox_upid == "UPID:start"
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_delete_requires_stop_upid_and_stopped_observation(monkeypatch):
    engine, db = _database()
    try:
        data = _classroom(db)
        actor = data["instructors"][0]
        monkeypatch.setattr(
            "app.services.operation_service.ProxmoxClient", _DeleteClient
        )
        _DeleteClient.delete_calls = 0
        _DeleteClient.stop_upid = None
        _DeleteClient.status = "running"
        missing = _operation(
            db, data, requested_by=actor.id, operation_type="vm.delete"
        )
        with pytest.raises(RuntimeError, match="stop did not return"):
            asyncio.run(execute_operation(db, missing))
        assert _DeleteClient.delete_calls == 0

        _DeleteClient.stop_upid = "UPID:stop"
        stale = _operation(db, data, requested_by=actor.id, operation_type="vm.delete")
        with pytest.raises(RuntimeError, match="stopped before delete"):
            asyncio.run(execute_operation(db, stale))
        assert _DeleteClient.delete_calls == 0
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_vmid_allocator_uses_cluster_local_maximum():
    engine, db = _database()
    try:
        db.add_all(
            [
                StudentVM(
                    organization_id=1,
                    proxmox_cluster_id=1,
                    owner_id=1,
                    template_id=1,
                    vm_name="one",
                    vmid=200010,
                    proxmox_node="n",
                ),
                StudentVM(
                    organization_id=1,
                    proxmox_cluster_id=2,
                    owner_id=1,
                    template_id=1,
                    vm_name="two",
                    vmid=200001,
                    proxmox_node="n",
                ),
            ]
        )
        db.commit()
        assert allocate_vmid(db, "proxmox-cluster:1", proxmox_cluster_id=1) == 200011
        assert allocate_vmid(db, "proxmox-cluster:2", proxmox_cluster_id=2) == 200002
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_warning_requires_observed_running_state(monkeypatch):
    import json

    class WarningClient(_LifecycleClient):
        async def wait_for_task(self, _node, _upid, **kwargs):
            assert kwargs["allow_warnings"] is True
            return {"exitstatus": "WARNINGS: 1"}

    engine, db = _database()
    try:
        data = _classroom(db)
        monkeypatch.setattr(
            "app.services.operation_service.ProxmoxClient", WarningClient
        )
        WarningClient.upid = "UPID:start"
        WarningClient.status = "stopped"
        row = _operation(db, data, requested_by=data["instructors"][0].id)
        with pytest.raises(RuntimeError, match="did not observe"):
            asyncio.run(execute_operation(db, row))
        WarningClient.status = "running"
        asyncio.run(execute_operation(db, row))
        assert row.state == "succeeded"
        assert json.loads(row.result_json)["warnings"][0]["message"] == "WARNINGS: 1"
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_delete_absent_vm_uses_inventory_without_mutation(monkeypatch):
    class AbsentClient(_DeleteClient):
        async def vm_exists(self, _vmid):
            return False

        async def get_vm_status(self, *_args):
            raise AssertionError("Absent guest must not be queried")

        async def delete_vm(self, *_args):
            raise AssertionError("Absent guest must not be deleted")

    engine, db = _database()
    try:
        data = _classroom(db)
        monkeypatch.setattr(
            "app.services.operation_service.ProxmoxClient", AbsentClient
        )
        row = _operation(
            db, data, requested_by=data["instructors"][0].id, operation_type="vm.delete"
        )
        asyncio.run(execute_operation(db, row))
        assert row.state == "succeeded"
        assert data["vms"][0].deleted_at is not None
    finally:
        db.close()
        Base.metadata.drop_all(engine)
