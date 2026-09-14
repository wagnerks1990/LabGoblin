import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.guest_discovery import candidate_addresses, discover_guest_addresses


CONFIG = {
    "net0": "virtio=02:00:00:00:00:01,bridge=vmbr0",
    "ipconfig0": "ip=192.0.2.10/24,gw=192.0.2.1",
}


def interface(mac="02:00:00:00:00:01", addresses=None):
    return {
        "hardware-address": mac,
        "ip-addresses": [
            {"ip-address": value} for value in (addresses or ["192.0.2.10"])
        ],
    }


def test_discovery_matches_hypervisor_mac_and_static_cloud_init():
    result = candidate_addresses(
        CONFIG,
        [
            interface(addresses=["192.0.2.20", "192.0.2.10", "192.0.2.10"]),
            interface(mac="02:00:00:00:00:02"),
        ],
    )
    assert result == [
        {
            "address": "192.0.2.10",
            "mac_address": "02:00:00:00:00:01",
            "matches_cloud_init": True,
        },
        {
            "address": "192.0.2.20",
            "mac_address": "02:00:00:00:00:01",
            "matches_cloud_init": False,
        },
    ]


def test_discovery_filters_non_destinations_and_invalid_types():
    result = candidate_addresses(
        CONFIG,
        [
            interface(
                addresses=[
                    "127.0.0.1",
                    "169.254.1.1",
                    "::1",
                    "fe80::1",
                    "0.0.0.0",
                    "224.0.0.1",
                    "255.255.255.255",
                    "host.example",
                    123,
                    None,
                    "192.0.2.10",
                ]
            )
        ],
    )
    assert len(result) == 1
    assert result[0]["address"] == "192.0.2.10"


def test_discovery_dhcp_is_not_a_static_binding():
    result = candidate_addresses({**CONFIG, "ipconfig0": "ip=dhcp"}, [interface()])
    assert result[0]["matches_cloud_init"] is False


def test_discovery_does_not_read_or_return_guest_credentials():
    result = candidate_addresses(
        {**CONFIG, "cipassword": "must-not-return", "ciuser": "private-user"},
        [interface()],
    )
    assert "must-not-return" not in str(result)
    assert "private-user" not in str(result)


def test_agent_failure_is_explicit_and_does_not_probe_a_guest():
    proxmox = SimpleNamespace(
        get_guest_network=AsyncMock(side_effect=RuntimeError("secret error"))
    )
    addresses, hint = asyncio.run(
        discover_guest_addresses(
            proxmox, SimpleNamespace(proxmox_node="node", vmid=42), CONFIG
        )
    )
    assert addresses == []
    assert "unavailable" in hint
    assert "secret" not in hint
    proxmox.get_guest_network.assert_awaited_once_with("node", 42)
