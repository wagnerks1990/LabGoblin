from fastapi import HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
import asyncio
import asyncssh
import ssl
from urllib.parse import urlencode
import websockets

from app.core.config import settings
from app.api.deps import get_user_from_token
from app.models.models import User, StudentVM, AuditLog
from app.services.console_access import get_console_vm_for_user
from app.services.organization_access import resolve_organization_context
from app.services.proxmox import ProxmoxClient
from app.db.tx import safe_commit
from app.services.rfb_auth import authenticate_browser
from app.services.remote_capabilities import inspect_console
from app.services.session_service import SessionService


class ConsoleWsService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def discover_vm_ip(interfaces):
        for iface in interfaces:
            for addr in iface.get("ip-addresses", []):
                if addr.get("ip-address-type") == "ipv4" and not addr.get(
                    "ip-address", ""
                ).startswith("127."):
                    return addr.get("ip-address")
        return None

    async def _watch_session_access(
        self,
        websocket: WebSocket,
        service: SessionService,
        session_id: int,
        user: User,
        vm: StudentVM,
        operation: str,
        auth_token: str,
        organization_id: int,
    ) -> None:
        while True:
            await asyncio.sleep(30)
            self.db.expire_all()
            try:
                current_user = get_user_from_token(auth_token, self.db)
                if getattr(current_user, "force_password_change", False):
                    raise HTTPException(
                        status_code=403, detail="Password change required"
                    )
                organization = resolve_organization_context(
                    self.db, current_user, organization_id
                )
                current_vm = get_console_vm_for_user(
                    self.db,
                    user=current_user,
                    vm_id=vm.id,
                    organization=organization,
                    operation=operation,
                )
                flag = {
                    "console": "console_enabled",
                    "terminal": "ssh_enabled",
                    "rdp": "rdp_enabled",
                }.get(operation)
                if flag and not getattr(current_vm, flag, False):
                    raise HTTPException(403, "Connection disabled")
            except HTTPException:
                await websocket.close(code=1008, reason="Console access revoked")
                return
            if not service.heartbeat(session_id):
                await websocket.close(code=1008, reason="Session expired")
                return

    async def ssh_ws(
        self,
        websocket: WebSocket,
        user: User,
        vm: StudentVM,
        *,
        auth_token: str,
        organization_id: int,
    ):
        proxmox = ProxmoxClient(cluster_id=vm.proxmox_cluster_id)
        host = vm.assigned_ip
        if not host:
            try:
                interfaces = await proxmox.get_guest_network(vm.proxmox_node, vm.vmid)
                host = self.discover_vm_ip(interfaces)
                if host:
                    vm.assigned_ip = host
                    safe_commit(self.db)
            except Exception:
                pass
        if not host:
            await websocket.accept()
            await websocket.send_text(
                "ERROR: No VM IP address found. Install/enable QEMU guest agent or manually set assigned_ip."
            )
            await websocket.close(code=1000)
            return

        username = (
            vm.ssh_username
            or settings.lab_vm_ssh_username
            or vm.default_username
            or "student"
        )
        port = vm.ssh_port or 22
        if (
            not settings.lab_vm_ssh_private_key_path
            or not settings.lab_vm_ssh_known_hosts
        ):
            await websocket.accept()
            await websocket.send_text(
                "ERROR: SSH requires LAB_VM_SSH_PRIVATE_KEY_PATH and LAB_VM_SSH_KNOWN_HOSTS."
            )
            await websocket.close(code=1000)
            return

        await websocket.accept()
        self.db.add(
            AuditLog(
                organization_id=vm.organization_id,
                actor_id=user.id,
                action="ssh_ws_launch",
                target_type="student_vm",
                target_id=str(vm.vmid),
            )
        )
        safe_commit(self.db)
        svc = SessionService(self.db)
        launch = svc.create_launch(user, vm, "SSH_WS", "success", host)
        session = svc.create_launching_session(
            user, vm, "SSH_WS", connection_launch_id=launch.id
        )
        safe_commit(self.db)
        svc.mark_active(session.id)
        svc.heartbeat(session.id)

        try:
            async with asyncssh.connect(
                host,
                port=port,
                username=username,
                client_keys=[settings.lab_vm_ssh_private_key_path],
                known_hosts=settings.lab_vm_ssh_known_hosts,
            ) as conn:
                process = await conn.create_process(
                    term_type="xterm", term_size=(24, 120)
                )

                async def to_ws():
                    while not process.stdout.at_eof():
                        chunk = await process.stdout.read(1024)
                        if not chunk:
                            break
                        await websocket.send_text(chunk)

                async def from_ws():
                    while True:
                        process.stdin.write(await websocket.receive_text())

                t1 = asyncio.create_task(to_ws())
                t2 = asyncio.create_task(from_ws())
                watchdog = asyncio.create_task(
                    self._watch_session_access(
                        websocket,
                        svc,
                        session.id,
                        user,
                        vm,
                        "terminal",
                        auth_token,
                        organization_id,
                    )
                )
                _done, pending = await asyncio.wait(
                    {t1, t2, watchdog}, return_when=asyncio.FIRST_COMPLETED
                )
                for t in pending:
                    t.cancel()
        except WebSocketDisconnect:
            svc.mark_disconnected(session.id)
            return
        except Exception:
            try:
                svc.mark_failed(session.id, "SSH connection failed")
            except Exception:
                pass
            await websocket.send_text("ERROR: SSH connection failed")
            await websocket.close(code=1011)
        finally:
            svc.mark_disconnected(session.id)

    async def _run_pumps(self, *coroutines):
        tasks = {asyncio.create_task(coroutine) for coroutine in coroutines}
        try:
            done, _pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                task.result()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def novnc_ws(self, websocket, user, vm, *, auth_token, organization_id):
        await self._proxmox_ws(websocket, user, vm, auth_token, organization_id, False)

    async def serial_ws(self, websocket, user, vm, *, auth_token, organization_id):
        await self._proxmox_ws(websocket, user, vm, auth_token, organization_id, True)

    async def _proxmox_ws(
        self, websocket, user, vm, auth_token, organization_id, serial
    ):
        import json

        service = SessionService(self.db)
        session = None
        failed = False
        operation = "terminal" if serial else "console"
        protocol = "SERIAL_WS" if serial else "NOVNC_WS"
        await websocket.accept()
        try:
            proxmox = ProxmoxClient(cluster_id=vm.proxmox_cluster_id)
            capability = await inspect_console(self.db, vm, proxmox)
            if not capability["terminal" if serial else "vnc"]:
                await websocket.close(
                    code=1008,
                    reason="Connection unavailable; check VM connection options",
                )
                return
            ticket_data = await (
                proxmox.get_terminal_ticket(vm.proxmox_node, vm.vmid)
                if serial
                else proxmox.get_novnc_ticket(vm.proxmox_node, vm.vmid)
            )
            if not ticket_data.get("port") or not ticket_data.get("ticket"):
                raise ValueError("Console ticket unavailable")
            query = urlencode(
                {"port": ticket_data["port"], "vncticket": ticket_data["ticket"]}
            )
            base = proxmox.base_url.rstrip("/")
            ws_url = base.replace("https://", "wss://", 1).replace(
                "http://", "ws://", 1
            )
            ws_url += f"/nodes/{vm.proxmox_node}/qemu/{vm.vmid}/vncwebsocket?{query}"
            context = None
            if ws_url.startswith("wss://"):
                context = ssl.create_default_context()
                if not proxmox.verify_ssl:
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
            self.db.add(
                AuditLog(
                    organization_id=vm.organization_id,
                    actor_id=user.id,
                    action=f"{operation}_ws_launch",
                    target_type="student_vm",
                    target_id=str(vm.id),
                )
            )
            launch = service.create_launch(user, vm, protocol, "launching")
            session = service.create_launching_session(
                user, vm, protocol, connection_launch_id=launch.id
            )
            safe_commit(self.db)
            async with websockets.connect(
                ws_url,
                ssl=context,
                additional_headers=proxmox.headers,
                open_timeout=15,
                max_size=4194304,
                max_queue=16,
            ) as upstream:
                if serial:
                    username, ticket = (
                        ticket_data.get("user", ""),
                        ticket_data["ticket"],
                    )
                    if not username or any(c in username + ticket for c in "\r\n"):
                        raise ValueError("Invalid terminal ticket")
                    await upstream.send(f"{username}:{ticket}\n")
                    async with asyncio.timeout(15):
                        answer = await upstream.recv()
                    if answer not in ("OK", b"OK"):
                        raise ValueError("Terminal authentication rejected")
                    await websocket.send_json({"type": "ready"})
                else:
                    await authenticate_browser(websocket, upstream, ticket_data)
                launch.status = "success"
                service.mark_active(session.id)
                service.heartbeat(session.id)

                async def from_browser():
                    while True:
                        if serial:
                            message = await websocket.receive_text()
                            if len(message) > 65536:
                                raise ValueError("Terminal input too large")
                            event = json.loads(message)
                            if event.get("type") == "input" and isinstance(
                                event.get("data"), str
                            ):
                                data = event["data"]
                                await upstream.send(f"0:{len(data.encode())}:{data}")
                            elif event.get("type") == "resize":
                                cols, rows = int(event["cols"]), int(event["rows"])
                                if not (2 <= cols <= 500 and 2 <= rows <= 200):
                                    raise ValueError("Invalid terminal dimensions")
                                await upstream.send(f"1:{cols}:{rows}:")
                            else:
                                raise ValueError("Invalid terminal input")
                        else:
                            await upstream.send(await websocket.receive_bytes())

                async def to_browser():
                    import codecs

                    decoder = codecs.getincrementaldecoder("utf-8")("replace")
                    async for data in upstream:
                        if serial:
                            output = (
                                decoder.decode(data)
                                if isinstance(data, bytes)
                                else data
                            )
                            await websocket.send_json(
                                {"type": "output", "data": output}
                            )
                        elif isinstance(data, bytes):
                            await websocket.send_bytes(data)
                        else:
                            raise ValueError("Invalid graphical console data")

                async def keepalive():
                    while True:
                        await asyncio.sleep(20)
                        if serial:
                            await upstream.send("2")

                await self._run_pumps(
                    from_browser(),
                    to_browser(),
                    keepalive(),
                    self._watch_session_access(
                        websocket,
                        service,
                        session.id,
                        user,
                        vm,
                        operation,
                        auth_token,
                        organization_id,
                    ),
                )
        except (WebSocketDisconnect, websockets.exceptions.ConnectionClosedOK):
            pass
        except Exception:
            failed = True
            if session:
                service.mark_failed(session.id, "Remote console connection failed")
            # Never return upstream exceptions: their request URLs contain tickets.
        finally:
            if session:
                if not service.mark_disconnected(session.id):
                    service.mark_failed(
                        session.id,
                        "Connection ended before the remote session became active",
                    )
            try:
                await websocket.close(
                    code=1011 if failed else 1000,
                    reason="Connection failed; check connection prerequisites"
                    if failed
                    else "Session closed",
                )
            except (RuntimeError, WebSocketDisconnect):
                pass
