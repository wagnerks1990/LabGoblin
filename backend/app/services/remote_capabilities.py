"""Connection discovery uses hypervisor configuration, never guest-reported OS/IP."""

from fastapi import HTTPException


def guest_os(config):
    ostype = str(config.get("ostype", "")).lower()
    if ostype in {
        "win11",
        "win10",
        "win8",
        "win7",
        "w2k8",
        "wvista",
        "w2k3",
        "wxp",
        "w2k",
        "w10",
        "w11",
    }:
        return "windows"
    if ostype in {"l26", "l24"}:
        return "linux"
    return "unknown"


async def inspect_console(db, vm, proxmox):
    try:
        config = await proxmox.get_vm_config(vm.proxmox_node, vm.vmid)
        status = await proxmox.get_vm_status(vm.proxmox_node, vm.vmid)
    except Exception:
        raise HTTPException(
            502,
            "Cannot inspect this VM. Refresh its status or ask an administrator to check Proxmox connectivity.",
        ) from None
    os_name = guest_os(config)
    running = status.get("status") == "running"
    vnc = running and bool(vm.console_enabled)
    terminal = (
        running
        and os_name == "linux"
        and bool(vm.ssh_enabled)
        and config.get("serial0") == "socket"
    )
    return {
        "_config": config,
        "operating_system": os_name,
        "running": running,
        "vnc": vnc,
        "terminal": terminal,
        "rdp": running and os_name == "windows",
        "terminal_hint": "Log in using your Linux account. The guest must have a serial login service on ttyS0."
        if terminal
        else "Linux terminal requires serial0=socket and a guest login service on ttyS0.",
    }
