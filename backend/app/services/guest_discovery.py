"""Read-only guest observations. Discovery never grants connection authority."""

import asyncio
import ipaddress
import re


def candidate_addresses(config, interfaces):
    adapters = {}
    for name, value in config.items():
        if not re.fullmatch(r"net\d+", name):
            continue
        match = re.search(r"(?:^|,)[\w-]+=([0-9a-fA-F:]{17})(?:,|$)", str(value))
        if match:
            adapters[match[1].lower()] = name[3:]
    found = {}
    for interface in interfaces[:64]:
        if not isinstance(interface, dict):
            continue
        mac = str(interface.get("hardware-address", "")).lower()
        if mac not in adapters:
            continue
        addresses = interface.get("ip-addresses", [])
        if not isinstance(addresses, list):
            continue
        configured = str(config.get(f"ipconfig{adapters[mac]}", ""))
        static = set()
        for item in configured.split(","):
            key, _, value = item.partition("=")
            if key in {"ip", "ip6"}:
                try:
                    static.add(str(ipaddress.ip_interface(value).ip))
                except ValueError:
                    pass
        for entry in addresses[:64]:
            if not isinstance(entry, dict):
                continue
            if not isinstance(entry.get("ip-address"), str):
                continue
            try:
                ip = ipaddress.ip_address(entry.get("ip-address", ""))
            except ValueError:
                continue
            if (
                ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_unspecified
                or ip.is_reserved
            ):
                continue
            found[(str(ip), mac)] = {
                "address": str(ip),
                "mac_address": mac,
                "matches_cloud_init": str(ip) in static,
            }
    return sorted(
        found.values(),
        key=lambda item: (
            not item["matches_cloud_init"],
            ipaddress.ip_address(item["address"]).version,
            item["address"],
            item["mac_address"],
        ),
    )[:32]


async def discover_guest_addresses(proxmox, vm, config):
    try:
        async with asyncio.timeout(8):
            interfaces = await proxmox.get_guest_network(vm.proxmox_node, vm.vmid)
        if not isinstance(interfaces, list):
            raise ValueError("Invalid agent response")
        addresses = candidate_addresses(config, interfaces)
        return addresses, (
            "Addresses reported by the guest agent and matched to Proxmox adapters."
            if addresses
            else "The agent reported no usable addresses on the VM's Proxmox adapters."
        )
    except Exception:
        return (
            [],
            "Guest agent unavailable. Start the VM and verify its agent is enabled.",
        )
