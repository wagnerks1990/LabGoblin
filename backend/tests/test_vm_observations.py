import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.vm_observations import resources, observe_vm
from app.schemas.vm import VMResponse


def test_resource_units_multiple_disks_and_no_config_secret_disclosure():
    result = resources(
        {"cpu": 0.125, "mem": 1024, "netin": 0, "uptime": 90},
        {
            "cores": 4,
            "sockets": 2,
            "memory": "8192",
            "scsi0": "local:private-volume,size=60G",
            "virtio1": "local:data,size=1.5T",
            "ide2": "local:iso/installer.iso,media=cdrom,size=2G",
            "ide3": "local:vm-100-cloudinit,size=4M",
            "efidisk0": "local:efi,size=4M",
            "unused0": "local:unused,size=90G",
            "cipassword": "secret",
            "ciuser": "private",
        },
    )
    assert result.cpu_count == 8
    assert result.cpu_usage_percent == 12.5
    assert result.memory_bytes == 8192 * 1024**2
    assert result.disk_capacity_bytes == 60 * 1024**3 + int(1.5 * 1024**4)
    assert len(result.disks) == 2
    assert result.network_received_bytes == 0
    assert "secret" not in result.model_dump_json()
    assert "private" not in result.model_dump_json()
    assert resources({}, {"scsi0": "local:disk"}).disk_capacity_bytes is None
    assert resources({"cpu": float("nan")}, {}).cpu_usage_percent is None


def test_agent_address_is_observation_never_saved_connection_destination():
    vm = SimpleNamespace(
        id=1,
        vm_name="test",
        vmid=100,
        status="running",
        proxmox_node="pve",
        assigned_ip=None,
    )
    client = SimpleNamespace(
        get_vm_config=AsyncMock(
            return_value={
                "ostype": "win10",
                "net0": "virtio=02:00:00:00:00:01",
                "memory": 4096,
            }
        ),
        get_guest_network=AsyncMock(
            return_value=[
                {
                    "hardware-address": "02:00:00:00:00:01",
                    "ip-addresses": [{"ip-address": "10.20.30.40"}],
                }
            ]
        ),
    )
    asyncio.run(observe_vm(client, vm, {"status": "running"}))
    result = VMResponse.model_validate(vm, from_attributes=True)
    assert result.observed_addresses[0].address == "10.20.30.40"
    assert vm.assigned_ip is None
    assert result.operating_system == "windows"
    assert result.resources.memory_bytes == 4096 * 1024**2
    client.get_guest_network.side_effect = RuntimeError("private upstream credential")
    asyncio.run(observe_vm(client, vm, {"status": "running"}))
    assert vm.observed_addresses == []
    assert "unavailable" in vm.discovery_hint
    assert "private" not in vm.discovery_hint
    assert vm.resources.memory_bytes == 4096 * 1024**2


def test_stopped_vm_resources_without_agent_and_partial_failure():
    vm = SimpleNamespace(proxmox_node="pve", vmid=100)
    client = SimpleNamespace(
        get_vm_config=AsyncMock(return_value={"memory": 2048}),
        get_guest_network=AsyncMock(),
    )
    asyncio.run(observe_vm(client, vm, {"status": "stopped", "uptime": 0}))
    client.get_guest_network.assert_not_awaited()
    assert vm.resources.uptime_seconds == 0
    client.get_vm_config.side_effect = RuntimeError("private details")
    asyncio.run(observe_vm(client, vm, {"status": "running", "maxmem": 1000}))
    assert vm.resources.memory_bytes == 1000
    assert vm.resource_warning
    assert "private" not in vm.resource_warning
