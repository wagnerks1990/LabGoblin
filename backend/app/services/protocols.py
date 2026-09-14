PROTOCOL_REGISTRY = {
    "novnc": {"implemented": True, "message": "server-authenticated Proxmox console"},
    "guacamole": {
        "implemented": True,
        "message": "bundled browser VNC, RDP and SSH gateway",
    },
    "rdp": {
        "implemented": True,
        "message": "browser RDP with a verified VM connection profile",
    },
    "spice": {"implemented": False, "message": "spice is disabled"},
    "web_terminal": {
        "implemented": True,
        "message": "browser SSH with a verified VM connection profile",
    },
}


def get_protocol_info(name: str) -> dict:
    return PROTOCOL_REGISTRY.get(
        name, {"implemented": False, "message": "not implemented yet"}
    )
