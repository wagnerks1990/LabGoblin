import ipaddress
import json
import re

from fastapi import HTTPException
from app.core.config import settings
from app.models.models import VMRemoteProfile
from app.services.secret_crypto import decrypt_secret


def validate_address(address):
    try:
        ip = ipaddress.ip_address(address)
        networks = [
            ipaddress.ip_network(item.strip())
            for item in settings.guacamole_allowed_networks.split(",")
            if item.strip()
        ]
        if (
            ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_unspecified
            or (networks and not any(ip in network for network in networks))
        ):
            raise ValueError()
    except ValueError:
        raise HTTPException(
            422,
            "Use a reserved unicast VM IP permitted by the deployment network policy.",
        ) from None
    return str(ip)


def vm_macs(config):
    result = set()
    for key, value in config.items():
        if re.fullmatch(r"net\d+", key):
            match = re.search(
                r"(?:^|,)[a-zA-Z0-9_-]+=([0-9a-fA-F:]{17})(?:,|$)", str(value)
            )
            if match:
                result.add(match[1].lower())
    return result


def validate_identity(protocol, identity):
    if protocol == "rdp":
        if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", identity):
            raise HTTPException(
                422,
                "Provide the verified RDP certificate fingerprint as sha256: followed by 64 hexadecimal digits.",
            )
    elif not re.fullmatch(
        r"[^\s]+ (?:ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp(?:256|384|521)) [A-Za-z0-9+/=]+",
        identity,
    ):
        raise HTTPException(
            422, "Provide one verified OpenSSH known_hosts entry without a comment."
        )


def profile_parameters(db, vm, config, os_name):
    profile = db.get(VMRemoteProfile, vm.id)
    expected = "rdp" if os_name == "windows" else "ssh" if os_name == "linux" else None
    if not profile or not profile.enabled or profile.protocol != expected:
        raise HTTPException(
            409, "An administrator must configure remote access for this VM."
        )
    if profile.protocol == "rdp" and not vm.rdp_enabled:
        raise HTTPException(403, "RDP is disabled for this VM.")
    validate_address(profile.address)
    validate_identity(profile.protocol, profile.server_identity)
    if profile.mac_address not in vm_macs(config):
        raise HTTPException(
            409,
            "VM network identity changed. Ask an administrator to review the connection profile.",
        )
    credentials = json.loads(decrypt_secret(profile.encrypted_credentials))
    parameters = {
        "hostname": profile.address,
        "port": str(profile.port),
        "username": credentials["username"],
        "password": credentials["password"],
        "disable-copy": "true",
        "disable-paste": "true",
        "enable-sftp": "false",
    }
    if profile.protocol == "rdp":
        parameters.update(
            {
                "domain": credentials.get("domain", ""),
                "security": "nla",
                "ignore-cert": "false",
                "cert-tofu": "false",
                "cert-fingerprints": profile.server_identity,
                "enable-drive": "false",
                "enable-printing": "false",
                "disable-audio": "true",
                "resize-method": "display-update",
            }
        )
    else:
        parameters.update(
            {
                "host-key": profile.server_identity,
                "server-alive-interval": "15",
                "font-name": "monospace",
                "font-size": "12",
                "color-scheme": "green-black",
            }
        )
    return profile, parameters
