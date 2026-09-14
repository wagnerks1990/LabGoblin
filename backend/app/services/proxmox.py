import asyncio
import re
import httpx
from app.core.config import settings
from app.architecture.async_retry import async_retry_with_backoff
from app.db.session import SessionLocal
from app.models.models import ProxmoxCluster
from app.services.secret_crypto import decrypt_secret
from app.services.proxmox_url import canonicalize_proxmox_api_url


class ProxmoxClient:
    def __init__(self, cluster_id: int | None = None):
        active = self._load_cluster(cluster_id)
        if active:
            self.base_url = active.api_url.rstrip("/")
            secret = (
                decrypt_secret(active.encrypted_token_secret)
                if active.encrypted_token_secret
                else ""
            )
            self.headers = {
                "Authorization": f"PVEAPIToken={active.token_user}!{active.token_id}={secret}"
            }
            self.verify_ssl = bool(active.verify_ssl)
            self.config_source = (
                "database_bound_cluster" if cluster_id else "database_active_cluster"
            )
        else:
            self.base_url = settings.proxmox_base_url.rstrip("/")
            self.headers = {
                "Authorization": f"PVEAPIToken={settings.proxmox_token_id}={settings.proxmox_token_secret}"
            }
            self.verify_ssl = settings.proxmox_verify_ssl
            self.config_source = "env_fallback"
        if not self.base_url or not self.headers.get("Authorization"):
            raise RuntimeError(
                "Proxmox is not configured. Complete Admin > Proxmox Setup."
            )
        try:
            self.base_url = canonicalize_proxmox_api_url(
                self.base_url, verify_ssl=self.verify_ssl
            )
        except ValueError as exc:
            raise RuntimeError(f"Unsafe Proxmox API configuration: {exc}") from exc

    def _load_cluster(self, cluster_id: int | None):
        db = SessionLocal()
        try:
            query = db.query(ProxmoxCluster)
            if cluster_id is not None:
                cluster = query.filter(ProxmoxCluster.id == cluster_id).first()
                if cluster is None:
                    raise RuntimeError(
                        f"Bound Proxmox cluster {cluster_id} does not exist"
                    )
                return cluster
            return query.filter(ProxmoxCluster.is_active.is_(True)).one_or_none()
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(
                "Unable to load Proxmox configuration from the database"
            ) from exc
        finally:
            db.close()

    async def list_nodes(self):
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=30) as client:
            r = await client.get(f"{self.base_url}/nodes", headers=self.headers)
            r.raise_for_status()
            return r.json()["data"]

    async def clone_vm(self, node: str, source_vmid: int, newid: int, name: str):
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=30) as client:
            r = await client.post(
                f"{self.base_url}/nodes/{node}/qemu/{source_vmid}/clone",
                headers=self.headers,
                data={"newid": newid, "name": name, "full": 1},
            )
            r.raise_for_status()
            return r.json()

    async def start_vm(self, node: str, vmid: int):
        return await self._vm_action(node, vmid, "start")

    async def stop_vm(self, node: str, vmid: int):
        return await self._vm_action(node, vmid, "stop")

    async def reboot_vm(self, node: str, vmid: int):
        return await self._vm_action(node, vmid, "reboot")

    async def delete_vm(self, node: str, vmid: int):
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=30) as client:
            r = await client.delete(
                f"{self.base_url}/nodes/{node}/qemu/{vmid}", headers=self.headers
            )
            r.raise_for_status()
            return r.json()

    async def vm_exists(self, vmid: int) -> bool:
        """Check cluster-wide IDs without querying a nonexistent guest's status."""
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=30) as client:
            response = await client.get(
                f"{self.base_url}/cluster/resources",
                headers=self.headers,
                params={"type": "vm"},
            )
            response.raise_for_status()
            rows = response.json().get("data")
        if not isinstance(rows, list):
            raise RuntimeError("Invalid Proxmox VM inventory response")
        identifiers = set()
        for row in rows:
            if not isinstance(row, dict) or row.get("type") not in {"qemu", "lxc"}:
                raise RuntimeError("Invalid Proxmox VM inventory entry")
            identifier = row.get("vmid")
            if isinstance(identifier, bool) or not str(identifier).isdigit():
                raise RuntimeError("Invalid Proxmox VM inventory identifier")
            identifiers.add(int(identifier))
        return vmid in identifiers

    async def get_vm_status(self, node: str, vmid: int):
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=30) as client:
            r = await client.get(
                f"{self.base_url}/nodes/{node}/qemu/{vmid}/status/current",
                headers=self.headers,
            )
            r.raise_for_status()
            return r.json()["data"]

    async def wait_for_task(
        self,
        node: str,
        upid: str,
        timeout_seconds: int = 120,
        on_poll=None,
        allow_warnings: bool = False,
    ):
        deadline = asyncio.get_event_loop().time() + timeout_seconds
        while True:

            async def _fetch_task():
                async with httpx.AsyncClient(
                    verify=self.verify_ssl, timeout=30
                ) as client:
                    r = await client.get(
                        f"{self.base_url}/nodes/{node}/tasks/{upid}/status",
                        headers=self.headers,
                    )
                    r.raise_for_status()
                    return r.json()["data"]

            rr = await async_retry_with_backoff(
                _fetch_task, max_attempts=3, allowed_exceptions=(httpx.HTTPError,)
            )
            if not rr.ok:
                raise TimeoutError(f"Failed polling task {upid}: {rr.error}")
            task = rr.value
            if task.get("status") == "stopped":
                exitstatus = str(task.get("exitstatus") or "")
                warning = bool(re.fullmatch(r"WARNINGS: [1-9][0-9]*", exitstatus))
                if exitstatus != "OK" and not (allow_warnings and warning):
                    raise RuntimeError(
                        f"Proxmox task failed: {task.get('exitstatus') or 'unknown'}"
                    )
                return task
            if on_poll is not None:
                on_poll()
            if asyncio.get_event_loop().time() > deadline:
                raise TimeoutError(f"Timed out waiting for Proxmox task {upid}")
            await asyncio.sleep(2)

    async def _vm_action(self, node: str, vmid: int, action: str):
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=30) as client:
            r = await client.post(
                f"{self.base_url}/nodes/{node}/qemu/{vmid}/status/{action}",
                headers=self.headers,
            )
            r.raise_for_status()
            return r.json()

    async def get_vm_config(self, node: str, vmid: int):
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=15) as client:
            response = await client.get(
                f"{self.base_url}/nodes/{node}/qemu/{vmid}/config", headers=self.headers
            )
            response.raise_for_status()
            return response.json().get("data", {})

    async def get_terminal_ticket(self, node: str, vmid: int):
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=15) as client:
            response = await client.post(
                f"{self.base_url}/nodes/{node}/qemu/{vmid}/termproxy",
                headers=self.headers,
                data={"serial": "serial0"},
            )
            response.raise_for_status()
            return response.json().get("data", {})

    async def get_novnc_ticket(self, node: str, vmid: int):
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=30) as client:
            r = await client.post(
                f"{self.base_url}/nodes/{node}/qemu/{vmid}/vncproxy",
                headers=self.headers,
                data={"websocket": 1},
            )
            r.raise_for_status()
            return r.json().get("data", {})

    async def get_spice_config(self, node: str, vmid: int):
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=30) as client:
            r = await client.post(
                f"{self.base_url}/nodes/{node}/qemu/{vmid}/spiceproxy",
                headers=self.headers,
            )
            r.raise_for_status()
            return r.json().get("data", "")

    async def get_guest_network(self, node: str, vmid: int):
        async def _fetch():
            async with httpx.AsyncClient(verify=self.verify_ssl, timeout=30) as client:
                r = await client.get(
                    f"{self.base_url}/nodes/{node}/qemu/{vmid}/agent/network-get-interfaces",
                    headers=self.headers,
                )
                r.raise_for_status()
                return r.json().get("data", {}).get("result", [])

        rr = await async_retry_with_backoff(
            _fetch, max_attempts=3, allowed_exceptions=(httpx.HTTPError,)
        )
        if not rr.ok:
            raise TimeoutError(
                f"Guest-agent discovery failed for vmid={vmid}: {rr.error}"
            )
        return rr.value
