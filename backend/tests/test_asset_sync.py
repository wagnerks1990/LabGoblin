import pytest
from app.services.asset_sync import AssetSyncService


class Obj:
    def __init__(self, **k):
        self.__dict__.update(k)


class Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.rows[0] if self.rows else None


class DB:
    def __init__(self):
        self._id = 1
        self.jobs = []

    def add(self, obj):
        if not getattr(obj, "id", None):
            obj.id = self._id
            self._id += 1
        if hasattr(obj, "method") and obj not in self.jobs:
            self.jobs.append(obj)

    def flush(self):
        pass

    def commit(self):
        pass

    def close(self):
        pass

    def query(self, _model):
        return Query(self.jobs)


@pytest.mark.asyncio
async def test_url_safety_rejects_bad_scheme(monkeypatch):
    s = AssetSyncService(DB())
    from app.core.config import settings

    monkeypatch.setattr(
        settings, "asset_source_iso_base_url", "http://192.0.2.10/assets/iso"
    )
    with pytest.raises(ValueError):
        await s.enqueue_iso(
            "a.iso", "local", "ftp://192.0.2.10/assets/iso/a.iso", ["pve-lab-01"]
        )


@pytest.mark.asyncio
async def test_url_safety_rejects_credentials(monkeypatch):
    s = AssetSyncService(DB())
    from app.core.config import settings

    monkeypatch.setattr(
        settings, "asset_source_iso_base_url", "http://192.0.2.10/assets/iso"
    )
    with pytest.raises(ValueError):
        await s.enqueue_iso(
            "a.iso", "local", "http://u:p@192.0.2.10/assets/iso/a.iso", ["pve-lab-01"]
        )


@pytest.mark.asyncio
async def test_enqueue_iso_creates_queued_job(monkeypatch):
    s = AssetSyncService(DB())
    from app.core.config import settings

    monkeypatch.setattr(
        settings, "asset_source_iso_base_url", "http://192.0.2.10/assets/iso"
    )

    async def _ok_targets(*_args, **_kwargs):
        return None

    monkeypatch.setattr(s, "_validate_targets", _ok_targets)
    jobs = await s.enqueue_iso(
        "ubuntu.iso", "local", "http://192.0.2.10/assets/iso/ubuntu.iso", ["pve-lab-02"]
    )
    assert jobs[0].state == "queued"
    assert jobs[0].finished_at is None


@pytest.mark.asyncio
async def test_process_job_ok_transitions_verified(monkeypatch):
    db = DB()
    job = Obj(
        id=1,
        method="download-url-iso",
        metadata_json="{'filename':'ubuntu.iso','storage_id':'local','source_url':'http://192.0.2.10/assets/iso/ubuntu.iso'}",
        target_node="pve-lab-02",
        state="queued",
        proxmox_upid=None,
        error=None,
        finished_at=None,
    )
    db.jobs = [job]

    import app.services.asset_sync as m

    monkeypatch.setattr(m, "SessionLocal", lambda: db)
    svc = AssetSyncService(db)

    async def _discover(nodes, storage):
        if not hasattr(_discover, "c"):
            _discover.c = 1
            return [{"node": nodes[0], "items": []}]
        return [{"node": nodes[0], "items": [{"filename": "ubuntu.iso"}]}]

    async def _download(*_args, **_kwargs):
        return "UPID:node:200"

    async def _task(*_args, **_kwargs):
        return {"status": "stopped", "exitstatus": "OK"}

    monkeypatch.setattr(
        AssetSyncService,
        "__init__",
        lambda self, _db: (
            setattr(self, "db", _db) or setattr(self, "assets", svc.assets)
        ),
    )
    monkeypatch.setattr(svc.assets, "discover_isos_by_node", _discover)
    monkeypatch.setattr(svc.assets, "download_url", _download)
    monkeypatch.setattr(svc.assets, "task_status", _task)

    await m.AssetSyncService.process_job(1)
    assert job.state == "verified"
    assert job.proxmox_upid == "UPID:node:200"
    assert job.finished_at is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source_url",
    [
        "http://127.0.0.1:8088/ubuntu.iso",
        "http://169.254.169.254/ubuntu.iso",
        "http://192.0.2.11/assets/iso/ubuntu.iso",
        "http://192.0.2.10/admin/ubuntu.iso",
        "http://192.0.2.10/assets/iso/../admin/ubuntu.iso",
        "http://192.0.2.10/assets/iso/ubuntu.iso?token=secret",
    ],
)
async def test_url_safety_rejects_non_configured_or_unsafe_destination(
    monkeypatch, source_url
):
    from app.core.config import settings

    monkeypatch.setattr(
        settings, "asset_source_iso_base_url", "http://192.0.2.10/assets/iso"
    )
    with pytest.raises(ValueError):
        await AssetSyncService(DB()).enqueue_iso(
            "ubuntu.iso", "local", source_url, ["pve-lab-01"]
        )


@pytest.mark.asyncio
async def test_poll_timeout_uses_config(monkeypatch):
    s = AssetSyncService(DB())
    job = Obj(id=99)

    import app.services.asset_sync as m

    monkeypatch.setattr(m.settings, "asset_sync_poll_interval_seconds", 1)
    monkeypatch.setattr(m.settings, "asset_sync_download_timeout_seconds", 3)

    async def _task(*_args, **_kwargs):
        return {"status": "running", "exitstatus": None}

    async def _nosleep(_secs):
        return None

    monkeypatch.setattr(s.assets, "task_status", _task)
    monkeypatch.setattr(s, "_sleep", _nosleep)

    ok, err = await s._poll_task_until_done(job, "pve-lab-02", "UPID:node:201")
    assert ok is False
    assert "Timed out waiting for Proxmox download task to complete" in err


@pytest.mark.asyncio
async def test_vm_sync_unsupported_sets_finished_at():
    s = AssetSyncService(DB())
    jobs = await s.sync_vm_template(
        "pve-lab-01", 303, "Ubuntu2604LTSv1c451c4", "local-lvm", ["pve-lab-02"]
    )
    assert jobs[0].state == "failed"
    assert jobs[0].error
    assert jobs[0].finished_at is not None
