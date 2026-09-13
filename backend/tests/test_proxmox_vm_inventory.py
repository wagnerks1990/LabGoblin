import httpx
import pytest

from app.services.proxmox import ProxmoxClient


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ([], False),
        ([{"type": "qemu", "vmid": 200000}], True),
        ([{"type": "lxc", "vmid": "200000"}], True),
        ([{"type": "qemu", "vmid": 9002}], False),
    ],
)
async def test_vm_exists_checks_cluster_collection(monkeypatch, data, expected):
    def handler(request):
        assert request.url.path == "/api2/json/cluster/resources"
        assert request.url.params["type"] == "vm"
        return httpx.Response(200, json={"data": data})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )
    client = object.__new__(ProxmoxClient)
    client.base_url = "https://pve.test/api2/json"
    client.headers = {}
    client.verify_ssl = True
    assert await client.vm_exists(200000) is expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data", [None, {}, [None], [{"type": "qemu"}], [{"type": "qemu", "vmid": True}]]
)
async def test_vm_exists_rejects_invalid_inventory(monkeypatch, data):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: real_client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"data": data})
            ),
            **kw,
        ),
    )
    client = object.__new__(ProxmoxClient)
    client.base_url = "https://pve.test/api2/json"
    client.headers = {}
    client.verify_ssl = True
    with pytest.raises(RuntimeError, match="Invalid Proxmox"):
        await client.vm_exists(200000)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 500])
async def test_inventory_failure_is_not_vm_absence(monkeypatch, status):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: real_client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(status, json={"data": None})
            ),
            **kw,
        ),
    )
    client = object.__new__(ProxmoxClient)
    client.base_url = "https://pve.test/api2/json"
    client.headers = {}
    client.verify_ssl = True
    with pytest.raises(httpx.HTTPStatusError):
        await client.vm_exists(200000)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exitstatus", "allowed", "success"),
    [
        ("OK", False, True),
        ("WARNINGS: 1", False, False),
        ("WARNINGS: 1", True, True),
        ("WARNINGS: 0", True, False),
        ("ERROR: startup failed", True, False),
        ("WARNINGS: 1 error", True, False),
    ],
)
async def test_task_warning_acceptance_is_explicit(
    monkeypatch, exitstatus, allowed, success
):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: real_client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200, json={"data": {"status": "stopped", "exitstatus": exitstatus}}
                )
            ),
            **kw,
        ),
    )
    client = object.__new__(ProxmoxClient)
    client.base_url = "https://pve.test/api2/json"
    client.headers = {}
    client.verify_ssl = True
    if success:
        result = await client.wait_for_task("pve", "task", allow_warnings=allowed)
        assert result["exitstatus"] == exitstatus
    else:
        with pytest.raises(RuntimeError, match="Proxmox task failed"):
            await client.wait_for_task("pve", "task", allow_warnings=allowed)
