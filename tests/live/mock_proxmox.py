#!/usr/bin/env python3
"""Small stateful Proxmox API simulator used only by the disposable live test."""

from __future__ import annotations

import argparse
import json
import ssl
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


NODE = "pve-live-test"
TEMPLATE_VMID = 9000
_lock = threading.Lock()
_vms: dict[int, dict] = {
    TEMPLATE_VMID: {
        "vmid": TEMPLATE_VMID,
        "name": "classroom-template",
        "status": "stopped",
        "template": 1,
        "node": NODE,
    }
}
_tasks: dict[str, dict] = {}
_task_sequence = 0


def _new_task(action: str, vmid: int) -> str:
    global _task_sequence
    _task_sequence += 1
    upid = f"UPID:{NODE}:{_task_sequence:08X}:{action}:{vmid}:root@pam:"
    _tasks[upid] = {"status": "stopped", "exitstatus": "OK"}
    return upid


class Handler(BaseHTTPRequestHandler):
    server_version = "ProxmoxLiveTest/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"mock-proxmox: {fmt % args}", flush=True)

    def _json(self, status: int, data: object) -> None:
        body = json.dumps({"data": data}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _path(self) -> list[str]:
        path = urllib.parse.urlsplit(self.path).path
        prefix = "/api2/json/"
        if not path.startswith(prefix):
            return []
        return [
            urllib.parse.unquote(part)
            for part in path[len(prefix) :].split("/")
            if part
        ]

    def _form(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length", "0"))
        values = urllib.parse.parse_qs(self.rfile.read(length).decode())
        return {key: value[-1] for key, value in values.items()}

    def do_GET(self) -> None:  # noqa: N802
        parts = self._path()
        with _lock:
            if parts == ["version"]:
                return self._json(200, {"version": "8.2", "release": "live-test"})
            if parts == ["cluster", "resources"]:
                rows = [{"type": "node", "node": NODE, "status": "online"}]
                rows.extend({"type": "qemu", **vm} for vm in _vms.values())
                query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                if query.get("type") == ["vm"]:
                    rows = [row for row in rows if row["type"] in {"qemu", "lxc"}]
                return self._json(200, rows)
            if parts == ["nodes"]:
                return self._json(200, [{"node": NODE, "status": "online"}])
            if parts == ["nodes", NODE, "qemu"]:
                return self._json(200, list(_vms.values()))
            if parts == ["nodes", NODE, "storage"]:
                return self._json(
                    200,
                    [
                        {
                            "storage": "local",
                            "type": "dir",
                            "content": "iso,vztmpl",
                            "enabled": 1,
                            "active": 1,
                        }
                    ],
                )
            if parts == ["nodes", NODE, "storage", "local", "content"]:
                return self._json(200, [])
            if parts == ["nodes", NODE, "network"]:
                return self._json(
                    200,
                    [{"iface": "vmbr0", "type": "bridge", "active": 1, "autostart": 1}],
                )
            if (
                len(parts) == 5
                and parts[:2] == ["nodes", NODE]
                and parts[2] == "tasks"
                and parts[-1] == "status"
            ):
                task = _tasks.get(parts[3])
                return self._json(200, task) if task else self._json(404, None)
            if (
                len(parts) == 6
                and parts[:3] == ["nodes", NODE, "qemu"]
                and parts[4:] == ["status", "current"]
            ):
                vm = _vms.get(int(parts[3]))
                return self._json(200, vm) if vm else self._json(404, None)
        self._json(404, None)

    def do_POST(self) -> None:  # noqa: N802
        parts = self._path()
        form = self._form()
        with _lock:
            if (
                len(parts) == 5
                and parts[:3] == ["nodes", NODE, "qemu"]
                and parts[-1] == "clone"
            ):
                source = _vms.get(int(parts[3]))
                if not source or not source.get("template"):
                    return self._json(404, None)
                vmid = int(form["newid"])
                if vmid in _vms:
                    return self._json(409, None)
                _vms[vmid] = {
                    "vmid": vmid,
                    "name": form.get("name", f"vm-{vmid}"),
                    "status": "stopped",
                    "template": 0,
                    "node": NODE,
                }
                return self._json(200, _new_task("clone", vmid))
            if (
                len(parts) == 6
                and parts[:3] == ["nodes", NODE, "qemu"]
                and parts[4] == "status"
            ):
                vmid = int(parts[3])
                vm = _vms.get(vmid)
                action = parts[5]
                if not vm:
                    return self._json(404, None)
                if action in {"start", "reboot"}:
                    vm["status"] = "running"
                elif action in {"stop", "shutdown"}:
                    vm["status"] = "stopped"
                else:
                    return self._json(400, None)
                return self._json(200, _new_task(action, vmid))
        self._json(404, None)

    def do_DELETE(self) -> None:  # noqa: N802
        parts = self._path()
        with _lock:
            if len(parts) == 4 and parts[:3] == ["nodes", NODE, "qemu"]:
                vmid = int(parts[3])
                if vmid == TEMPLATE_VMID or vmid not in _vms:
                    return self._json(404, None)
                del _vms[vmid]
                return self._json(200, _new_task("delete", vmid))
        self._json(404, None)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18006)
    parser.add_argument("--certfile")
    parser.add_argument("--keyfile")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    if args.certfile or args.keyfile:
        if not args.certfile or not args.keyfile:
            parser.error("--certfile and --keyfile must be provided together")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(args.certfile, args.keyfile)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
