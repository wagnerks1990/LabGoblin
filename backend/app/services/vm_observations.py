"""Bounded, read-only VM observations; never connection authorization."""

import asyncio
import math
import re
from datetime import datetime, timezone

from app.schemas.vm import VMResources, VMDisk
from app.services.guest_discovery import discover_guest_addresses
from app.services.remote_capabilities import guest_os


def number(value):
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) and parsed >= 0 else None
    except (TypeError, ValueError):
        return None


def resources(status, config):
    disks = []
    for name, value in config.items():
        if not re.fullmatch(r"(?:scsi|sata|virtio|ide)\d+", name):
            continue
        parts = str(value).split(",")
        if "media=cdrom" in parts or parts[0] == "none" or "cloudinit" in parts[0]:
            continue
        size = next((part[5:] for part in parts if part.startswith("size=")), "")
        match = re.fullmatch(r"(\d+(?:\.\d+)?)([KMGT]?)", size)
        capacity = None
        if match:
            capacity = int(
                float(match[1])
                * 1024 ** ("KMGT".index(match[2]) + 1 if match[2] else 0)
            )
        disks.append(VMDisk(device=name, capacity_bytes=capacity))
    memory = str(config.get("memory", "")).split(",")[0].removeprefix("current=")
    configured_memory = number(memory)
    cores, sockets = number(config.get("cores", 1)), number(config.get("sockets", 1))
    cpu = number(status.get("cpu"))
    return VMResources(
        cpu_count=int(cores * sockets) if config and cores and sockets else None,
        cpu_usage_percent=round(cpu * 100, 1) if cpu is not None else None,
        memory_bytes=int(configured_memory * 1024**2)
        if configured_memory is not None
        else number(status.get("maxmem")),
        memory_used_bytes=number(status.get("mem")),
        disk_capacity_bytes=sum(d.capacity_bytes for d in disks)
        if disks and all(d.capacity_bytes is not None for d in disks)
        else None,
        disks=disks,
        uptime_seconds=number(status.get("uptime")),
        network_received_bytes=number(status.get("netin")),
        network_sent_bytes=number(status.get("netout")),
        disk_read_bytes=number(status.get("diskread")),
        disk_written_bytes=number(status.get("diskwrite")),
    )


async def observe_vm(proxmox, vm, status):
    # The caller has already authorized this VM. Do not persist agent IPs into
    # assigned_ip: those observations must never become approved destinations.
    vm.observed_addresses = []
    vm.resources = resources(status, {})
    vm.observed_at = datetime.now(timezone.utc)
    vm.resource_warning = None
    vm.discovery_hint = "Start the VM to discover guest IP addresses."
    try:
        async with asyncio.timeout(5):
            config = await proxmox.get_vm_config(vm.proxmox_node, vm.vmid)
        vm.resources = resources(status, config)
        vm.operating_system = guest_os(config)
    except Exception:
        vm.resource_warning = (
            "VM configuration could not be read; some resource details are unavailable."
        )
        vm.discovery_hint = "Network discovery requires readable VM configuration."
        return
    if status.get("status") == "running":
        vm.observed_addresses, vm.discovery_hint = await discover_guest_addresses(
            proxmox, vm, config
        )
