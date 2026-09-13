from datetime import datetime
import httpx
from sqlalchemy.orm import Session
from urllib.parse import quote

from app.models.models import ProxmoxCluster, ProxmoxNode, ProxmoxClusterDefault
from app.services.secret_crypto import encrypt_secret, decrypt_secret
from app.services.proxmox_url import canonicalize_proxmox_api_url


TOKEN_ID_DEFAULT = "labgoblin"
SERVICE_USER = "labgoblin@pve"
SERVICE_ROLE = "LabGoblinRole"
SERVICE_PRIVILEGES = frozenset(
    {
        "Datastore.AllocateSpace",
        "Datastore.AllocateTemplate",
        "Datastore.Audit",
        "Pool.Allocate",
        "Pool.Audit",
        "SDN.Audit",
        "SDN.Use",
        "Sys.Audit",
        "VM.Allocate",
        "VM.Audit",
        "VM.Clone",
        "VM.Console",
        "VM.GuestAgent.Audit",
        "VM.PowerMgmt",
    }
)


class ProxmoxBootstrapError(RuntimeError):
    """A safe bootstrap failure that never contains credentials."""


class ProxmoxBootstrapService:
    def __init__(self, db: Session):
        self.db = db

    async def bootstrap_with_root(self, payload: dict) -> dict:
        verify_ssl = payload.get("verify_ssl", True)
        if not isinstance(verify_ssl, bool):
            raise ValueError("verify_ssl must be a boolean")
        api_url = canonicalize_proxmox_api_url(
            payload["api_url"], verify_ssl=verify_ssl
        )
        root_username = str(payload.get("root_username") or "root@pam").strip()
        if root_username != "root@pam":
            raise ValueError("Automatic bootstrap accepts only root@pam")
        root_password = str(payload.get("root_password") or "")
        if not root_password:
            raise ValueError("Root password is required for bootstrap")
        if len(root_password) > 4096:
            raise ValueError("Root password exceeds the accepted length")
        cluster_name = str(payload.get("name") or "").strip()
        if not cluster_name:
            raise ValueError("Cluster name is required")
        if len(cluster_name) > 120 or not cluster_name.isprintable():
            raise ValueError("Cluster name must be 1-120 printable characters")
        token_id = TOKEN_ID_DEFAULT

        existing_cluster = (
            self.db.query(ProxmoxCluster)
            .filter(ProxmoxCluster.name == cluster_name)
            .first()
        )
        if existing_cluster is not None:
            raise ProxmoxBootstrapError(
                "A cluster with this name already exists; validate it or use manual token setup"
            )

        steps = []
        auth_ticket = await self._login(
            api_url, verify_ssl, root_username, root_password
        )
        steps.append({"step": "root_authentication", "status": "success"})

        created_role = False
        created_user = False
        try:
            created_role = await self._ensure_service_role(
                api_url, verify_ssl, auth_ticket
            )
            steps.append(
                {"step": "service_role", "status": "success", "created": created_role}
            )
            await self._create_service_user(api_url, verify_ssl, auth_ticket)
            created_user = True
            steps.append({"step": "service_user", "status": "success", "created": True})
            await self._grant_service_acl(api_url, verify_ssl, auth_ticket)
            steps.append({"step": "service_acl", "status": "success"})
            token_secret = await self._create_service_token(
                api_url, verify_ssl, auth_ticket, token_id
            )
            steps.append({"step": "service_token", "status": "success"})
            probe = await self._validate_with_token(
                api_url, verify_ssl, SERVICE_USER, token_id, token_secret
            )
            if not probe.get("ok"):
                raise ProxmoxBootstrapError(
                    "The dedicated API token failed its permission validation"
                )
            resources = probe.get("resources", [])
            steps.append(
                {
                    "step": "token_validation",
                    "status": "success",
                    "count": len(resources),
                }
            )

            has_active_cluster = (
                self.db.query(ProxmoxCluster)
                .filter(ProxmoxCluster.is_active.is_(True))
                .first()
                is not None
            )
            cluster = ProxmoxCluster(
                name=cluster_name,
                api_url=api_url,
                verify_ssl=verify_ssl,
                auth_mode="token",
                root_username=root_username,
                token_user=SERVICE_USER,
                token_id=token_id,
                encrypted_token_secret=encrypt_secret(token_secret),
                token_created_by_app=True,
                is_active=not has_active_cluster,
                last_validated_at=datetime.utcnow(),
                last_validation_status="success",
                last_validation_error=None,
            )
            self.db.add(cluster)
            self.db.flush()

            self._upsert_nodes(cluster.id, resources)

            defaults = ProxmoxClusterDefault(cluster_id=cluster.id)
            self.db.add(defaults)
            self.db.commit()
        except Exception:
            self.db.rollback()
            if created_user:
                await self._delete_service_user_best_effort(
                    api_url, verify_ssl, auth_ticket
                )
            if created_role:
                await self._delete_service_role_best_effort(
                    api_url, verify_ssl, auth_ticket
                )
            raise

        node_count = len([item for item in resources if item.get("type") == "node"])
        return {
            "cluster_id": cluster.id,
            "name": cluster.name,
            "api_url": cluster.api_url,
            "verify_ssl": cluster.verify_ssl,
            "token_user": cluster.token_user,
            "token_id": cluster.token_id,
            "token_created_by_app": True,
            "is_active": cluster.is_active,
            "nodes_discovered": node_count,
            "steps": steps,
        }

    @staticmethod
    def _root_client(auth: dict, verify_ssl: bool) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            verify=verify_ssl,
            timeout=20,
            cookies={"PVEAuthCookie": auth["ticket"]},
            headers={"CSRFPreventionToken": auth["csrf"]},
            follow_redirects=False,
        )

    async def _ensure_service_role(
        self, api_url: str, verify_ssl: bool, auth: dict
    ) -> bool:
        role_path = f"{api_url}/access/roles/{SERVICE_ROLE}"
        async with self._root_client(auth, verify_ssl) as client:
            listing = await client.get(f"{api_url}/access/roles")
            listing.raise_for_status()
            rows = listing.json().get("data")
            if not isinstance(rows, list) or any(
                not isinstance(row, dict) or "roleid" not in row for row in rows
            ):
                raise ProxmoxBootstrapError("Invalid Proxmox role discovery response")
            supported_response = await client.get(
                f"{api_url}/access/roles/Administrator"
            )
            supported_response.raise_for_status()
            supported = supported_response.json().get("data")
            if not isinstance(supported, dict):
                raise ProxmoxBootstrapError(
                    "Invalid Proxmox privilege discovery response"
                )
            available = {
                key for key, value in supported.items() if value in (1, True, "1")
            }
            privileges = set(SERVICE_PRIVILEGES)
            if "VM.GuestAgent.Audit" not in available and "VM.Monitor" in available:
                privileges.remove("VM.GuestAgent.Audit")
                privileges.add("VM.Monitor")
            missing = privileges - available
            if missing:
                raise ProxmoxBootstrapError(
                    "Proxmox does not support required privileges: "
                    + ", ".join(sorted(missing))
                )
            if any(row["roleid"] == SERVICE_ROLE for row in rows):
                existing = await client.get(role_path)
                existing.raise_for_status()
                data = existing.json().get("data", {})
                actual = {
                    key for key, enabled in data.items() if enabled in (1, True, "1")
                }
                if actual != privileges:
                    raise ProxmoxBootstrapError(
                        f"Existing {SERVICE_ROLE} has unexpected privileges; refusing to modify it"
                    )
                return False
            created = await client.post(
                f"{api_url}/access/roles",
                data={
                    "roleid": SERVICE_ROLE,
                    "privs": " ".join(sorted(privileges)),
                },
            )
            created.raise_for_status()
            return True

    async def _create_service_user(
        self, api_url: str, verify_ssl: bool, auth: dict
    ) -> None:
        async with self._root_client(auth, verify_ssl) as client:
            listing = await client.get(f"{api_url}/access/users")
            listing.raise_for_status()
            rows = listing.json().get("data")
            if not isinstance(rows, list) or any(
                not isinstance(row, dict) or "userid" not in row for row in rows
            ):
                raise ProxmoxBootstrapError("Invalid Proxmox user discovery response")
            if any(row["userid"] == SERVICE_USER for row in rows):
                raise ProxmoxBootstrapError(
                    f"{SERVICE_USER} already exists; refusing to take ownership automatically"
                )
            created = await client.post(
                f"{api_url}/access/users",
                data={
                    "userid": SERVICE_USER,
                    "enable": 1,
                    "comment": "Managed by LabGoblin",
                },
            )
            created.raise_for_status()

    async def _grant_service_acl(
        self, api_url: str, verify_ssl: bool, auth: dict
    ) -> None:
        async with self._root_client(auth, verify_ssl) as client:
            response = await client.put(
                f"{api_url}/access/acl",
                data={
                    "path": "/",
                    "users": SERVICE_USER,
                    "roles": SERVICE_ROLE,
                    "propagate": 1,
                },
            )
            response.raise_for_status()

    async def _create_service_token(
        self, api_url: str, verify_ssl: bool, auth: dict, token_id: str
    ) -> str:
        encoded_user = quote(SERVICE_USER, safe="")
        async with self._root_client(auth, verify_ssl) as client:
            response = await client.post(
                f"{api_url}/access/users/{encoded_user}/token/{token_id}",
                data={"privsep": 0, "comment": "Managed by LabGoblin"},
            )
            response.raise_for_status()
            secret = response.json().get("data", {}).get("value")
            if not secret:
                raise ProxmoxBootstrapError(
                    "Proxmox created the API token without returning its secret"
                )
            return str(secret)

    async def _delete_service_user_best_effort(
        self, api_url: str, verify_ssl: bool, auth: dict
    ) -> None:
        encoded_user = quote(SERVICE_USER, safe="")
        try:
            async with self._root_client(auth, verify_ssl) as client:
                await client.delete(f"{api_url}/access/users/{encoded_user}")
        except Exception:
            pass

    async def _delete_service_role_best_effort(
        self, api_url: str, verify_ssl: bool, auth: dict
    ) -> None:
        try:
            async with self._root_client(auth, verify_ssl) as client:
                await client.delete(f"{api_url}/access/roles/{SERVICE_ROLE}")
        except Exception:
            pass

    async def upsert_manual_token(self, payload: dict) -> dict:
        verify_ssl = bool(payload.get("verify_ssl", True))
        api_url = canonicalize_proxmox_api_url(
            payload["api_url"], verify_ssl=verify_ssl
        )
        name = payload["name"]
        token_user = payload["token_user"]
        token_id = payload["token_id"]
        token_secret = payload["token_secret"]

        probe = await self._validate_with_token(
            api_url, verify_ssl, token_user, token_id, token_secret
        )
        if not probe.get("ok"):
            return probe

        cluster = (
            self.db.query(ProxmoxCluster).filter(ProxmoxCluster.name == name).first()
        )
        if cluster is None:
            cluster = ProxmoxCluster(name=name)
            self.db.add(cluster)

        cluster.api_url = api_url
        cluster.verify_ssl = verify_ssl
        cluster.auth_mode = "token"
        cluster.token_user = token_user
        cluster.token_id = token_id
        cluster.encrypted_token_secret = encrypt_secret(token_secret)
        cluster.token_created_by_app = False
        cluster.last_validated_at = datetime.utcnow()
        cluster.last_validation_status = "success"
        cluster.last_validation_error = None
        self.db.flush()
        self._upsert_nodes(cluster.id, probe.get("resources", []))
        self.db.commit()
        return {
            "ok": True,
            "cluster_id": cluster.id,
            "nodes_discovered": probe.get("nodes_count", 0),
        }

    async def validate_cluster(self, cluster: ProxmoxCluster) -> dict:
        headers = self._cluster_headers(cluster)
        if not headers:
            return {"ok": False, "error": "missing token secret"}
        async with httpx.AsyncClient(
            verify=cluster.verify_ssl, timeout=20, follow_redirects=False
        ) as client:
            r = await client.get(f"{cluster.api_url}/nodes", headers=headers)
            r.raise_for_status()
            nodes = r.json().get("data", [])
        return {"ok": True, "nodes_count": len(nodes)}

    async def discover_storage(self, cluster: ProxmoxCluster) -> list[dict]:
        headers = self._cluster_headers(cluster)
        if not headers:
            return []
        out: list[dict] = []
        async with httpx.AsyncClient(
            verify=cluster.verify_ssl,
            timeout=20,
            headers=headers,
            follow_redirects=False,
        ) as client:
            nodes_resp = await client.get(f"{cluster.api_url}/nodes")
            nodes_resp.raise_for_status()
            for node in nodes_resp.json().get("data", []):
                node_name = node.get("node")
                if not node_name:
                    continue
                s = await client.get(f"{cluster.api_url}/nodes/{node_name}/storage")
                if s.status_code >= 400:
                    continue
                for st in s.json().get("data", []):
                    out.append(
                        {
                            "node": node_name,
                            "storage": st.get("storage"),
                            "type": st.get("type"),
                            "content": st.get("content"),
                            "enabled": st.get("enabled"),
                            "active": st.get("active"),
                        }
                    )
        return out

    async def discover_templates(self, cluster: ProxmoxCluster) -> list[dict]:
        headers = self._cluster_headers(cluster)
        if not headers:
            return []
        out: list[dict] = []
        async with httpx.AsyncClient(
            verify=cluster.verify_ssl,
            timeout=20,
            headers=headers,
            follow_redirects=False,
        ) as client:
            nodes_resp = await client.get(f"{cluster.api_url}/nodes")
            nodes_resp.raise_for_status()
            for node in nodes_resp.json().get("data", []):
                node_name = node.get("node")
                if not node_name:
                    continue
                v = await client.get(f"{cluster.api_url}/nodes/{node_name}/qemu")
                if v.status_code >= 400:
                    continue
                for vm in v.json().get("data", []):
                    if vm.get("template") != 1:
                        continue
                    out.append(
                        {
                            "node": node_name,
                            "vmid": vm.get("vmid"),
                            "name": vm.get("name"),
                            "status": vm.get("status"),
                            "template": True,
                        }
                    )
        return out

    async def discover_networks(self, cluster: ProxmoxCluster) -> list[dict]:
        headers = self._cluster_headers(cluster)
        if not headers:
            return []
        out: list[dict] = []
        async with httpx.AsyncClient(
            verify=cluster.verify_ssl,
            timeout=20,
            headers=headers,
            follow_redirects=False,
        ) as client:
            nodes_resp = await client.get(f"{cluster.api_url}/nodes")
            nodes_resp.raise_for_status()
            for node in nodes_resp.json().get("data", []):
                node_name = node.get("node")
                if not node_name:
                    continue
                n = await client.get(f"{cluster.api_url}/nodes/{node_name}/network")
                if n.status_code >= 400:
                    continue
                for net in n.json().get("data", []):
                    if (net.get("iface") or "").startswith("vmbr"):
                        out.append(
                            {
                                "node": node_name,
                                "bridge": net.get("iface"),
                                "type": net.get("type"),
                                "active": net.get("active"),
                                "autostart": net.get("autostart"),
                            }
                        )
        return out

    async def discover_isos(self, cluster: ProxmoxCluster) -> dict:
        headers = self._cluster_headers(cluster)
        if not headers:
            return {"items": [], "warnings": ["Missing token secret for cluster"]}
        out: list[dict] = []
        warnings: list[str] = []
        async with httpx.AsyncClient(
            verify=cluster.verify_ssl,
            timeout=20,
            headers=headers,
            follow_redirects=False,
        ) as client:
            nodes_resp = await client.get(f"{cluster.api_url}/nodes")
            nodes_resp.raise_for_status()
            for node in nodes_resp.json().get("data", []):
                node_name = node.get("node")
                if not node_name:
                    continue
                s = await client.get(f"{cluster.api_url}/nodes/{node_name}/storage")
                if s.status_code >= 400:
                    warnings.append(f"Could not read storage list for node {node_name}")
                    continue
                for st in s.json().get("data", []):
                    storage = st.get("storage")
                    if not storage:
                        continue
                    c = await client.get(
                        f"{cluster.api_url}/nodes/{node_name}/storage/{storage}/content"
                    )
                    if c.status_code >= 400:
                        continue
                    for item in c.json().get("data", []):
                        volid = item.get("volid") or ""
                        ctype = item.get("content")
                        if (
                            ctype != "iso"
                            and "/iso/" not in volid
                            and not volid.endswith(".iso")
                        ):
                            continue
                        out.append(
                            {
                                "node": node_name,
                                "storage": storage,
                                "content_id": volid,
                                "name": item.get("text") or volid.split("/")[-1],
                                "content_type": ctype,
                                "size": item.get("size"),
                            }
                        )
        if not out and not warnings:
            warnings.append(
                "No ISO/media content discovered. Configure ISO storage or use shared media."
            )
        return {"items": out, "warnings": warnings}

    async def _login(
        self, api_url: str, verify_ssl: bool, username: str, password: str
    ) -> dict:
        async with httpx.AsyncClient(
            verify=verify_ssl, timeout=20, follow_redirects=False
        ) as client:
            r = await client.post(
                f"{api_url}/access/ticket",
                data={"username": username, "password": password},
            )
            r.raise_for_status()
            data = r.json().get("data", {})
            if not data.get("ticket") or not data.get("CSRFPreventionToken"):
                raise ProxmoxBootstrapError(
                    "Proxmox authentication succeeded without a usable root session"
                )
            return {
                "ticket": data.get("ticket"),
                "csrf": data.get("CSRFPreventionToken"),
            }

    async def _validate_with_token(
        self,
        api_url: str,
        verify_ssl: bool,
        token_user: str,
        token_id: str,
        token_secret: str,
    ) -> dict:
        headers = {
            "Authorization": f"PVEAPIToken={token_user}!{token_id}={token_secret}"
        }
        async with httpx.AsyncClient(
            verify=verify_ssl,
            timeout=20,
            headers=headers,
            follow_redirects=False,
        ) as client:
            r = await client.get(f"{api_url}/cluster/resources")
            if r.status_code >= 400:
                return {
                    "ok": False,
                    "error": f"token validation failed ({r.status_code})",
                }
            resources = r.json().get("data", [])
        nodes_count = len([x for x in resources if x.get("type") == "node"])
        return {"ok": True, "resources": resources, "nodes_count": nodes_count}

    def _upsert_nodes(self, cluster_id: int, resources: list[dict]) -> None:
        self.db.query(ProxmoxNode).filter(ProxmoxNode.cluster_id == cluster_id).delete()
        for item in resources:
            if item.get("type") == "node":
                self.db.add(
                    ProxmoxNode(
                        cluster_id=cluster_id,
                        node_name=item.get("node"),
                        status=item.get("status"),
                        raw_summary_json=str(item),
                    )
                )

    def _cluster_headers(self, cluster: ProxmoxCluster) -> dict | None:
        secret = (
            decrypt_secret(cluster.encrypted_token_secret)
            if cluster.encrypted_token_secret
            else None
        )
        if not secret:
            return None
        return {
            "Authorization": f"PVEAPIToken={cluster.token_user}!{cluster.token_id}={secret}"
        }
