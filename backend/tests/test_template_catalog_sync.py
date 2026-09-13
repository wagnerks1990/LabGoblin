from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.session import Base
from app.models.models import Organization, ProxmoxCluster, VMTemplate
from app.api.routers.admin_proxmox_setup import sync_templates
from app.services.proxmox_bootstrap import ProxmoxBootstrapService


@pytest.mark.asyncio
async def test_sync_preserves_legacy_identity_disabled_state_and_tenant_boundary(
    monkeypatch,
):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all(
            [
                Organization(id=1, name="One", slug="one"),
                Organization(id=2, name="Two", slug="two"),
                ProxmoxCluster(
                    id=1,
                    name="Cluster",
                    api_url="https://pve.test/api2/json",
                    is_active=True,
                ),
            ]
        )
        db.flush()
        legacy = VMTemplate(
            organization_id=1,
            name="Custom Windows",
            proxmox_node="pve1",
            source_vmid=9002,
            enabled=False,
        )
        other = VMTemplate(
            organization_id=2,
            name="Other tenant",
            proxmox_node="pve1",
            source_vmid=9002,
            enabled=False,
        )
        db.add_all([legacy, other])
        db.commit()
        legacy_id = legacy.id

        async def discover(self, cluster):
            return [
                {"vmid": 9002, "node": "pve1", "name": "Windows"},
                {"vmid": 9003, "node": "pve1", "name": "Custom Windows"},
            ]

        monkeypatch.setattr(ProxmoxBootstrapService, "discover_templates", discover)
        for _ in range(2):
            result = await sync_templates(
                _user=None, organization=SimpleNamespace(id=1), db=db
            )
            assert result["imported_count"] == 2
        assert db.query(VMTemplate).count() == 3
        assert legacy.id == legacy_id
        assert legacy.name == "Custom Windows"
        assert legacy.enabled is False
        assert legacy.proxmox_cluster_id == 1
        assert other.proxmox_cluster_id is None
        assert other.name == "Other tenant"
        assert (
            len({row.name for row in db.query(VMTemplate).filter_by(organization_id=1)})
            == 2
        )
    engine.dispose()
