"""Bounded probes of administrator-approved destinations; never arbitrary guest claims."""

import asyncio
import hashlib
import ssl
import struct

import asyncssh


async def inspect_rdp(address, port):
    writer = None
    try:
        async with asyncio.timeout(6):
            reader, writer = await asyncio.open_connection(address, port)
            # TPKT / X.224 connection request: request TLS + NLA + extended NLA.
            writer.write(bytes.fromhex("030000130ee00000000000010008000b000000"))
            await writer.drain()
            header = await reader.readexactly(4)
            length = struct.unpack("!H", header[2:4])[0]
            if header[:2] != b"\3\0" or not 11 <= length <= 256:
                raise ValueError("Invalid RDP negotiation")
            response = await reader.readexactly(length - 4)
            if response[-8] != 2 or response[-4:] not in (b"\2\0\0\0", b"\10\0\0\0"):
                raise ValueError("RDP server does not offer NLA")
            # Discovery only: retrieve the public certificate without credentials.
            # Subsequent guacd login requires the GUI-approved SHA-256 pin.
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            await writer.start_tls(context)
            certificate = writer.get_extra_info("ssl_object").getpeercert(
                binary_form=True
            )
            if not certificate:
                raise ValueError("RDP certificate unavailable")
            return "sha256:" + hashlib.sha256(certificate).hexdigest()
    finally:
        if writer:
            writer.close()
            try:
                await writer.wait_closed()
            except (OSError, ssl.SSLError):
                pass


async def inspect_ssh(address, port):
    async with asyncio.timeout(6):
        key = await asyncssh.get_server_host_key(address, port=port)
        if key is None:
            raise ValueError("SSH host key unavailable")
        return f"{address if port == 22 else f'[{address}]:{port}'} {key.export_public_key().decode().strip()}"


async def check_profile(profile):
    try:
        identity = await (
            inspect_rdp(profile.address, profile.port)
            if profile.protocol == "rdp"
            else inspect_ssh(profile.address, profile.port)
        )
        if identity != profile.server_identity:
            return (
                False,
                "The guest server identity changed. An administrator must review it before connecting.",
            )
        return True, "Guest service is reachable and its server identity matches."
    except Exception:
        return (
            False,
            "The guest service is not responding. Check that RDP or SSH is enabled and allowed through the guest firewall.",
        )


async def check_proxmox_vnc(proxmox, vm):
    from app.services.guacamole_console import vnc_bridge

    # The adapter performs a complete upstream ticket/RFB authentication before
    # opening its temporary listener. No guest TCP address is used.
    try:
        async with asyncio.timeout(25):
            async with vnc_bridge(proxmox, vm):
                return True
    except Exception:
        return False
