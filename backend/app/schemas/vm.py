from datetime import datetime
from pydantic import BaseModel, Field
from app.schemas.console import GuestAddressObservation


class TemplateResponse(BaseModel):
    id: int
    name: str
    proxmox_node: str
    source_vmid: int
    enabled: bool = True


class TemplateCreateRequest(BaseModel):
    name: str
    proxmox_node: str
    source_vmid: int
    enabled: bool = True


class TemplateUpdateRequest(BaseModel):
    name: str | None = None
    proxmox_node: str | None = None
    source_vmid: int | None = None
    enabled: bool | None = None


class CreateVMRequest(BaseModel):
    template_id: int
    lab_name: str
    auto_start: bool = True
    assignment_id: int | None = None


class VMDisk(BaseModel):
    device: str
    capacity_bytes: int | None = None


class VMResources(BaseModel):
    cpu_count: int | None = None
    cpu_usage_percent: float | None = None
    memory_bytes: int | None = None
    memory_used_bytes: int | None = None
    disk_capacity_bytes: int | None = None
    disks: list[VMDisk] = Field(default_factory=list)
    uptime_seconds: int | None = None
    network_received_bytes: int | None = None
    network_sent_bytes: int | None = None
    disk_read_bytes: int | None = None
    disk_written_bytes: int | None = None


class VMResponse(BaseModel):
    id: int
    vm_name: str
    vmid: int
    status: str
    proxmox_node: str
    created_at: datetime | None = None
    operating_system: str | None = None
    access_protocols: str | None = None
    ssh_enabled: bool | None = None
    rdp_enabled: bool | None = None
    spice_enabled: bool | None = None
    console_enabled: bool | None = None
    default_username: str | None = None
    assigned_ip: str | None = None
    hostname: str | None = None
    resources: VMResources | None = None
    observed_addresses: list[GuestAddressObservation] = Field(default_factory=list)
    observed_at: datetime | None = None
    resource_warning: str | None = None
    discovery_hint: str | None = None
    ssh_username: str | None = None
    ssh_auth_method: str | None = None
    ssh_port: int | None = 22
    allowed_stop: bool | None = None
    allowed_delete: bool | None = None
    allowed_terminal: bool | None = None
    allowed_console: bool | None = None
    allowed_rdp: bool | None = None
    allowed_spice: bool | None = None
    assignment_expires_at: datetime | None = None


class VMCreateResponse(VMResponse):
    operation_id: int | None = None
    operation_state: str | None = None
    message: str | None = None


class VMOperationResponse(BaseModel):
    operation_id: int
    state: str
    vm_id: int
    message: str


class AuditLogResponse(BaseModel):
    id: int
    actor_id: int | None = None
    action: str
    target_type: str
    target_id: str
    outcome: str = "success"
    message: str | None = None
    request_id: str | None = None
    source_ip: str | None = None
    metadata_json: str | None = None
    created_at: datetime | None = None


class ConnectionLaunchResponse(BaseModel):
    id: int
    actor_id: int
    vm_id: int
    protocol: str
    status: str
    details: str | None = None
    created_at: datetime | None = None
