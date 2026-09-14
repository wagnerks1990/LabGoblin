from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json
from app.models.models import VMRemoteProfile, AuditLog
from app.services.proxmox import ProxmoxClient
from app.services.remote_capabilities import inspect_console, guest_os
from app.services.remote_profile import (
    profile_parameters,
    validate_address,
    validate_identity,
    vm_macs,
)
from app.services.connection_checks import check_profile, inspect_rdp, inspect_ssh
from app.services.secret_crypto import encrypt_secret
from app.services.guest_discovery import discover_guest_addresses
from app.services.rbac import get_role_name
from app.db.tx import safe_commit
from app.schemas.console import (
    ConnectionOptionsResponse,
    RemoteProfileRequest,
    RemoteProfileResponse,
    RemoteProbeRequest,
    RemoteProbeResponse,
)

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.models import User
from app.schemas.console import ConsoleLaunchResponse
from app.services.console_access import get_console_vm_for_user
from app.services.console_service import ConsoleService
from app.services.organization_access import (
    OrganizationContext,
    get_current_organization,
)

router = APIRouter()


def _get_vm_for_user(
    db: Session,
    user: User,
    vm_id: int,
    organization: OrganizationContext,
    operation: str,
):
    return get_console_vm_for_user(
        db,
        user=user,
        vm_id=vm_id,
        organization=organization,
        operation=operation,
    )


@router.get("/vms/{id}/console/terminal-url", response_model=ConsoleLaunchResponse)
async def console_terminal_url(
    id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(get_current_organization),
):
    vm = _get_vm_for_user(db, user, id, organization, "terminal")
    return await ConsoleService(db).terminal_url(user, vm)


@router.get("/vms/{id}/console/rdp", response_model=ConsoleLaunchResponse)
async def console_rdp(
    id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(get_current_organization),
):
    vm = _get_vm_for_user(db, user, id, organization, "rdp")
    host = vm.assigned_ip or vm.hostname or vm.vm_name
    return {
        "type": "rdp",
        "host": host,
        "rdp_file": f"full address:s:{host}\nusername:s:{vm.default_username or 'student'}\nprompt for credentials:i:1\n",
    }


@router.get("/vms/{id}/console/spice", response_model=ConsoleLaunchResponse)
async def console_spice(
    id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(get_current_organization),
):
    raise HTTPException(status_code=501, detail="SPICE console is not supported")


@router.get("/vms/{id}/console/novnc", response_model=ConsoleLaunchResponse)
async def console_novnc(
    id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(get_current_organization),
):
    vm = _get_vm_for_user(db, user, id, organization, "console")
    return {
        "type": "novnc",
        "vmid": vm.vmid,
        "node": vm.proxmox_node,
        "launch_url": f"/console/{vm.id}",
    }


@router.get("/vms/{id}/console/options", response_model=ConnectionOptionsResponse)
async def connection_options(
    id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(get_current_organization),
):
    vm = _get_vm_for_user(db, user, id, organization, "view")
    proxmox = ProxmoxClient(cluster_id=vm.proxmox_cluster_id)
    capability = await inspect_console(db, vm, proxmox)

    def allowed(operation):
        try:
            _get_vm_for_user(db, user, id, organization, operation)
            return True
        except HTTPException:
            return False

    result = {
        "vm_id": vm.id,
        "vm_name": vm.vm_name,
        "operating_system": capability["operating_system"],
        "running": capability["running"],
        "vnc": capability["vnc"] and allowed("console"),
        "rdp": False,
        "terminal": False,
        "native_rdp": False,
        "can_configure": get_role_name(user) == "Admin",
        "hint": "Start the VM to connect."
        if not capability["running"]
        else "VNC uses the Proxmox console. RDP and SSH require an approved VM address and guest login; administrators can prepare them here.",
    }
    profile = db.get(VMRemoteProfile, vm.id)
    if profile and profile.enabled and capability["running"]:
        config = capability["_config"]
        try:
            profile_parameters(db, vm, config, capability["operating_system"])
            ready, hint = await check_profile(profile)
            result["hint"] = hint
            if profile.protocol == "rdp":
                result["rdp"] = ready and allowed("rdp")
                result["native_rdp"] = result["rdp"]
            elif profile.protocol == "ssh":
                result["terminal"] = ready and vm.ssh_enabled and allowed("terminal")
        except HTTPException as exc:
            result["hint"] = str(exc.detail)
    if result["vnc"]:
        from app.services.connection_checks import check_proxmox_vnc

        result["vnc"] = await check_proxmox_vnc(proxmox, vm)
        if not result["vnc"]:
            result["hint"] = (
                "Proxmox VNC authentication failed. Ask an administrator to check VM.Console permission and cluster connectivity."
            )
    from app.services.guacamole import check_guacamole_reachable

    gateway_ready, gateway_hint = await check_guacamole_reachable()
    if not gateway_ready:
        result.update(vnc=False, rdp=False, terminal=False, hint=gateway_hint)
    return result


def _profile_admin(db, user, id, organization):
    if get_role_name(user) != "Admin":
        raise HTTPException(
            403, "A platform administrator must approve guest connection destinations."
        )
    return _get_vm_for_user(db, user, id, organization, "view")


@router.get("/vms/{id}/console/profile", response_model=RemoteProfileResponse)
async def get_remote_profile(
    id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(get_current_organization),
):
    vm = _profile_admin(db, user, id, organization)
    profile = db.get(VMRemoteProfile, vm.id)
    proxmox = ProxmoxClient(cluster_id=vm.proxmox_cluster_id)
    capability = await inspect_console(db, vm, proxmox)
    addresses, hint = await discover_guest_addresses(proxmox, vm, capability["_config"])
    observations = {"observed_addresses": addresses, "discovery_hint": hint}
    if not profile:
        return {
            "configured": False,
            "address": addresses[0]["address"] if len(addresses) == 1 else None,
            **observations,
        }
    return {
        "configured": True,
        "protocol": profile.protocol,
        "address": profile.address,
        "port": profile.port,
        "mac_address": profile.mac_address,
        "server_identity": profile.server_identity,
        "enabled": profile.enabled,
        **observations,
    }


@router.post("/vms/{id}/console/probe", response_model=RemoteProbeResponse)
async def probe_remote_profile(
    id: int,
    payload: RemoteProbeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(get_current_organization),
):
    vm = _profile_admin(db, user, id, organization)
    if not payload.confirm_reserved_address:
        raise HTTPException(
            422, "Confirm that this address is reserved for this VM before probing."
        )
    address = validate_address(payload.address)
    proxmox = ProxmoxClient(cluster_id=vm.proxmox_cluster_id)
    config = (await inspect_console(db, vm, proxmox))["_config"]
    os_name = guest_os(config)
    if os_name not in {"windows", "linux"}:
        raise HTTPException(
            409, "Set the guest OS type in Proxmox before preparing remote access."
        )
    protocol = "rdp" if os_name == "windows" else "ssh"
    identity = None
    try:
        identity = await (
            inspect_rdp(address, payload.port)
            if protocol == "rdp"
            else inspect_ssh(address, payload.port)
        )
    except Exception:
        pass
    db.add(
        AuditLog(
            organization_id=organization.id,
            actor_id=user.id,
            action="remote_access_probe",
            target_type="student_vm",
            target_id=str(vm.id),
            message=f"{protocol} service probe",
        )
    )
    safe_commit(db)
    return {
        "protocol": protocol,
        "reachable": identity is not None,
        "server_identity": identity,
        "mac_addresses": sorted(vm_macs(config)),
        "hint": "Review the server identity before approving this connection."
        if identity
        else "Guest service is unavailable. Enable it in the guest and allow its port through the guest firewall.",
    }


@router.put("/vms/{id}/console/profile", response_model=RemoteProfileResponse)
async def save_remote_profile(
    id: int,
    payload: RemoteProfileRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization: OrganizationContext = Depends(get_current_organization),
):
    vm = _profile_admin(db, user, id, organization)
    address = validate_address(payload.address)
    config = (
        await inspect_console(db, vm, ProxmoxClient(cluster_id=vm.proxmox_cluster_id))
    )["_config"]
    os_name = guest_os(config)
    if os_name not in {"windows", "linux"}:
        raise HTTPException(409, "Unknown VM operating system")
    protocol = "rdp" if os_name == "windows" else "ssh"
    validate_identity(protocol, payload.server_identity)
    if payload.mac_address.lower() not in vm_macs(config):
        raise HTTPException(422, "Select a network adapter belonging to this VM.")
    profile = db.get(VMRemoteProfile, vm.id)
    if profile is None:
        profile = VMRemoteProfile(vm_id=vm.id, revision=0)
        db.add(profile)
    password = payload.password.get_secret_value()
    if not payload.username or not password:
        raise HTTPException(
            422, "A VM-specific guest username and password are required."
        )
    profile.protocol, profile.address, profile.port = protocol, address, payload.port
    profile.mac_address, profile.server_identity = (
        payload.mac_address.lower(),
        payload.server_identity,
    )
    profile.enabled = payload.enabled
    profile.revision += 1
    profile.encrypted_credentials = encrypt_secret(
        json.dumps(
            {
                "username": payload.username,
                "password": password,
                "domain": payload.domain,
            }
        )
    )
    vm.operating_system = os_name
    vm.rdp_enabled = protocol == "rdp" and payload.enabled
    vm.access_protocols = "novnc," + protocol
    db.add(
        AuditLog(
            organization_id=organization.id,
            actor_id=user.id,
            action="remote_access_configured",
            target_type="student_vm",
            target_id=str(vm.id),
            message="VM-bound guest connection profile updated",
        )
    )
    safe_commit(db)
    return {
        "configured": True,
        "protocol": protocol,
        "address": address,
        "port": profile.port,
        "mac_address": profile.mac_address,
        "server_identity": profile.server_identity,
        "enabled": profile.enabled,
    }
