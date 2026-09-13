from urllib.parse import parse_qs

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.models import ProxmoxCluster, ProxmoxNode
import app.services.proxmox_bootstrap as bootstrap_module
from app.services.proxmox_bootstrap import (
    ProxmoxBootstrapError,
    ProxmoxBootstrapService,
    SERVICE_PRIVILEGES,
    SERVICE_ROLE,
    SERVICE_USER,
)


def _database():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, autocommit=False, autoflush=False)()


def _install_transport(monkeypatch, handler):
    def routed(request):
        if request.url.path.endswith("/access/roles/Administrator"):
            return httpx.Response(
                200, json={"data": {p: 1 for p in SERVICE_PRIVILEGES}}
            )
        return handler(request)

    transport = httpx.MockTransport(routed)
    real_client = httpx.AsyncClient

    def client_factory(**kwargs):
        return real_client(transport=transport, **kwargs)

    monkeypatch.setattr(bootstrap_module.httpx, "AsyncClient", client_factory)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"verify_ssl": "false"}, "verify_ssl must be a boolean"),
        ({"root_username": "admin@pam"}, "only root@pam"),
        ({"root_password": "x" * 4097}, "accepted length"),
        ({"name": "x" * 121}, "1-120 printable characters"),
    ],
)
async def test_root_bootstrap_rejects_invalid_inputs_before_network(
    monkeypatch, override, message
):
    def unexpected_network(**_kwargs):
        raise AssertionError("invalid input must not reach Proxmox")

    monkeypatch.setattr(bootstrap_module.httpx, "AsyncClient", unexpected_network)
    engine, db = _database()
    payload = {
        "name": "Primary Proxmox",
        "api_url": "https://pve.example.test:8006/api2/json",
        "root_password": "root-secret",
        **override,
    }
    try:
        with pytest.raises(ValueError, match=message):
            await ProxmoxBootstrapService(db).bootstrap_with_root(payload)
    finally:
        db.close()
        Base.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_root_bootstrap_creates_and_stores_only_dedicated_token(monkeypatch):
    requests = []
    token_secret = "generated-proxmox-token-secret"

    def handler(request: httpx.Request):
        body = parse_qs(request.content.decode())
        requests.append((request.method, request.url.path, body, dict(request.headers)))
        path = request.url.path
        if request.method == "POST" and path.endswith("/access/ticket"):
            assert body == {"username": ["root@pam"], "password": ["root-secret"]}
            return httpx.Response(
                200,
                json={
                    "data": {
                        "ticket": "root-ticket",
                        "CSRFPreventionToken": "csrf-token",
                    }
                },
            )
        if request.method == "GET" and path.endswith("/access/roles"):
            return httpx.Response(200, json={"data": []})
        if request.method == "POST" and path.endswith("/access/roles"):
            assert body["roleid"] == [SERVICE_ROLE]
            assert set(body["privs"][0].split()) == SERVICE_PRIVILEGES
            return httpx.Response(200, json={"data": None})
        if request.method == "GET" and path.endswith("/access/users"):
            return httpx.Response(200, json={"data": []})
        if request.method == "POST" and path.endswith("/access/users"):
            assert body["userid"] == [SERVICE_USER]
            return httpx.Response(200, json={"data": None})
        if request.method == "PUT" and path.endswith("/access/acl"):
            assert body["path"] == ["/"]
            assert body["users"] == [SERVICE_USER]
            assert body["roles"] == [SERVICE_ROLE]
            return httpx.Response(200, json={"data": None})
        if request.method == "POST" and path.endswith(
            f"/access/users/{SERVICE_USER}/token/labgoblin"
        ):
            assert body["privsep"] == ["0"]
            return httpx.Response(200, json={"data": {"value": token_secret}})
        if request.method == "GET" and path.endswith("/cluster/resources"):
            assert request.headers["Authorization"] == (
                f"PVEAPIToken={SERVICE_USER}!labgoblin={token_secret}"
            )
            return httpx.Response(
                200,
                json={"data": [{"type": "node", "node": "pve1", "status": "online"}]},
            )
        return httpx.Response(
            500, json={"error": f"unexpected {request.method} {path}"}
        )

    _install_transport(monkeypatch, handler)
    monkeypatch.setattr(
        bootstrap_module, "encrypt_secret", lambda value: f"encrypted::{value}"
    )
    engine, db = _database()
    try:
        result = await ProxmoxBootstrapService(db).bootstrap_with_root(
            {
                "name": "Primary Proxmox",
                "api_url": "https://pve.example.test:8006/api2/json",
                "root_username": "root@pam",
                "root_password": "root-secret",
                "verify_ssl": True,
            }
        )
        cluster = db.query(ProxmoxCluster).one()
        assert result["token_user"] == SERVICE_USER
        assert result["token_id"] == "labgoblin"
        assert result["nodes_discovered"] == 1
        assert cluster.token_user == SERVICE_USER
        assert cluster.is_active is True
        assert cluster.encrypted_token_secret == f"encrypted::{token_secret}"
        assert db.query(ProxmoxNode).one().node_name == "pve1"
        non_login_requests = [
            item for item in requests if not item[1].endswith("/access/ticket")
        ]
        assert "root-secret" not in repr(non_login_requests)
    finally:
        db.close()
        Base.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_root_bootstrap_refuses_broader_existing_role(monkeypatch):
    def handler(request: httpx.Request):
        if request.url.path.endswith("/access/ticket"):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "ticket": "root-ticket",
                        "CSRFPreventionToken": "csrf-token",
                    }
                },
            )
        if request.url.path.endswith("/access/roles"):
            return httpx.Response(200, json={"data": [{"roleid": SERVICE_ROLE}]})
        if request.url.path.endswith(f"/access/roles/{SERVICE_ROLE}"):
            data = {privilege: 1 for privilege in SERVICE_PRIVILEGES}
            data["Permissions.Modify"] = 1
            return httpx.Response(200, json={"data": data})
        return httpx.Response(500)

    _install_transport(monkeypatch, handler)
    engine, db = _database()
    try:
        with pytest.raises(ProxmoxBootstrapError, match="unexpected privileges"):
            await ProxmoxBootstrapService(db).bootstrap_with_root(
                {
                    "name": "Primary Proxmox",
                    "api_url": "https://pve.example.test:8006/api2/json",
                    "root_password": "root-secret",
                }
            )
        assert db.query(ProxmoxCluster).count() == 0
    finally:
        db.close()
        Base.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_failed_token_validation_removes_created_user_and_role(monkeypatch):
    deletes = []

    def handler(request: httpx.Request):
        path = request.url.path
        if request.method == "POST" and path.endswith("/access/ticket"):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "ticket": "root-ticket",
                        "CSRFPreventionToken": "csrf-token",
                    }
                },
            )
        if request.method == "GET" and (
            path.endswith("/access/roles") or path.endswith("/access/users")
        ):
            return httpx.Response(200, json={"data": []})
        if request.method in {"POST", "PUT"} and path.endswith("/access/roles"):
            return httpx.Response(200, json={"data": None})
        if request.method == "POST" and path.endswith("/access/users"):
            return httpx.Response(200, json={"data": None})
        if request.method == "PUT" and path.endswith("/access/acl"):
            return httpx.Response(200, json={"data": None})
        if request.method == "POST" and "/token/labgoblin" in path:
            return httpx.Response(200, json={"data": {"value": "bad-token"}})
        if request.method == "GET" and path.endswith("/cluster/resources"):
            return httpx.Response(403, json={"data": None})
        if request.method == "DELETE":
            deletes.append(path)
            return httpx.Response(200, json={"data": None})
        return httpx.Response(500)

    _install_transport(monkeypatch, handler)
    engine, db = _database()
    try:
        with pytest.raises(ProxmoxBootstrapError, match="permission validation"):
            await ProxmoxBootstrapService(db).bootstrap_with_root(
                {
                    "name": "Primary Proxmox",
                    "api_url": "https://pve.example.test:8006/api2/json",
                    "root_password": "root-secret",
                }
            )
        assert any(path.endswith(f"/access/users/{SERVICE_USER}") for path in deletes)
        assert any(path.endswith(f"/access/roles/{SERVICE_ROLE}") for path in deletes)
        assert db.query(ProxmoxCluster).count() == 0
    finally:
        db.close()
        Base.metadata.drop_all(engine)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["roles", "users"])
@pytest.mark.parametrize(
    "status,data", [(500, None), (403, None), (200, None), (200, [{}])]
)
async def test_identity_discovery_fails_closed(monkeypatch, kind, status, data):
    def handler(request):
        assert request.method == "GET"
        assert request.url.path.endswith("/access/" + kind)
        return httpx.Response(status, json={"data": data})

    _install_transport(monkeypatch, handler)
    service = ProxmoxBootstrapService(None)
    operation = (
        service._ensure_service_role
        if kind == "roles"
        else service._create_service_user
    )
    with pytest.raises((httpx.HTTPStatusError, ProxmoxBootstrapError)):
        await operation(
            "https://pve.example.test/api2/json",
            True,
            {"ticket": "test", "csrf": "test"},
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", [False, True])
async def test_role_uses_supported_guest_agent_privilege(monkeypatch, legacy):
    available = set(SERVICE_PRIVILEGES)
    assert "VM.GuestAgent.Audit" in available
    assert "VM.Monitor" not in available
    if legacy:
        available.remove("VM.GuestAgent.Audit")
        available.add("VM.Monitor")
    posted = []

    def handler(request):
        if request.method == "GET" and request.url.path.endswith("/Administrator"):
            return httpx.Response(200, json={"data": {p: 1 for p in available}})
        if request.method == "GET":
            return httpx.Response(200, json={"data": []})
        posted.append(parse_qs(request.content.decode())["privs"][0].split())
        return httpx.Response(200, json={"data": None})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        bootstrap_module.httpx,
        "AsyncClient",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )
    await ProxmoxBootstrapService(None)._ensure_service_role(
        "https://pve.example.test/api2/json", True, {"ticket": "test", "csrf": "test"}
    )
    assert set(posted[0]) == available
