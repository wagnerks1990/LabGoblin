from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
import httpx
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.session import get_db
from app.models.models import (
    ProxmoxCluster,
    Organization,
    ProxmoxNode,
    ProxmoxClusterDefault,
    VMTemplate,
    StudentVM,
    User,
    ProxmoxHostAccess,
    AuditLog,
)
from app.core.config import settings
from app.services.proxmox_bootstrap import (
    ProxmoxBootstrapError,
    ProxmoxBootstrapService,
)
from app.services.proxmox import ProxmoxClient
from app.services.proxmox_resource_stats import ProxmoxResourceStatsService
from app.services.asset_server_control import (
    AssetServerControl,
    HostRunnerNotConfiguredError,
)
from app.services.host_runner import HostRunnerService
from app.services.organization_access import (
    OrganizationContext,
    get_current_organization,
)

router = APIRouter()


def _audit(db: Session, actor_id: int, action: str, target_id: str, details: str):
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=f"{action}: {details}",
            target_type="host_access",
            target_id=target_id,
        )
    )


def _resolve_cluster_id(db: Session, cluster_id: int | None) -> int:
    if cluster_id:
        return int(cluster_id)
    active = db.query(ProxmoxCluster).filter(ProxmoxCluster.is_active.is_(True)).first()
    if not active:
        raise HTTPException(
            status_code=400, detail="No active Proxmox cluster configured."
        )
    return int(active.id)


def _mask(v: str | None) -> str | None:
    if not v:
        return None
    if len(v) <= 4:
        return "****"
    return f"{v[:2]}***{v[-2:]}"


def _compute_asset_constraints(
    *,
    online_nodes: set[str],
    eligible_nodes: set[str],
    templates: list[dict],
    iso_items: list[dict],
    placement_policy: str | None,
):
    template_by_vmid: dict[int, set[str]] = {}
    for t in templates:
        vmid = t.get("vmid")
        node = t.get("node")
        if vmid is None or not node:
            continue
        try:
            ivmid = int(vmid)
        except Exception:
            continue
        template_by_vmid.setdefault(ivmid, set()).add(str(node))

    iso_by_content: dict[str, set[str]] = {}
    iso_by_node: dict[str, set[str]] = {}
    for i in iso_items:
        node = i.get("node")
        key = i.get("content_id") or i.get("name")
        if not node or not key:
            continue
        node = str(node)
        key = str(key)
        iso_by_content.setdefault(key, set()).add(node)
        iso_by_node.setdefault(node, set()).add(key)

    required_nodes = set(eligible_nodes or set())
    if (
        placement_policy in {"balanced", "prefer_default_then_balance"}
        and len(online_nodes) > 1
    ):
        required_nodes = set(online_nodes)

    missing_templates_by_node: dict[str, list[int]] = {}
    for node in sorted(required_nodes):
        missing = sorted(
            [vmid for vmid, ns in template_by_vmid.items() if node not in ns]
        )
        if missing:
            missing_templates_by_node[node] = missing

    missing_isos_by_node: dict[str, list[str]] = {}
    all_isos = set(iso_by_content.keys())
    for node in sorted(required_nodes):
        node_isos = iso_by_node.get(node, set())
        missing = sorted([iso for iso in all_isos if iso not in node_isos])
        if missing and all_isos:
            missing_isos_by_node[node] = missing

    asset_ready_nodes = sorted(
        [
            node
            for node in required_nodes
            if node not in missing_templates_by_node
            and node not in missing_isos_by_node
        ]
    )
    constrained_nodes = sorted(
        [n for n in required_nodes if n not in set(asset_ready_nodes)]
    )
    return {
        "template_by_vmid": template_by_vmid,
        "iso_by_content": iso_by_content,
        "asset_ready_nodes": asset_ready_nodes,
        "constrained_nodes": constrained_nodes,
        "missing_templates_by_node": missing_templates_by_node,
        "missing_isos_by_node": missing_isos_by_node,
    }


@router.get("/admin/proxmox/clusters")
def list_clusters(_user=Depends(require_role("Admin")), db: Session = Depends(get_db)):
    rows = db.query(ProxmoxCluster).order_by(ProxmoxCluster.id.desc()).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "api_url": r.api_url,
            "verify_ssl": r.verify_ssl,
            "auth_mode": r.auth_mode,
            "token_user": r.token_user,
            "token_id": _mask(r.token_id),
            "token_created_by_app": r.token_created_by_app,
            "is_active": r.is_active,
            "last_validated_at": r.last_validated_at,
            "last_validation_status": r.last_validation_status,
            "last_validation_error": r.last_validation_error,
        }
        for r in rows
    ]


@router.post("/admin/proxmox/bootstrap-root")
async def bootstrap_root(
    payload: dict, _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    required = ["name", "api_url", "root_password"]
    missing = [key for key in required if not payload.get(key)]
    if missing:
        raise HTTPException(
            status_code=422, detail={"error": f"Missing fields: {', '.join(missing)}"}
        )
    try:
        return await ProxmoxBootstrapService(db).bootstrap_with_root(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProxmoxBootstrapError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        raise HTTPException(
            status_code=502,
            detail=f"Proxmox rejected root bootstrap (HTTP {status})",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="Unable to reach Proxmox securely during root bootstrap",
        ) from exc


@router.post("/admin/proxmox/host-access/bootstrap")
def host_access_bootstrap(
    payload: dict, _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    raise HTTPException(
        status_code=501,
        detail=(
            "Automatic host-access bootstrap is disabled because the current "
            "implementation cannot securely install or verify a runner key. "
            "Configure the least-privilege host runner manually and use the "
            "validation endpoint."
        ),
    )


@router.get("/admin/proxmox/host-access/status")
def host_access_status(
    cluster_id: int | None = None,
    _user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    cluster_id = _resolve_cluster_id(db, cluster_id)
    rows = (
        db.query(ProxmoxHostAccess)
        .filter(ProxmoxHostAccess.cluster_id == cluster_id)
        .all()
    )
    cluster_nodes = (
        db.query(ProxmoxNode).filter(ProxmoxNode.cluster_id == cluster_id).all()
    )
    mode = "api_only"
    if settings.asset_source_iso_base_url or settings.asset_source_ct_base_url:
        mode = "static_asset_server"
    if any(r.status == "host_runner" for r in rows):
        mode = "host_runner"
    row_by_node = {r.node_name: r for r in rows}
    nodes = []
    for n in cluster_nodes:
        r = row_by_node.get(n.node_name)
        nodes.append(
            {
                "node_name": n.node_name,
                "cluster_status": n.status,
                "host_access_status": r.status if r else "not_configured",
                "runner_user": (r.runner_user if r else settings.host_runner_user),
                "auth_method": (r.auth_method if r else None),
                "capabilities": (
                    [] if not r or not r.capabilities_json else [r.capabilities_json]
                ),
                "public_key_fingerprint": (r.public_key_fingerprint if r else None),
                "last_checked_at": (r.last_checked_at if r else None),
            }
        )
    return {
        "cluster_id": cluster_id,
        "mode": mode,
        "asset_source_node": settings.asset_source_node,
        "asset_source_iso_base_url": settings.asset_source_iso_base_url,
        "asset_source_ct_base_url": settings.asset_source_ct_base_url,
        "nodes": nodes,
    }


@router.post("/admin/proxmox/host-access/validate")
def host_access_validate(
    payload: dict, _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    cluster_id = _resolve_cluster_id(db, payload.get("cluster_id"))
    _audit(db, _user.id, "host_access.validate.started", str(cluster_id), "started")
    try:
        runner = HostRunnerService()
        runner.ensure_ready()
    except ValueError as e:
        db.commit()
        return {
            "ok": False,
            "cluster_id": cluster_id,
            "validated_nodes": [],
            "message": str(e),
        }

    nodes = db.query(ProxmoxNode).filter(ProxmoxNode.cluster_id == cluster_id).all()
    validated, failed = [], []
    for n in nodes:
        iso = runner.run_helper(n.node_name, "iso", "status")
        ct = runner.run_helper(n.node_name, "ct_template", "status")
        helper_executed = iso.returncode == 0 or ct.returncode == 0
        if helper_executed:
            rec = (
                db.query(ProxmoxHostAccess)
                .filter(
                    ProxmoxHostAccess.cluster_id == cluster_id,
                    ProxmoxHostAccess.node_name == n.node_name,
                )
                .first()
            )
            if not rec:
                rec = ProxmoxHostAccess(cluster_id=cluster_id, node_name=n.node_name)
                db.add(rec)
            rec.status = "host_runner"
            rec.runner_user = settings.host_runner_user
            rec.auth_method = "ssh_key"
            rec.key_ref = settings.host_runner_private_key_path
            rec.capabilities_json = str(
                {"asset_server": ["status", "install", "start", "stop"]}
            )
            rec.last_checked_at = datetime.utcnow()
            rec.updated_at = datetime.utcnow()
            validated.append(
                {
                    "node_name": n.node_name,
                    "status": "host_runner",
                    "allowlist_ok": True,
                }
            )
        else:
            failed.append(
                {
                    "node_name": n.node_name,
                    "error": (
                        iso.stderr or ct.stderr or "helper execution failed"
                    ).strip()[:300],
                }
            )
    _audit(
        db,
        _user.id,
        "host_access.validate.completed",
        str(cluster_id),
        f"nodes={len(validated)}",
    )
    db.commit()
    if not validated:
        return {
            "ok": False,
            "cluster_id": cluster_id,
            "validated_nodes": [],
            "failed_nodes": failed,
            "message": "Host runner is not configured for any cluster nodes.",
        }
    return {
        "ok": len(failed) == 0,
        "cluster_id": cluster_id,
        "validated_nodes": validated,
        "failed_nodes": failed,
        "message": ("Validated with partial failures." if failed else "Validated."),
    }


@router.get("/admin/proxmox/asset-server/status")
def asset_server_status(
    kind: str,
    cluster_id: int | None = None,
    source_node: str | None = None,
    _user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    try:
        return AssetServerControl(db).status(
            kind=kind, cluster_id=cluster_id, source_node=source_node
        )
    except HostRunnerNotConfiguredError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/admin/proxmox/asset-server/install")
def asset_server_install(
    payload: dict, _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    try:
        return AssetServerControl(db).action(
            "install",
            kind=payload.get("kind"),
            cluster_id=payload.get("cluster_id"),
            source_node=payload.get("source_node"),
            bind_address=payload.get("bind_address"),
            port=payload.get("port"),
        )
    except HostRunnerNotConfiguredError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/admin/proxmox/asset-server/start")
def asset_server_start(
    payload: dict, _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    try:
        return AssetServerControl(db).action(
            "start",
            kind=payload.get("kind"),
            cluster_id=payload.get("cluster_id"),
            source_node=payload.get("source_node"),
            bind_address=payload.get("bind_address"),
            port=payload.get("port"),
        )
    except HostRunnerNotConfiguredError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/admin/proxmox/asset-server/stop")
def asset_server_stop(
    payload: dict, _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    try:
        return AssetServerControl(db).action(
            "stop",
            kind=payload.get("kind"),
            cluster_id=payload.get("cluster_id"),
            source_node=payload.get("source_node"),
            bind_address=payload.get("bind_address"),
            port=payload.get("port"),
        )
    except HostRunnerNotConfiguredError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/admin/proxmox/clusters/{id}")
def get_cluster(
    id: int, _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    row = db.query(ProxmoxCluster).filter(ProxmoxCluster.id == id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Cluster not found")
    defaults = (
        db.query(ProxmoxClusterDefault)
        .filter(ProxmoxClusterDefault.cluster_id == id)
        .first()
    )
    return {
        "id": row.id,
        "name": row.name,
        "api_url": row.api_url,
        "verify_ssl": row.verify_ssl,
        "auth_mode": row.auth_mode,
        "token_user": row.token_user,
        "token_id": _mask(row.token_id),
        "token_created_by_app": row.token_created_by_app,
        "is_active": row.is_active,
        "last_validated_at": row.last_validated_at,
        "last_validation_status": row.last_validation_status,
        "last_validation_error": row.last_validation_error,
        "defaults": {
            "default_node": getattr(defaults, "default_node", None),
            "default_storage": getattr(defaults, "default_storage", None),
            "default_bridge": getattr(defaults, "default_bridge", None),
            "default_template_vmid": getattr(defaults, "default_template_vmid", None),
            "clone_mode": getattr(defaults, "clone_mode", None),
            "placement_policy": getattr(defaults, "placement_policy", None),
            "notes": getattr(defaults, "notes", None),
        },
    }


@router.patch("/admin/proxmox/clusters/{id}")
def patch_cluster(
    id: int,
    payload: dict,
    _user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    row = db.query(ProxmoxCluster).filter(ProxmoxCluster.id == id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Cluster not found")
    if "api_url" in payload or "verify_ssl" in payload:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cluster endpoint and TLS policy cannot be changed in place. "
                "Create or validate a new credential-bound cluster configuration."
            ),
        )
    for key in ["name"]:
        if key in payload:
            setattr(row, key, payload[key])
    db.commit()
    return {"ok": True}


@router.delete("/admin/proxmox/clusters/{id}")
def delete_cluster(
    id: int, _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    row = db.query(ProxmoxCluster).filter(ProxmoxCluster.id == id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Cluster not found")
    dependency_counts = {
        "templates": db.query(VMTemplate)
        .filter(VMTemplate.proxmox_cluster_id == id)
        .count(),
        "vm_history": db.query(StudentVM)
        .filter(StudentVM.proxmox_cluster_id == id)
        .count(),
    }
    if any(dependency_counts.values()):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "Cluster cannot be deleted while templates or VM history reference it.",
                "dependencies": dependency_counts,
            },
        )
    db.query(ProxmoxNode).filter(ProxmoxNode.cluster_id == id).delete()
    db.query(ProxmoxClusterDefault).filter(
        ProxmoxClusterDefault.cluster_id == id
    ).delete()
    db.delete(row)
    db.commit()
    return {"ok": True, "deleted_cluster_id": id}


@router.patch("/admin/proxmox/clusters/{id}/defaults")
def patch_defaults(
    id: int,
    payload: dict,
    _user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    row = db.query(ProxmoxCluster).filter(ProxmoxCluster.id == id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Cluster not found")
    d = (
        db.query(ProxmoxClusterDefault)
        .filter(ProxmoxClusterDefault.cluster_id == id)
        .first()
    )
    if d is None:
        d = ProxmoxClusterDefault(cluster_id=id)
        db.add(d)
    for key in [
        "default_node",
        "default_storage",
        "default_bridge",
        "default_template_vmid",
        "clone_mode",
        "placement_policy",
        "notes",
    ]:
        if key in payload:
            setattr(d, key, payload[key])
    db.commit()
    return {
        "ok": True,
        "defaults": {
            "default_node": d.default_node,
            "default_storage": d.default_storage,
            "default_bridge": d.default_bridge,
            "default_template_vmid": d.default_template_vmid,
            "clone_mode": d.clone_mode,
            "placement_policy": d.placement_policy,
            "notes": d.notes,
        },
    }


@router.post("/admin/proxmox/clusters/{id}/activate")
def activate_cluster(
    id: int, _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    row = db.query(ProxmoxCluster).filter(ProxmoxCluster.id == id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Cluster not found")
    db.query(ProxmoxCluster).update({ProxmoxCluster.is_active: False})
    row.is_active = True
    row.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "active_cluster_id": id}


@router.post("/admin/proxmox/clusters/{id}/validate")
async def validate_cluster(
    id: int, _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    row = db.query(ProxmoxCluster).filter(ProxmoxCluster.id == id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Cluster not found")
    svc = ProxmoxBootstrapService(db)
    result = await svc.validate_cluster(row)
    row.last_validated_at = datetime.utcnow()
    row.last_validation_status = "success" if result.get("ok") else "error"
    row.last_validation_error = None if result.get("ok") else result.get("error")
    db.commit()
    return result


@router.get("/admin/proxmox/clusters/{id}/nodes")
def list_cluster_nodes(
    id: int, _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    return [
        {
            "id": n.id,
            "node_name": n.node_name,
            "status": n.status,
            "last_seen_at": n.last_seen_at,
        }
        for n in db.query(ProxmoxNode).filter(ProxmoxNode.cluster_id == id).all()
    ]


@router.get("/admin/proxmox/clusters/{id}/storage")
@router.get("/admin/proxmox/cluster/{id}/storage")
@router.get("/admin/proxmox/clusters/{id}/storage/")
async def list_cluster_storage(
    id: int, _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    row = db.query(ProxmoxCluster).filter(ProxmoxCluster.id == id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return await ProxmoxBootstrapService(db).discover_storage(row)


@router.get("/admin/proxmox/clusters/{id}/templates")
@router.get("/admin/proxmox/cluster/{id}/templates")
@router.get("/admin/proxmox/clusters/{id}/templates/")
async def list_cluster_templates(
    id: int, _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    row = db.query(ProxmoxCluster).filter(ProxmoxCluster.id == id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return await ProxmoxBootstrapService(db).discover_templates(row)


@router.get("/admin/proxmox/clusters/{id}/networks")
@router.get("/admin/proxmox/cluster/{id}/networks")
@router.get("/admin/proxmox/clusters/{id}/networks/")
async def list_cluster_networks(
    id: int, _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    row = db.query(ProxmoxCluster).filter(ProxmoxCluster.id == id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return await ProxmoxBootstrapService(db).discover_networks(row)


@router.post("/admin/proxmox/clusters/manual-token")
async def manual_token(
    payload: dict, _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    required = ["name", "api_url", "token_user", "token_id", "token_secret"]
    missing = [k for k in required if not payload.get(k)]
    if missing:
        raise HTTPException(
            status_code=422, detail={"error": f"Missing fields: {', '.join(missing)}"}
        )
    svc = ProxmoxBootstrapService(db)
    try:
        result = await svc.upsert_manual_token(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.get("/admin/proxmox/resource-stats")
async def active_resource_stats(
    _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    try:
        return await ProxmoxResourceStatsService(db).active_cluster_stats()
    except RuntimeError as exc:
        return {
            "config_source": "not_configured",
            "cluster": {"id": None, "name": None, "api_url": None},
            "summary": {
                "total_nodes": 0,
                "online_nodes": 0,
                "offline_nodes": 0,
                "total_cpu_cores": 0,
                "cpu_usage_percent": None,
                "memory_used_bytes": 0,
                "memory_total_bytes": 0,
                "memory_usage_percent": None,
                "disk_used_bytes": 0,
                "disk_total_bytes": 0,
                "disk_usage_percent": None,
                "total_vms": 0,
                "running_vms": 0,
                "stopped_vms": 0,
                "paused_vms": 0,
                "templates": 0,
                "unknown_vms": 0,
            },
            "nodes": [],
            "warnings": [str(exc)],
            "fetched_at": datetime.utcnow().isoformat() + "Z",
        }


@router.get("/admin/proxmox/clusters/{id}/resource-stats")
async def cluster_resource_stats(
    id: int, _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    row = db.query(ProxmoxCluster).filter(ProxmoxCluster.id == id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return await ProxmoxResourceStatsService(db).cluster_stats(row)


@router.get("/admin/proxmox/templates/discovered")
async def discovered_templates(
    _user=Depends(require_role("Admin")),
    organization: OrganizationContext = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    active = db.query(ProxmoxCluster).filter(ProxmoxCluster.is_active.is_(True)).first()
    if not active:
        raise HTTPException(
            status_code=404, detail="No active Proxmox cluster configured"
        )
    discovered = await ProxmoxBootstrapService(db).discover_templates(active)
    out = []
    for t in discovered:
        existing = (
            db.query(VMTemplate)
            .filter(
                VMTemplate.organization_id == organization.id,
                VMTemplate.proxmox_cluster_id == active.id,
                VMTemplate.source_vmid == t.get("vmid"),
            )
            .first()
        )
        out.append(
            {
                "node": t.get("node"),
                "vmid": t.get("vmid"),
                "name": t.get("name"),
                "status": t.get("status"),
                "template": bool(t.get("template", True)),
                "already_imported": bool(existing),
                "imported_template_id": getattr(existing, "id", None),
            }
        )
    return out


@router.post("/admin/proxmox/templates/import")
async def import_templates(
    payload: dict,
    _user=Depends(require_role("Admin")),
    organization: OrganizationContext = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    active = db.query(ProxmoxCluster).filter(ProxmoxCluster.is_active.is_(True)).first()
    if not active:
        raise HTTPException(
            status_code=409, detail="No active Proxmox cluster configured"
        )
    items = (
        payload.get("templates")
        if isinstance(payload.get("templates"), list)
        else [payload]
    )
    imported = []
    for item in items:
        vmid = (
            int(item["source_vmid"])
            if item.get("source_vmid") is not None
            else int(item["vmid"])
        )
        node = item.get("proxmox_node") or item.get("node")
        name = item.get("name") or f"template-{vmid}"
        enabled = bool(item.get("enabled", True))
        row = (
            db.query(VMTemplate)
            .filter(
                VMTemplate.organization_id == organization.id,
                VMTemplate.proxmox_cluster_id == active.id,
                VMTemplate.source_vmid == vmid,
            )
            .first()
        )
        if row is None:
            row = VMTemplate(
                organization_id=organization.id,
                proxmox_cluster_id=active.id,
                name=name,
                proxmox_node=node,
                source_vmid=vmid,
                enabled=enabled,
            )
            db.add(row)
        else:
            row.name = name or row.name
            row.proxmox_node = node or row.proxmox_node
            if "enabled" in item:
                row.enabled = enabled
        db.flush()
        imported.append(
            {
                "id": row.id,
                "name": row.name,
                "proxmox_node": row.proxmox_node,
                "source_vmid": row.source_vmid,
                "enabled": row.enabled,
            }
        )
    db.commit()
    return {"ok": True, "imported": imported}


@router.post("/admin/proxmox/templates/sync")
async def sync_templates(
    _user=Depends(require_role("Admin")),
    organization: OrganizationContext = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    active = db.query(ProxmoxCluster).filter(ProxmoxCluster.is_active.is_(True)).first()
    if not active:
        raise HTTPException(
            status_code=404, detail="No active Proxmox cluster configured"
        )
    discovered = await ProxmoxBootstrapService(db).discover_templates(active)
    # Serialize catalog updates for the selected tenant, preserving existing IDs.
    db.query(Organization).filter(
        Organization.id == organization.id
    ).with_for_update().one()
    catalog = (
        db.query(VMTemplate).filter(VMTemplate.organization_id == organization.id).all()
    )
    names = {row.name for row in catalog}
    imported = []
    for t in discovered:
        vmid = int(t["vmid"])
        node = t["node"]
        row = next(
            (
                item
                for item in catalog
                if item.proxmox_cluster_id == active.id and item.source_vmid == vmid
            ),
            None,
        )
        if row is None:
            legacy = [
                item
                for item in catalog
                if item.proxmox_cluster_id is None
                and item.source_vmid == vmid
                and item.proxmox_node == node
            ]
            if len(legacy) == 1:
                row = legacy[0]
                row.proxmox_cluster_id = active.id
        if row is None:
            base = str(t.get("name") or f"template-{vmid}")[:100]
            name = base
            suffix = 0
            while name in names:
                suffix += 1
                ending = f"-{active.id}-{vmid}-{suffix}"
                name = base[: 100 - len(ending)] + ending
            row = VMTemplate(
                organization_id=organization.id,
                proxmox_cluster_id=active.id,
                name=name,
                proxmox_node=node,
                source_vmid=vmid,
                enabled=True,
            )
            db.add(row)
            catalog.append(row)
            names.add(name)
        else:
            row.proxmox_node = node
        db.flush()
        imported.append(
            {
                "id": row.id,
                "name": row.name,
                "proxmox_node": row.proxmox_node,
                "source_vmid": row.source_vmid,
                "enabled": row.enabled,
            }
        )
    db.commit()
    return {"ok": True, "imported_count": len(imported), "imported": imported}


@router.get("/admin/proxmox/inventory/vms")
async def proxmox_inventory_vms(
    status: str | None = None,
    node: str | None = None,
    template: bool | None = None,
    q: str | None = None,
    linked: bool | None = None,
    _user=Depends(require_role("Admin")),
    organization: OrganizationContext = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    active = db.query(ProxmoxCluster).filter(ProxmoxCluster.is_active.is_(True)).first()
    if not active:
        raise HTTPException(
            status_code=404, detail="No active Proxmox cluster configured"
        )
    stats = await ProxmoxResourceStatsService(db).cluster_stats(active)
    tpl_map = {
        t.source_vmid: t
        for t in db.query(VMTemplate)
        .filter(
            VMTemplate.organization_id == organization.id,
            VMTemplate.proxmox_cluster_id == active.id,
        )
        .all()
    }
    vm_map = {
        v.vmid: v
        for v in db.query(StudentVM)
        .filter(
            StudentVM.organization_id == organization.id,
            StudentVM.proxmox_cluster_id == active.id,
            StudentVM.deleted_at.is_(None),
        )
        .all()
    }
    users = {u.id: u.username for u in db.query(User).all()}
    items = []
    for n in stats.get("nodes", []):
        pass
    # Build from live resources for richer fields
    client = ProxmoxClient(active.id)
    import httpx

    async with httpx.AsyncClient(
        verify=client.verify_ssl, timeout=30, headers=client.headers
    ) as http:
        r = await http.get(f"{client.base_url}/cluster/resources")
        r.raise_for_status()
        resources = r.json().get("data", [])
    for vm in [x for x in resources if x.get("type") == "qemu"]:
        vmid = int(vm.get("vmid"))
        is_tpl = vm.get("template") in (1, True, "1", "true", "True")
        linked_vm = vm_map.get(vmid)
        linked_tpl = tpl_map.get(vmid)
        row = {
            "source": "proxmox",
            "node": vm.get("node"),
            "vmid": vmid,
            "name": vm.get("name"),
            "status": vm.get("status"),
            "template": bool(is_tpl),
            "cpu_usage": vm.get("cpu"),
            "memory_used": vm.get("mem"),
            "memory_total": vm.get("maxmem"),
            "disk_used": vm.get("disk"),
            "disk_total": vm.get("maxdisk"),
            "uptime": vm.get("uptime"),
            "tags": vm.get("tags"),
            "app_linked": bool(linked_vm or linked_tpl),
            "app_vm_id": getattr(linked_vm, "id", None),
            "app_template_id": getattr(linked_tpl, "id", None),
            "owner_username": users.get(linked_vm.owner_id) if linked_vm else None,
        }
        items.append(row)

    def ok(it):
        if status and (it.get("status") or "").lower() != status.lower():
            return False
        if node and it.get("node") != node:
            return False
        if template is not None and bool(it.get("template")) != bool(template):
            return False
        if linked is not None and bool(it.get("app_linked")) != bool(linked):
            return False
        if q:
            qq = q.lower()
            if qq not in str(it.get("name", "")).lower() and qq not in str(
                it.get("vmid", "")
            ):
                return False
        return True

    return [x for x in items if ok(x)]


@router.post("/admin/proxmox/vms/{node}/{vmid}/start")
async def admin_start_vm(node: str, vmid: int, _user=Depends(require_role("Admin"))):
    raise HTTPException(
        status_code=409,
        detail="Direct mutation of unmanaged Proxmox inventory is disabled",
    )


@router.post("/admin/proxmox/vms/{node}/{vmid}/stop")
async def admin_stop_vm(node: str, vmid: int, _user=Depends(require_role("Admin"))):
    raise HTTPException(
        status_code=409,
        detail="Direct mutation of unmanaged Proxmox inventory is disabled",
    )


@router.post("/admin/proxmox/vms/{node}/{vmid}/reboot")
async def admin_reboot_vm(node: str, vmid: int, _user=Depends(require_role("Admin"))):
    raise HTTPException(
        status_code=409,
        detail="Direct mutation of unmanaged Proxmox inventory is disabled",
    )


@router.post("/admin/proxmox/vms/{node}/{vmid}/shutdown")
async def admin_shutdown_vm(node: str, vmid: int, _user=Depends(require_role("Admin"))):
    raise HTTPException(
        status_code=409,
        detail="Direct mutation of unmanaged Proxmox inventory is disabled",
    )


@router.get("/admin/proxmox/vms/{node}/{vmid}/status")
async def admin_vm_status(node: str, vmid: int, _user=Depends(require_role("Admin"))):
    return await ProxmoxClient().get_vm_status(node, vmid)


@router.get("/admin/proxmox/templates/availability")
async def template_availability(
    _user=Depends(require_role("Admin")),
    organization: OrganizationContext = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    active = db.query(ProxmoxCluster).filter(ProxmoxCluster.is_active.is_(True)).first()
    if not active:
        raise HTTPException(
            status_code=404, detail="No active Proxmox cluster configured"
        )
    svc = ProxmoxBootstrapService(db)
    discovered = await svc.discover_templates(active)
    nodes = [
        n.node_name
        for n in db.query(ProxmoxNode).filter(ProxmoxNode.cluster_id == active.id).all()
    ]
    out = []
    by_vmid = {}
    for t in discovered:
        by_vmid.setdefault(int(t.get("vmid")), []).append(t)

    imported_by_vmid = {}
    for row in (
        db.query(VMTemplate).filter(VMTemplate.organization_id == organization.id).all()
    ):
        vmid = int(row.source_vmid)
        imported_by_vmid[vmid] = row
        found = by_vmid.get(vmid, [])
        available_nodes = sorted({str(x.get("node")) for x in found if x.get("node")})
        missing_nodes = sorted([n for n in nodes if n not in available_nodes])
        warnings = (
            []
            if len(missing_nodes) == 0
            else [f"Only available on {', '.join(available_nodes) or 'no nodes'}"]
        )
        recommended_action = (
            "Ready for balanced placement across all discovered nodes."
            if len(missing_nodes) == 0
            else "Use prefer_default_then_balance/manual policy, shared storage, or Proxmox-native replication before balanced placement."
        )
        out.append(
            {
                "template_id": row.id,
                "template_vmid": vmid,
                "name": row.name,
                "source_node": row.proxmox_node,
                "available_nodes": available_nodes,
                "missing_nodes": missing_nodes,
                "can_balance_across_all_nodes": len(missing_nodes) == 0,
                "clone_target_supported": None,
                "storage_compatibility": None,
                "warnings": warnings,
                "recommended_action": recommended_action,
            }
        )

    # Include discovered templates not yet imported into app vm_templates so readiness is complete.
    for vmid, found in sorted(by_vmid.items(), key=lambda kv: kv[0]):
        if vmid in imported_by_vmid:
            continue
        available_nodes = sorted({str(x.get("node")) for x in found if x.get("node")})
        missing_nodes = sorted([n for n in nodes if n not in available_nodes])
        sample = found[0] if found else {}
        warnings = ["Template discovered but not imported into app templates."]
        if missing_nodes:
            warnings.append(
                f"Only available on {', '.join(available_nodes) or 'no nodes'}."
            )
        out.append(
            {
                "template_id": None,
                "template_vmid": vmid,
                "name": sample.get("name") or f"vm-{vmid}",
                "source_node": sample.get("node"),
                "available_nodes": available_nodes,
                "missing_nodes": missing_nodes,
                "can_balance_across_all_nodes": len(missing_nodes) == 0,
                "clone_target_supported": None,
                "storage_compatibility": None,
                "warnings": warnings,
                "recommended_action": "Import this template first, then validate cross-node availability for balanced placement.",
            }
        )
    return out


@router.get("/admin/proxmox/reconciliation/vms")
async def reconcile_vms(
    _user=Depends(require_role("Admin")),
    organization: OrganizationContext = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    active = db.query(ProxmoxCluster).filter(ProxmoxCluster.is_active.is_(True)).first()
    if not active:
        raise HTTPException(
            status_code=404, detail="No active Proxmox cluster configured"
        )
    inv = await proxmox_inventory_vms(_user=_user, organization=organization, db=db)
    inv_map = {(x.get("node"), int(x.get("vmid"))): x for x in inv}
    report = []
    matched = 0
    missing = 0
    status_updated = 0
    app_rows = (
        db.query(StudentVM)
        .filter(
            StudentVM.organization_id == organization.id,
            StudentVM.proxmox_cluster_id == active.id,
            StudentVM.deleted_at.is_(None),
        )
        .all()
    )
    for vm in app_rows:
        key = (vm.proxmox_node, int(vm.vmid))
        found = inv_map.get(key)
        previous_status = vm.status
        if not found:
            new_status = vm.status if vm.status in {"missing", "error"} else "missing"
            vm.status = new_status
            if previous_status != new_status:
                status_updated += 1
            missing += 1
            report.append(
                {
                    "app_vm_id": vm.id,
                    "vmid": vm.vmid,
                    "node": vm.proxmox_node,
                    "state": "app_only_missing_in_proxmox",
                    "previous_status": previous_status,
                    "new_status": vm.status,
                    "message": f"App VM record exists but VMID {vm.vmid} was not found on {vm.proxmox_node}.",
                }
            )
        else:
            proxmox_status = (
                found.get("status") or vm.status or ""
            ).lower() or vm.status
            if proxmox_status and vm.status != proxmox_status:
                vm.status = proxmox_status
                status_updated += 1
            state = "matched" if vm.status == proxmox_status else "status_mismatch"
            if state == "matched":
                matched += 1
            report.append(
                {
                    "app_vm_id": vm.id,
                    "vmid": vm.vmid,
                    "node": vm.proxmox_node,
                    "state": state,
                    "previous_status": previous_status,
                    "new_status": vm.status,
                    "proxmox_status": proxmox_status,
                    "message": f"VMID {vm.vmid} exists in Proxmox on {vm.proxmox_node}.",
                }
            )
    db.commit()
    proxmox_only = [x for x in inv if not x.get("app_vm_id")]
    return {
        "summary": {
            "app_vms": len(app_rows),
            "matched": matched,
            "missing": missing,
            "status_updated": status_updated,
            "proxmox_only": len(proxmox_only),
        },
        "report": report,
        "proxmox_only_count": len(proxmox_only),
        "proxmox_only": proxmox_only,
    }


@router.post("/admin/proxmox/reconciliation/vms")
async def reconcile_vms_post(
    _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    return await reconcile_vms(_user=_user, db=db)


@router.post("/admin/proxmox/templates/{vmid}/sync")
async def sync_template_to_nodes(
    vmid: int,
    payload: dict,
    _user=Depends(require_role("Admin")),
    db: Session = Depends(get_db),
):
    active = db.query(ProxmoxCluster).filter(ProxmoxCluster.is_active.is_(True)).first()
    if not active:
        raise HTTPException(
            status_code=404, detail="No active Proxmox cluster configured"
        )
    source_node = payload.get("source_node")
    target_nodes = payload.get("target_nodes") or []
    target_storage = payload.get("target_storage")
    if not source_node or not target_nodes:
        raise HTTPException(
            status_code=422,
            detail={"error": "source_node and target_nodes are required"},
        )
    # Validation-only/dry-run to avoid unsafe assumptions on cross-node template replication semantics
    svc = ProxmoxBootstrapService(db)
    storage = await svc.discover_storage(active)
    unavailable = [
        n
        for n in target_nodes
        if target_storage
        and not any(
            s.get("node") == n and s.get("storage") == target_storage for s in storage
        )
    ]
    if unavailable:
        return {
            "ok": False,
            "supported": False,
            "message": "Some target nodes do not have requested storage.",
            "unavailable_nodes": unavailable,
        }
    return {
        "ok": False,
        "supported": False,
        "message": "Automated cross-node template replication is not enabled in cloud-safe mode. Use Proxmox native replication/clone workflow, then refresh discovery.",
    }


@router.get("/admin/proxmox/clusters/{id}/isos")
async def list_cluster_isos(
    id: int, _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    row = db.query(ProxmoxCluster).filter(ProxmoxCluster.id == id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Cluster not found")
    result = await ProxmoxBootstrapService(db).discover_isos(row)
    return {"items": result.get("items", []), "warnings": result.get("warnings", [])}


@router.get("/admin/proxmox/clusters/{id}/readiness")
async def cluster_readiness(
    id: int, _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    cluster = db.query(ProxmoxCluster).filter(ProxmoxCluster.id == id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    svc = ProxmoxBootstrapService(db)
    nodes = [
        {
            "node_name": n.node_name,
            "status": n.status,
            "memory_total": n.memory_total,
            "memory_used": n.memory_used,
            "cpu_total": n.cpu_total,
            "cpu_used": n.cpu_used,
        }
        for n in db.query(ProxmoxNode).filter(ProxmoxNode.cluster_id == id).all()
    ]
    storage = await svc.discover_storage(cluster)
    templates = await svc.discover_templates(cluster)
    networks = await svc.discover_networks(cluster)
    isos_result = await svc.discover_isos(cluster)
    defaults = (
        db.query(ProxmoxClusterDefault)
        .filter(ProxmoxClusterDefault.cluster_id == id)
        .first()
    )
    template_vmid = getattr(defaults, "default_template_vmid", None)
    default_storage = getattr(defaults, "default_storage", None)
    default_bridge = getattr(defaults, "default_bridge", None)
    policy = getattr(defaults, "placement_policy", None)
    online_nodes = {
        n["node_name"]
        for n in nodes
        if (n.get("status") or "").lower() in {"online", "up"}
    }
    eligible_nodes = set(online_nodes)
    warnings = list(isos_result.get("warnings", []))
    failures = []
    if not online_nodes:
        failures.append("No online nodes discovered in active cluster.")
    if template_vmid:
        tpl_nodes = {
            str(t.get("node"))
            for t in templates
            if int(t.get("vmid", -1)) == int(template_vmid)
        }
        if not tpl_nodes:
            failures.append(
                f"Default template VMID {template_vmid} was not found on discovered nodes."
            )
        elif tpl_nodes != online_nodes:
            warnings.append(
                f"Default template VMID {template_vmid} available only on: {', '.join(sorted(tpl_nodes))}."
            )
        eligible_nodes &= tpl_nodes
    if default_storage:
        st_nodes = {
            str(s.get("node"))
            for s in storage
            if s.get("storage") == default_storage
            and str(s.get("active")).lower() not in {"0", "false", "none"}
        }
        if not st_nodes:
            failures.append(
                f"Default storage {default_storage} not available on any discovered node."
            )
        eligible_nodes &= st_nodes
    if default_bridge:
        br_nodes = {
            str(n.get("node")) for n in networks if n.get("bridge") == default_bridge
        }
        if not br_nodes:
            failures.append(
                f"Default bridge {default_bridge} not found on discovered nodes."
            )
        eligible_nodes &= br_nodes
    constraints = _compute_asset_constraints(
        online_nodes=online_nodes,
        eligible_nodes=eligible_nodes,
        templates=templates,
        iso_items=isos_result.get("items", []),
        placement_policy=policy,
    )
    discovered_template_node_coverage = constraints["template_by_vmid"]
    node_limited_templates = [
        vmid
        for vmid, ns in discovered_template_node_coverage.items()
        if len(ns) == 1 and len(online_nodes) > 1
    ]
    iso_nodes = constraints["iso_by_content"]
    node_limited_isos = [
        k for k, ns in iso_nodes.items() if len(ns) == 1 and len(online_nodes) > 1
    ]

    if policy == "balanced" and (
        constraints["constrained_nodes"] or len(eligible_nodes) <= 1
    ):
        warnings.append(
            "Balanced placement is constrained because required assets are not available on all eligible nodes."
        )
    if not template_vmid and node_limited_templates:
        warnings.append(
            "Discovered templates are node-limited; balanced placement may be constrained until templates are prepared cluster-wide."
        )
    if node_limited_isos:
        warnings.append(
            "Discovered ISO/media files are node-limited; provisioning requiring ISO/media may be constrained on other nodes."
        )
    if policy == "prefer_default_then_balance" and (
        node_limited_templates or node_limited_isos
    ):
        warnings.append(
            "Fallback balancing is limited by template/ISO node availability."
        )
    excluded_nodes = sorted(list(online_nodes - eligible_nodes))
    excluded_reasons = {}
    for node_name in excluded_nodes:
        reasons = []
        if template_vmid:
            tpl_nodes = {
                str(t.get("node"))
                for t in templates
                if int(t.get("vmid", -1)) == int(template_vmid)
            }
            if node_name not in tpl_nodes:
                reasons.append("template_unavailable")
        if default_storage:
            st_nodes = {
                str(s.get("node"))
                for s in storage
                if s.get("storage") == default_storage
                and str(s.get("active")).lower() not in {"0", "false", "none"}
            }
            if node_name not in st_nodes:
                reasons.append("storage_unavailable")
        if default_bridge:
            br_nodes = {
                str(n.get("node"))
                for n in networks
                if n.get("bridge") == default_bridge
            }
            if node_name not in br_nodes:
                reasons.append("bridge_unavailable")
        excluded_reasons[node_name] = reasons or ["policy_filtered"]
    recommended_next_steps = []
    if failures:
        recommended_next_steps.append("Fix FAIL conditions before provisioning.")
    if warnings:
        recommended_next_steps.append(
            "Use prefer_default_then_balance or manual policy until assets are available cluster-wide."
        )
    if constraints["constrained_nodes"]:
        recommended_next_steps.append(
            f"Constrain placement to asset-ready nodes ({', '.join(constraints['asset_ready_nodes']) or 'none'}) until assets are available cluster-wide."
        )
        recommended_next_steps.append(
            "Use shared storage for templates/ISOs, or replicate/prepare required assets on all eligible nodes."
        )
    if template_vmid and len(eligible_nodes) <= 1:
        recommended_next_steps.append(
            "Replicate/prepare template on additional nodes or use shared template storage."
        )
    if node_limited_isos:
        recommended_next_steps.append(
            "Use shared ISO storage or replicate required media to additional nodes before balanced provisioning."
        )
    if default_storage:
        recommended_next_steps.append(
            f"Ensure storage {default_storage} exists and is active on intended target nodes."
        )
    if default_bridge:
        recommended_next_steps.append(
            f"Ensure bridge {default_bridge} exists on intended target nodes."
        )
    status = "FAIL" if failures else ("WARN" if warnings else "PASS")
    return {
        "status": status,
        "cluster": {
            "id": cluster.id,
            "name": cluster.name,
            "api_url": cluster.api_url,
            "is_active": cluster.is_active,
        },
        "defaults": {
            "default_node": getattr(defaults, "default_node", None),
            "default_storage": default_storage,
            "default_bridge": default_bridge,
            "default_template_vmid": template_vmid,
            "placement_policy": policy,
            "clone_mode": getattr(defaults, "clone_mode", None),
        },
        "nodes": nodes,
        "storage": storage,
        "templates": templates,
        "networks": networks,
        "isos": isos_result.get("items", []),
        "eligible_nodes": sorted(eligible_nodes),
        "asset_ready_nodes": constraints["asset_ready_nodes"],
        "constrained_nodes": constraints["constrained_nodes"],
        "missing_templates_by_node": constraints["missing_templates_by_node"],
        "missing_isos_by_node": constraints["missing_isos_by_node"],
        "excluded_nodes": excluded_nodes,
        "excluded_node_reasons": excluded_reasons,
        "warnings": warnings,
        "failures": failures,
        "recommended_next_steps": recommended_next_steps,
        "asset_summary": {
            "templates_total": len(discovered_template_node_coverage),
            "templates_cluster_wide": len(
                [
                    1
                    for _, ns in discovered_template_node_coverage.items()
                    if len(ns) == len(online_nodes) and len(online_nodes) > 0
                ]
            ),
            "templates_node_limited": len(node_limited_templates),
            "isos_total": len(iso_nodes),
            "isos_cluster_wide": len(
                [
                    1
                    for _, ns in iso_nodes.items()
                    if len(ns) == len(online_nodes) and len(online_nodes) > 0
                ]
            ),
            "isos_node_limited": len(node_limited_isos),
        },
        "placement_limitations": {
            "template": ["node_limited_templates"] if node_limited_templates else [],
            "storage": ["default_storage_not_cluster_wide"]
            if default_storage
            and any("storage" in w.lower() for w in warnings + failures)
            else [],
            "bridge": ["default_bridge_not_cluster_wide"]
            if default_bridge
            and any("bridge" in w.lower() for w in warnings + failures)
            else [],
            "iso_media": ["node_limited_isos"] if node_limited_isos else [],
        },
    }


@router.get("/admin/proxmox/assets/readiness-legacy")
async def assets_readiness_legacy(
    _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    active = db.query(ProxmoxCluster).filter(ProxmoxCluster.is_active.is_(True)).first()
    if not active:
        raise HTTPException(
            status_code=404, detail="No active Proxmox cluster configured"
        )
    readiness = await cluster_readiness(active.id, _user=_user, db=db)
    templates = readiness.get("templates", [])
    storage = readiness.get("storage", [])
    networks = readiness.get("networks", [])
    isos = readiness.get("isos", [])
    online_nodes = [
        n.get("node_name")
        for n in readiness.get("nodes", [])
        if (n.get("status") or "").lower() in {"online", "up"}
    ]
    template_nodes = sorted({str(t.get("node")) for t in templates if t.get("node")})
    storage_nodes = sorted(
        {
            str(s.get("node"))
            for s in storage
            if str(s.get("active")).lower() not in {"0", "false", "none"}
        }
    )
    bridge_nodes = sorted({str(n.get("node")) for n in networks if n.get("bridge")})
    return {
        **readiness,
        "summaries": {
            "template_readiness": {
                "templates_discovered": len(templates),
                "nodes_with_templates": template_nodes,
            },
            "iso_media_readiness": {"iso_items_discovered": len(isos)},
            "storage_readiness": {
                "storage_entries": len(storage),
                "nodes_with_active_storage": storage_nodes,
            },
            "bridge_readiness": {
                "bridge_entries": len(networks),
                "nodes_with_bridges": bridge_nodes,
            },
            "placement_limitations": readiness.get("warnings", []),
            "recommended_actions": readiness.get("recommended_next_steps", []),
            "online_nodes": online_nodes,
        },
    }


@router.post("/admin/proxmox/assets/sync-plan")
async def assets_sync_plan(
    payload: dict, _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    active = db.query(ProxmoxCluster).filter(ProxmoxCluster.is_active.is_(True)).first()
    if not active:
        raise HTTPException(
            status_code=404, detail="No active Proxmox cluster configured"
        )
    payload = payload or {}
    svc = ProxmoxBootstrapService(db)
    storage = await svc.discover_storage(active)
    templates = await svc.discover_templates(active)
    isos = await svc.discover_isos(active)
    nodes = [
        n.node_name
        for n in db.query(ProxmoxNode).filter(ProxmoxNode.cluster_id == active.id).all()
    ]

    req_type = payload.get("type") or payload.get("kind")
    if req_type == "media":
        req_type = "iso"

    if req_type == "template":
        vmid = int(payload.get("template_vmid", 0) or 0)
        source_node = payload.get("source_node")
        target_nodes = payload.get("target_nodes") or []
        target_storage = payload.get("target_storage")
        found = [t for t in templates if int(t.get("vmid", -1)) == vmid]
        template_nodes = sorted({str(t.get("node")) for t in found if t.get("node")})
        storage_ok = {
            n: bool(
                target_storage
                and any(
                    s.get("node") == n and s.get("storage") == target_storage
                    for s in storage
                )
            )
            for n in target_nodes
        }
        vmid_conflicts = {
            n: bool(
                any(
                    int(x.get("vmid", -1)) == vmid and str(x.get("node")) == n
                    for x in templates
                )
            )
            for n in target_nodes
        }
        warnings = []
        if not found:
            warnings.append(
                f"Template VMID {vmid} was not discovered in the active cluster."
            )
        if source_node and source_node not in template_nodes:
            warnings.append(
                f"Source node {source_node} does not currently host template VMID {vmid}."
            )
        missing_targets = [n for n in target_nodes if n not in nodes]
        if missing_targets:
            warnings.append(f"Unknown target nodes: {', '.join(missing_targets)}")
        return {
            "ok": True,
            "status": "dry_run",
            "supported": False,
            "kind": "template",
            "template_vmid": vmid,
            "source_node": source_node,
            "target_nodes": target_nodes,
            "target_storage": target_storage,
            "template_nodes": template_nodes,
            "target_storage_available": storage_ok,
            "vmid_conflicts": vmid_conflicts,
            "cluster_constraints": "Proxmox VMIDs are cluster-wide. Cross-node template replication requires explicit Proxmox-native workflow or shared storage.",
            "recommended_action": "Use manual/shared-storage preparation. Then refresh discovery and validate readiness.",
            "warnings": warnings,
        }

    if req_type == "iso":
        source_node = payload.get("source_node")
        source_storage = payload.get("source_storage")
        volume = payload.get("volume")
        target_nodes = payload.get("target_nodes") or []
        target_storage = payload.get("target_storage")
        iso_items = isos.get("items", [])
        source_exists = any(
            i.get("node") == source_node
            and i.get("storage") == source_storage
            and i.get("content_id") == volume
            for i in iso_items
        )
        target_storage_available = {
            n: bool(
                target_storage
                and any(
                    s.get("node") == n and s.get("storage") == target_storage
                    for s in storage
                )
            )
            for n in target_nodes
        }
        warnings = list(isos.get("warnings", []))
        if not source_exists:
            warnings.append(
                "Requested source ISO/media was not found in discovery output."
            )
        return {
            "ok": True,
            "status": "dry_run",
            "supported": False,
            "kind": "iso",
            "source_node": source_node,
            "source_storage": source_storage,
            "volume": volume,
            "target_nodes": target_nodes,
            "target_storage": target_storage,
            "source_exists": source_exists,
            "target_storage_available": target_storage_available,
            "cluster_constraints": "Automated ISO copy/transfer is not enabled in cloud-safe mode.",
            "recommended_action": "Use shared ISO storage or manual Proxmox copy, then refresh readiness.",
            "warnings": warnings,
        }

    return {
        "ok": True,
        "status": "dry_run",
        "supported": False,
        "message": "Specify payload.type or payload.kind as template or iso for detailed dry-run planning.",
        "request": payload,
    }


@router.post("/admin/proxmox/assets/sync-template")
async def assets_sync_template(
    payload: dict, _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    if not payload.get("confirm"):
        raise HTTPException(
            status_code=400,
            detail={"error": "confirm=true required for explicit admin sync action"},
        )
    plan = await assets_sync_plan(
        {"type": "template", **(payload or {})}, _user=_user, db=db
    )
    return {
        "ok": False,
        "status": "unsupported",
        "supported": False,
        "message": "Automated template sync is not enabled in cloud-safe mode. Use shared storage or manual Proxmox replication.",
        "plan": plan,
    }


@router.post("/admin/proxmox/assets/sync-iso")
async def assets_sync_iso(
    payload: dict, _user=Depends(require_role("Admin")), db: Session = Depends(get_db)
):
    if not payload.get("confirm"):
        raise HTTPException(
            status_code=400,
            detail={"error": "confirm=true required for explicit admin sync action"},
        )
    plan = await assets_sync_plan(
        {"type": "iso", **(payload or {})}, _user=_user, db=db
    )
    return {
        "ok": False,
        "status": "unsupported",
        "supported": False,
        "message": "Automated ISO/media sync is not enabled in cloud-safe mode. Use shared storage or manual Proxmox copy.",
        "plan": plan,
    }
