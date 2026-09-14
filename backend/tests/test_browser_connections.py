import asyncio
import struct
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.guacd_protocol import (
    InstructionParser,
    InstructionReader,
    encode_instruction,
    handshake,
    validate_browser_instruction,
)
from app.services.rfb_auth import authenticate_browser
from app.services.remote_capabilities import guest_os
from app.services.remote_profile import validate_address, validate_identity, vm_macs
from app.core.config import settings


def test_guacamole_fragmented_unicode_and_embedded_delimiters():
    parser = InstructionParser()
    encoded = encode_instruction("name", "VM 👩🏽‍💻,;.é") + encode_instruction(
        "sync", 123
    )
    found = []
    for char in encoded:
        parser.feed(char)
        while (instruction := parser.pop()) is not None:
            found.append(instruction)
    assert found == [["name", "VM 👩🏽‍💻,;.é"], ["sync", "123"]]
    assert parser.buffer == ""


@pytest.mark.parametrize("data", ["99999999.x", "-1.a;", "2.ab!", "x.a;"])
def test_invalid_guacamole_framing(data):
    parser = InstructionParser()
    parser.feed(data)
    with pytest.raises(ValueError):
        parser.pop()


@pytest.mark.parametrize(
    "instruction",
    [
        ["select", "$other-session"],
        ["connect", "evil"],
        ["argv", "0", "text/plain", "hostname"],
        ["clipboard", "0", "text/plain"],
        ["file", "0", "text/plain", "secret"],
        ["size", "99999", "800"],
        ["key", "12", "99"],
    ],
)
def test_browser_cannot_change_destination_join_session_or_create_streams(instruction):
    with pytest.raises(ValueError):
        validate_browser_instruction(instruction)


def test_browser_input_contract():
    for instruction in [
        ["key", "65293", "1"],
        ["mouse", "20", "30", "1"],
        ["size", "1280", "800"],
        ["sync", "123"],
        ["nop"],
    ]:
        assert validate_browser_instruction(instruction)
    assert not validate_browser_instruction(["disconnect"])


class Frames:
    def __init__(self, frames):
        self.frames = list(frames)
        self.sent = []

    async def recv(self):
        if not self.frames:
            raise EOFError()
        return self.frames.pop(0)

    async def send(self, data):
        self.sent.append(data)

    receive_bytes = recv
    send_bytes = send


def test_vencrypt_ticket_is_consumed_on_server_and_never_sent_to_browser():
    server_init = (
        struct.pack("!HH", 1024, 768) + bytes(16) + struct.pack("!I", 4) + b"test"
    )
    upstream = Frames(
        [
            b"RFB 003.",
            b"008\n\1\x13\0\2\0\1" + struct.pack("!I", 256) + bytes(4) + server_init,
        ]
    )
    browser = Frames([b"RFB 003.008\n\1\1"])
    asyncio.run(
        authenticate_browser(
            browser, upstream, {"user": "service@pve", "ticket": "server-only-ticket"}
        )
    )
    assert b"server-only-ticket" in b"".join(upstream.sent)
    assert b"server-only-ticket" not in b"".join(browser.sent)
    assert b"service@pve" not in b"".join(browser.sent)
    assert browser.sent[-1] == server_init
    assert upstream.sent[-1] == b"\1"


def test_noauth_upstream_is_rejected():
    upstream = Frames([b"RFB 003.008\n\1\1"])
    browser = Frames([])
    with pytest.raises(ValueError, match="Unsupported console authentication"):
        asyncio.run(authenticate_browser(browser, upstream, {"ticket": "secret"}))
    assert not browser.sent


def test_failed_rfb_auth_does_not_send_browser_success():
    upstream = Frames(
        [b"RFB 003.008\n\1\x13\0\2\0\1" + struct.pack("!I", 256) + b"\0\0\0\1"]
    )
    browser = Frames([])
    with pytest.raises(ValueError, match="rejected"):
        asyncio.run(
            authenticate_browser(
                browser, upstream, {"user": "svc@pve", "ticket": "secret"}
            )
        )
    assert not browser.sent


def test_os_detection_does_not_trust_names_or_legacy_database_label():
    assert guest_os({"ostype": "win10", "name": "linux"}) == "windows"
    assert guest_os({"ostype": "l26", "name": "windows"}) == "linux"
    assert guest_os({"name": "windows"}) == "unknown"
    assert vm_macs({"net0": "virtio=BC:24:11:AA:BB:CC,bridge=vmbr0", "agent": "1"}) == {
        "bc:24:11:aa:bb:cc"
    }


def test_remote_address_and_identity_policy(monkeypatch):
    monkeypatch.setattr(settings, "guacamole_allowed_networks", "192.0.2.0/24")
    assert validate_address("192.0.2.10") == "192.0.2.10"
    for address in [
        "127.0.0.1",
        "169.254.169.254",
        "::1",
        "10.0.0.1",
        "attacker.example",
        "224.0.0.1",
    ]:
        with pytest.raises(HTTPException):
            validate_address(address)
    validate_identity("rdp", "sha256:" + "a" * 64)
    with pytest.raises(HTTPException):
        validate_identity("rdp", "ignore-cert=true")
    with pytest.raises(HTTPException):
        validate_identity("ssh", "")


def test_guacd_handshake_keeps_connection_parameters_server_side():
    async def scenario():
        reader = asyncio.StreamReader()
        reader.feed_data(
            (
                encode_instruction(
                    "args",
                    "VERSION_1_5_0",
                    "hostname",
                    "port",
                    "security",
                    "ignore-cert",
                    "cert-fingerprints",
                    "username",
                    "password",
                )
                + encode_instruction("ready", "$upstream-session-id")
            ).encode()
        )
        reader.feed_eof()
        output = []

        async def drain():
            pass

        writer = SimpleNamespace(write=output.append, drain=drain)
        await handshake(
            InstructionReader(reader),
            writer,
            "rdp",
            {
                "hostname": "192.0.2.10",
                "port": "3389",
                "security": "nla",
                "ignore-cert": "false",
                "cert-fingerprints": "sha256:" + "a" * 64,
                "username": "guest",
                "password": "private",
            },
            1280,
            800,
        )
        assert b"private" in b"".join(output)
        assert b"nla" in b"".join(output)

    asyncio.run(scenario())


def test_changed_vm_mac_blocks_connection_before_credentials_are_loaded(monkeypatch):
    from app.services.remote_profile import profile_parameters

    profile = SimpleNamespace(
        protocol="rdp",
        enabled=True,
        address="192.0.2.10",
        server_identity="sha256:" + "a" * 64,
        mac_address="bc:24:11:aa:bb:cc",
    )
    db = SimpleNamespace(get=lambda *args: profile)
    vm = SimpleNamespace(id=1, rdp_enabled=True)
    monkeypatch.setattr(settings, "guacamole_allowed_networks", "192.0.2.0/24")
    with pytest.raises(HTTPException, match="network identity changed"):
        profile_parameters(db, vm, {"net0": "virtio=BC:24:11:00:00:00"}, "windows")


def test_student_cannot_approve_a_destination(monkeypatch):
    from app.api.routers.console import _profile_admin

    student = SimpleNamespace(role_rel=SimpleNamespace(name="Student"))
    with pytest.raises(HTTPException) as denied:
        _profile_admin(None, student, 1, SimpleNamespace(id=1))
    assert denied.value.status_code == 403


def test_guacamole_ws_rejects_origin_before_any_upstream_connection(monkeypatch):
    from app.api.routers import console_ws

    class Socket:
        headers = {}
        closed = None

        async def close(self, code, reason):
            self.closed = code

    async def access(_headers):
        return None

    monkeypatch.setattr(
        console_ws, "cloudflare_tunnel_host_allowed", lambda headers: True
    )
    monkeypatch.setattr(console_ws, "require_cloudflare_access", access)
    monkeypatch.setattr(console_ws, "websocket_origin_allowed", lambda socket: False)
    socket = Socket()
    asyncio.run(console_ws.guacamole_ws(1, "rdp", socket, None))
    assert socket.closed == 1008
