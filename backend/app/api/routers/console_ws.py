from fastapi import APIRouter, Depends, HTTPException, WebSocket
from sqlalchemy.orm import Session

from app.api.deps import get_user_from_token
from app.db.session import get_db
from app.models.models import User
from app.services.console_access import get_console_vm_for_user
from app.services.console_ws_service import ConsoleWsService
from app.services.organization_access import (
    OrganizationContext,
    resolve_organization_context,
)
from app.core.config import settings
from app.middleware.csrf import websocket_origin_allowed
from app.security.cloudflare_access import (
    CloudflareAccessInvalid,
    CloudflareAccessUnavailable,
    cloudflare_tunnel_host_allowed,
    require_cloudflare_access,
)

router = APIRouter()


def _get_user_from_ws_token(db: Session, token: str | None):
    if not token:
        return None
    try:
        user = get_user_from_token(token, db)
    except HTTPException:
        return None
    if getattr(user, "force_password_change", False):
        return None
    return user


def _get_vm_for_user(
    db: Session,
    user: User,
    vm_id: int,
    organization: OrganizationContext,
    operation: str,
):
    try:
        return get_console_vm_for_user(
            db,
            user=user,
            vm_id=vm_id,
            organization=organization,
            operation=operation,
        )
    except HTTPException:
        return None


@router.websocket("/vms/{id}/console/ssh/ws")
async def ssh_ws(id: int, websocket: WebSocket, db: Session = Depends(get_db)):
    if not cloudflare_tunnel_host_allowed(websocket.headers):
        await websocket.close(code=1008, reason="Invalid Host header")
        return
    try:
        await require_cloudflare_access(websocket.headers)
    except CloudflareAccessInvalid:
        await websocket.close(code=1008, reason="Cloudflare Access required")
        return
    except (CloudflareAccessUnavailable, ValueError):
        await websocket.close(code=1013, reason="Cloudflare Access unavailable")
        return
    if not websocket_origin_allowed(websocket):
        await websocket.close(code=1008, reason="Untrusted origin")
        return
    if not settings.ssh_terminal_enabled:
        await websocket.close(code=1008, reason="SSH terminal is disabled")
        return
    token = websocket.cookies.get(settings.auth_cookie_name)
    user = _get_user_from_ws_token(db, token)
    if not user:
        await websocket.close(code=1008, reason="Invalid token")
        return
    requested = websocket.query_params.get("organization_id")
    try:
        organization = resolve_organization_context(
            db, user, int(requested) if requested else None
        )
    except (ValueError, HTTPException):
        await websocket.close(code=1008, reason="Invalid organization")
        return
    vm = _get_vm_for_user(db, user, id, organization, "terminal")
    if not vm:
        await websocket.close(code=1008, reason="Forbidden")
        return
    await ConsoleWsService(db).ssh_ws(
        websocket,
        user,
        vm,
        auth_token=token,
        organization_id=organization.id,
    )


@router.websocket("/vms/{id}/console/novnc/ws")
async def novnc_ws(id: int, websocket: WebSocket, db: Session = Depends(get_db)):
    if not cloudflare_tunnel_host_allowed(websocket.headers):
        await websocket.close(code=1008, reason="Invalid Host header")
        return
    try:
        await require_cloudflare_access(websocket.headers)
    except CloudflareAccessInvalid:
        await websocket.close(code=1008, reason="Cloudflare Access required")
        return
    except (CloudflareAccessUnavailable, ValueError):
        await websocket.close(code=1013, reason="Cloudflare Access unavailable")
        return
    if not websocket_origin_allowed(websocket):
        await websocket.close(code=1008, reason="Untrusted origin")
        return
    token = websocket.cookies.get(settings.auth_cookie_name)
    user = _get_user_from_ws_token(db, token)
    if not user:
        await websocket.close(code=1008, reason="Invalid token")
        return
    requested = websocket.query_params.get("organization_id")
    try:
        organization = resolve_organization_context(
            db, user, int(requested) if requested else None
        )
    except (ValueError, HTTPException):
        await websocket.close(code=1008, reason="Invalid organization")
        return
    vm = _get_vm_for_user(db, user, id, organization, "console")
    if not vm:
        await websocket.close(code=1008, reason="Forbidden")
        return
    await ConsoleWsService(db).novnc_ws(
        websocket,
        user,
        vm,
        auth_token=token,
        organization_id=organization.id,
    )


@router.websocket("/vms/{id}/console/serial/ws")
async def serial_ws(id: int, websocket: WebSocket, db: Session = Depends(get_db)):
    if not cloudflare_tunnel_host_allowed(websocket.headers):
        await websocket.close(code=1008, reason="Invalid Host header")
        return
    try:
        await require_cloudflare_access(websocket.headers)
    except CloudflareAccessInvalid:
        await websocket.close(code=1008, reason="Cloudflare Access required")
        return
    except (CloudflareAccessUnavailable, ValueError):
        await websocket.close(code=1013, reason="Cloudflare Access unavailable")
        return
    if not websocket_origin_allowed(websocket):
        await websocket.close(code=1008, reason="Untrusted origin")
        return
    token = websocket.cookies.get(settings.auth_cookie_name)
    user = _get_user_from_ws_token(db, token)
    if not user:
        await websocket.close(code=1008, reason="Invalid token")
        return
    requested = websocket.query_params.get("organization_id")
    try:
        organization = resolve_organization_context(
            db, user, int(requested) if requested else None
        )
    except (ValueError, HTTPException):
        await websocket.close(code=1008, reason="Invalid organization")
        return
    vm = _get_vm_for_user(db, user, id, organization, "terminal")
    if not vm:
        await websocket.close(code=1008, reason="Forbidden")
        return
    await ConsoleWsService(db).serial_ws(
        websocket,
        user,
        vm,
        auth_token=token,
        organization_id=organization.id,
    )


@router.websocket("/vms/{id}/console/guacamole/{protocol}/ws")
async def guacamole_ws(
    id: int, protocol: str, websocket: WebSocket, db: Session = Depends(get_db)
):
    if not cloudflare_tunnel_host_allowed(websocket.headers):
        await websocket.close(code=1008, reason="Invalid Host header")
        return
    try:
        await require_cloudflare_access(websocket.headers)
    except CloudflareAccessInvalid:
        await websocket.close(code=1008, reason="Cloudflare Access required")
        return
    except (CloudflareAccessUnavailable, ValueError):
        await websocket.close(code=1013, reason="Cloudflare Access unavailable")
        return
    if not websocket_origin_allowed(websocket):
        await websocket.close(code=1008, reason="Untrusted origin")
        return
    token = websocket.cookies.get(settings.auth_cookie_name)
    user = _get_user_from_ws_token(db, token)
    if not user:
        await websocket.close(code=1008, reason="Invalid token")
        return
    requested = websocket.query_params.get("organization_id")
    try:
        organization = resolve_organization_context(
            db, user, int(requested) if requested else None
        )
    except (ValueError, HTTPException):
        await websocket.close(code=1008, reason="Invalid organization")
        return
    operation = {"vnc": "console", "rdp": "rdp", "ssh": "terminal"}.get(protocol)
    if not operation or "guacamole" not in websocket.scope.get("subprotocols", []):
        await websocket.close(code=1008, reason="Unsupported connection method")
        return
    vm = _get_vm_for_user(db, user, id, organization, operation)
    if not vm:
        await websocket.close(code=1008, reason="Forbidden")
        return
    from app.services.guacamole_console import GuacamoleConsole

    await GuacamoleConsole(db).connect(
        websocket, user, vm, protocol, token, organization.id
    )
