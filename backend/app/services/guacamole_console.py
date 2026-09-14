"""LabGoblin-authorized Guacamole tunnels. All destinations are server selected."""

import asyncio
from contextlib import asynccontextmanager
import hmac
import secrets
import ssl
import uuid
from urllib.parse import urlencode

import websockets
from fastapi import HTTPException, WebSocketDisconnect

from app.core.config import settings
from app.db.tx import safe_commit
from app.models.models import AuditLog, VMRemoteProfile, VMSession
from app.services.guacd_protocol import (
    InstructionParser,
    InstructionReader,
    encode_instruction,
    handshake,
    validate_browser_instruction,
)
from app.services.proxmox import ProxmoxClient
from app.services.remote_capabilities import guest_os
from app.services.remote_profile import profile_parameters
from app.services.template_credentials import template_connection_revision
from app.services.rfb_auth import authenticate_upstream, vnc_response
from app.services.session_service import SessionService


@asynccontextmanager
async def vnc_bridge(proxmox, vm):
    """Single-use, password-protected TCP RFB adapter on an unpublished API port.

    guacd owns the TCP side; Proxmox ticket authentication terminates here. This
    avoids installing guest VNC servers or exposing PVE tokens/tickets to guacd.
    """
    ticket = await proxmox.get_novnc_ticket(vm.proxmox_node, vm.vmid)
    query = urlencode({"port": ticket["port"], "vncticket": ticket["ticket"]})
    url = (
        proxmox.base_url.rstrip("/")
        .replace("https://", "wss://", 1)
        .replace("http://", "ws://", 1)
    )
    url += f"/nodes/{vm.proxmox_node}/qemu/{vm.vmid}/vncwebsocket?{query}"
    context = None
    if url.startswith("wss://"):
        context = ssl.create_default_context()
        if not proxmox.verify_ssl:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
    async with websockets.connect(
        url,
        ssl=context,
        additional_headers=proxmox.headers,
        open_timeout=15,
        max_size=4194304,
        max_queue=16,
    ) as upstream:
        async with asyncio.timeout(20):
            stream = await authenticate_upstream(upstream, ticket)
        password = secrets.token_urlsafe(
            6
        )  # VNC authentication consumes eight characters.
        used = False
        handlers = set()
        completion = asyncio.get_running_loop().create_future()

        async def accept(reader, writer):
            nonlocal used
            task = asyncio.current_task()
            handlers.add(task)
            authenticated = False
            try:
                async with asyncio.timeout(10):
                    if used:
                        return
                    writer.write(b"RFB 003.008\n")
                    await writer.drain()
                    if await reader.readexactly(12) != b"RFB 003.008\n":
                        return
                    writer.write(b"\1\2")
                    await writer.drain()
                    if await reader.readexactly(1) != b"\2":
                        return
                    challenge = secrets.token_bytes(16)
                    writer.write(challenge)
                    await writer.drain()
                    response = await reader.readexactly(16)
                    if (
                        not hmac.compare_digest(
                            response, vnc_response(password, challenge)
                        )
                        or used
                    ):
                        return
                    used = authenticated = True
                    writer.write(b"\0\0\0\0")
                    await writer.drain()
                    await upstream.send(await reader.readexactly(1))
                if stream.buffer:
                    writer.write(bytes(stream.buffer))
                    await writer.drain()

                async def tcp_to_pve():
                    while data := await reader.read(65536):
                        await upstream.send(data)

                async def pve_to_tcp():
                    async for data in upstream:
                        if not isinstance(data, bytes):
                            raise ValueError("Unexpected graphical console frame")
                        writer.write(data)
                        await writer.drain()

                await pump(tcp_to_pve(), pve_to_tcp())
            except (Exception, asyncio.CancelledError):
                # Do not log exception URLs or RFB handshake contents.
                pass
            finally:
                writer.close()
                await writer.wait_closed()
                handlers.discard(task)
                if authenticated and not completion.done():
                    completion.set_result(None)

        server = await asyncio.start_server(accept, "0.0.0.0", 0)  # nosec B104
        try:
            port = server.sockets[0].getsockname()[1]
            yield (
                {
                    "hostname": settings.guacd_bridge_host,
                    "port": str(port),
                    "password": password,
                    "disable-copy": "true",
                    "disable-paste": "true",
                    "enable-sftp": "false",
                },
                completion,
            )
        finally:
            server.close()
            await server.wait_closed()
            for task in tuple(handlers):
                task.cancel()
            await asyncio.gather(*tuple(handlers), return_exceptions=True)


async def pump(*coroutines):
    tasks = {asyncio.create_task(coroutine) for coroutine in coroutines}
    try:
        done, _pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


class GuacamoleConsole:
    def __init__(self, db):
        self.db = db

    async def connect(self, websocket, user, vm, protocol, auth_token, organization_id):
        from app.services.console_ws_service import ConsoleWsService
        from contextlib import AsyncExitStack

        await websocket.accept(subprotocol="guacamole")
        svc = SessionService(self.db)
        session = None
        writer = None
        failed = False
        try:
            count = (
                self.db.query(VMSession)
                .filter(
                    VMSession.user_id == user.id,
                    VMSession.state.in_(["launching", "active"]),
                )
                .count()
            )
            if count >= 5:
                raise HTTPException(
                    429, "Close another remote session before connecting."
                )
            proxmox = ProxmoxClient(cluster_id=vm.proxmox_cluster_id)
            async with asyncio.timeout(30):
                config = await proxmox.get_vm_config(vm.proxmox_node, vm.vmid)
                status = await proxmox.get_vm_status(vm.proxmox_node, vm.vmid)
            os_name = guest_os(config)
            if status.get("status") != "running":
                raise HTTPException(409, "Start the VM before connecting.")
            if protocol == "vnc" and not vm.console_enabled:
                raise HTTPException(403, "VNC is disabled for this VM.")
            if protocol not in {"vnc", "rdp", "ssh"}:
                raise HTTPException(403, "Unsupported connection method.")
            operation = {"vnc": "console", "rdp": "rdp", "ssh": "terminal"}[protocol]
            profile = None
            async with AsyncExitStack() as stack:
                if protocol == "vnc":
                    parameters, _completion = await stack.enter_async_context(
                        vnc_bridge(proxmox, vm)
                    )
                else:
                    profile, parameters = profile_parameters(
                        self.db, vm, config, os_name
                    )
                    if profile.protocol != protocol or (
                        protocol == "ssh" and not vm.ssh_enabled
                    ):
                        raise HTTPException(
                            403, "Connection method is disabled for this VM."
                        )
                revision = profile.revision if profile else None
                credential_revision = (
                    template_connection_revision(self.db, vm, profile)
                    if profile
                    else None
                )
                launch = svc.create_launch(
                    user, vm, f"GUAC_{protocol.upper()}", "launching"
                )
                session = svc.create_launching_session(
                    user, vm, f"GUAC_{protocol.upper()}", connection_launch_id=launch.id
                )
                self.db.add(
                    AuditLog(
                        organization_id=vm.organization_id,
                        actor_id=user.id,
                        action="console_launch",
                        target_type="student_vm",
                        target_id=str(vm.id),
                        message=f"Browser {protocol.upper()} connection",
                    )
                )
                safe_commit(self.db)
                async with asyncio.timeout(30):
                    reader, writer = await asyncio.open_connection(
                        settings.guacd_host, settings.guacd_port
                    )
                    guac_reader = InstructionReader(reader)
                    width = max(
                        200, min(4096, int(websocket.query_params.get("width", "1280")))
                    )
                    height = max(
                        200, min(4096, int(websocket.query_params.get("height", "800")))
                    )
                    await handshake(
                        guac_reader, writer, protocol, parameters, width, height
                    )
                # Local tunnel identifier, never the joinable guacd connection id.
                await websocket.send_text(encode_instruction("", str(uuid.uuid4())))

                async def to_browser():
                    active = False
                    while True:
                        async with asyncio.timeout(60 if not active else 120):
                            instruction = await guac_reader.read()
                        if instruction[0] in {"error", "required"}:
                            raise ValueError(
                                "Guest authentication or connection failed"
                            )
                        if instruction[0] == "sync" and not active:
                            active = True
                            launch.status = "success"
                            svc.mark_active(session.id)
                            svc.heartbeat(session.id)
                        # Never expose join IDs, server debug output, names or credential prompts.
                        if instruction[0] not in {
                            "ready",
                            "args",
                            "name",
                            "msg",
                            "log",
                        }:
                            await websocket.send_text(encode_instruction(*instruction))

                async def from_browser():
                    parser = InstructionParser(limit=65536)
                    while True:
                        data = await websocket.receive_text()
                        parser.feed(data)
                        while (instruction := parser.pop()) is not None:
                            if (
                                len(instruction) == 3
                                and instruction[:2] == ["", "ping"]
                                and instruction[2].isdigit()
                            ):
                                await websocket.send_text(
                                    encode_instruction(*instruction)
                                )
                                continue
                            if not validate_browser_instruction(instruction):
                                return
                            writer.write(encode_instruction(*instruction).encode())
                            await writer.drain()

                async def profile_watch():
                    while True:
                        await asyncio.sleep(15)
                        if profile:
                            self.db.expire_all()
                            current = self.db.get(VMRemoteProfile, vm.id)
                            if (
                                not current
                                or not current.enabled
                                or current.revision != revision
                                or template_connection_revision(self.db, vm, current)
                                != credential_revision
                            ):
                                await websocket.close(
                                    code=1008, reason="Connection settings changed"
                                )
                                return

                await pump(
                    to_browser(),
                    from_browser(),
                    profile_watch(),
                    ConsoleWsService(self.db)._watch_session_access(
                        websocket,
                        svc,
                        session.id,
                        user,
                        vm,
                        operation,
                        auth_token,
                        organization_id,
                    ),
                )
        except WebSocketDisconnect:
            pass
        except Exception:
            failed = True
            if session:
                svc.mark_failed(
                    session.id,
                    "Browser connection failed; verify guest service, profile and server identity",
                )
            try:
                await websocket.send_text(
                    encode_instruction(
                        "error",
                        "Connection failed. Check VM connection settings and guest service.",
                        "512",
                    )
                )
            except (RuntimeError, WebSocketDisconnect):
                pass
        finally:
            if writer:
                writer.close()
                try:
                    async with asyncio.timeout(3):
                        await writer.wait_closed()
                except (OSError, TimeoutError):
                    pass
            if session:
                if not svc.mark_disconnected(session.id):
                    svc.mark_failed(
                        session.id,
                        "Connection ended before the remote session became active",
                    )
            try:
                await websocket.close(code=1011 if failed else 1000)
            except (RuntimeError, WebSocketDisconnect):
                pass
