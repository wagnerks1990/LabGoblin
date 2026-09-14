"""Terminate Proxmox RFB authentication without releasing its ticket to noVNC.

Only the authentication prefix is translated. Desktop traffic remains binary.
VeNCrypt Plain is protected by the upstream TLS policy; VNCAuth supports older
Proxmox configurations. No unauthenticated upstream security type is accepted.
"""

import asyncio
import struct

from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES
from cryptography.hazmat.primitives.ciphers import Cipher, modes


class ByteStream:
    def __init__(self, receive):
        self.receive = receive
        self.buffer = bytearray()

    async def read(self, count):
        while len(self.buffer) < count:
            data = await self.receive()
            if not isinstance(data, bytes) or not data:
                raise ValueError("Invalid console handshake")
            self.buffer.extend(data)
            if len(self.buffer) > 1048576:
                raise ValueError("Console handshake too large")
        data = bytes(self.buffer[:count])
        del self.buffer[:count]
        return data


def vnc_response(ticket, challenge):
    key = ticket.encode("latin-1")[:8].ljust(8, b"\0")
    key = bytes(int(f"{byte:08b}"[::-1], 2) for byte in key)
    # VNC's legacy DES challenge requires this algorithm, never used for storage.
    cipher = Cipher(TripleDES(key * 3), modes.ECB()).encryptor()  # nosec B305
    return cipher.update(challenge) + cipher.finalize()


async def authenticate_upstream(upstream, ticket_data):
    stream = ByteStream(upstream.recv)
    version = await stream.read(12)
    if version != b"RFB 003.008\n":
        raise ValueError("Unsupported console protocol version")
    await upstream.send(version)
    count = (await stream.read(1))[0]
    security = await stream.read(count)
    ticket = ticket_data["ticket"]
    if 19 in security:
        await upstream.send(b"\x13")
        if await stream.read(2) != b"\0\2":
            raise ValueError("Unsupported VeNCrypt version")
        await upstream.send(b"\0\2")
        if await stream.read(1) != b"\0":
            raise ValueError("Console authentication rejected")
        count = (await stream.read(1))[0]
        subtypes = struct.unpack(f"!{count}I", await stream.read(count * 4))
        if 256 not in subtypes or not ticket_data.get("user"):
            raise ValueError("Unsupported console authentication")
        await upstream.send(struct.pack("!I", 256))
        username, password = ticket_data["user"].encode(), ticket.encode()
        await upstream.send(
            struct.pack("!II", len(username), len(password)) + username + password
        )
    elif 2 in security:
        await upstream.send(b"\2")
        await upstream.send(vnc_response(ticket, await stream.read(16)))
    else:
        raise ValueError("Unsupported console authentication")
    if await stream.read(4) != b"\0\0\0\0":
        raise ValueError("Console authentication rejected")
    return stream


async def authenticate_browser(websocket, upstream, ticket_data):
    async with asyncio.timeout(20):
        stream = await authenticate_upstream(upstream, ticket_data)
        browser = ByteStream(websocket.receive_bytes)
        await websocket.send_bytes(b"RFB 003.008\n")
        if await browser.read(12) != b"RFB 003.008\n":
            raise ValueError("Unsupported browser console version")
        # Browser transport is already protected by the live session and origin gate.
        await websocket.send_bytes(b"\1\1")
        if await browser.read(1) != b"\1":
            raise ValueError("Invalid browser console authentication")
        await websocket.send_bytes(b"\0\0\0\0")
        await upstream.send(await browser.read(1))  # ClientInit
        # Wait for ServerInit before declaring the desktop connected.
        header = await stream.read(24)
        name_length = struct.unpack("!I", header[20:24])[0]
        if name_length > 65536:
            raise ValueError("Invalid desktop name")
        await websocket.send_bytes(header + await stream.read(name_length))
        if stream.buffer:
            await websocket.send_bytes(bytes(stream.buffer))
        if browser.buffer:
            await upstream.send(bytes(browser.buffer))
