from sqlalchemy import (
    CheckConstraint,
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    func,
    Boolean,
    UniqueConstraint,
    Text,
    Index,
    text,
)
from sqlalchemy.orm import relationship
from app.db.session import Base


class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        UniqueConstraint("slug", name="organizations_slug_key"),
        Index("ix_organizations_slug", "slug", unique=True),
    )
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    slug = Column(String(80), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), nullable=False)


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "user_id", name="uq_organization_membership_user"
        ),
        CheckConstraint(
            "role IN ('student', 'instructor', 'admin', 'owner')",
            name="ck_organization_membership_role",
        ),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(32), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), nullable=False)

    organization = relationship("Organization", foreign_keys=[organization_id])
    user = relationship("User", foreign_keys=[user_id])


class DeploymentUpdateSettings(Base):
    __tablename__ = "deployment_update_settings"
    id = Column(Integer, primary_key=True)
    branch = Column(String(120), nullable=False, default="main")
    channel = Column(String(32), nullable=False, default="stable")
    automatic_updates = Column(Boolean, nullable=False, default=False)
    check_interval_minutes = Column(Integer, nullable=False, default=360)
    maintenance_hour_utc = Column(Integer, nullable=False, default=7)
    last_checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), nullable=False)


class DeploymentUpdateRun(Base):
    __tablename__ = "deployment_update_runs"
    id = Column(Integer, primary_key=True)
    requested_by = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False, index=True)
    from_version = Column(String(64), nullable=True)
    to_version = Column(String(64), nullable=True)
    backup_path = Column(String(512), nullable=True)
    details = Column(String(2048), nullable=True)
    agent_operation_id = Column(String(128), nullable=True, index=True)
    started_at = Column(DateTime, server_default=func.now(), nullable=False)
    finished_at = Column(DateTime, nullable=True)


class VmidAllocator(Base):
    __tablename__ = "vmid_allocators"
    __table_args__ = (
        UniqueConstraint("scope", name="vmid_allocators_scope_key"),
        Index("ix_vmid_allocators_scope", "scope", unique=True),
    )
    id = Column(Integer, primary_key=True)
    scope = Column(String(64), nullable=False)
    next_value = Column(Integer, nullable=False, default=200000)
    updated_at = Column(DateTime, server_default=func.now(), nullable=False)


class DurableOperation(Base):
    __tablename__ = "durable_operations"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_key", name="uq_durable_operations_idempotency_key"
        ),
        CheckConstraint(
            "state IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_durable_operations_state",
        ),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=True, index=True
    )
    requested_by = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    operation_type = Column(String(64), nullable=False, index=True)
    target_type = Column(String(64), nullable=False)
    target_id = Column(String(128), nullable=True)
    idempotency_key = Column(String(128), nullable=False)
    state = Column(String(32), nullable=False, default="queued", index=True)
    payload_json = Column(Text, nullable=False, default="{}")
    result_json = Column(Text, nullable=True)
    proxmox_upid = Column(String(255), nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    lease_owner = Column(String(128), nullable=True, index=True)
    lease_expires_at = Column(DateTime, nullable=True, index=True)
    run_after = Column(DateTime, nullable=True, index=True)
    error = Column(String(2048), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), nullable=False)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    display_name = Column(String(120), nullable=True)
    is_active = Column(Boolean, default=True)
    force_password_change = Column(Boolean, default=False)
    token_version = Column(Integer, nullable=False, default=1)
    password_changed_at = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    role = Column(String(50), nullable=True)  # deprecated: compatibility only

    role_rel = relationship("Role", foreign_keys=[role_id])


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        UniqueConstraint("token_id", name="auth_sessions_token_id_key"),
        Index("ix_auth_sessions_token_id", "token_id", unique=True),
    )
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_id = Column(String(64), nullable=False)
    user_agent = Column(String(255), nullable=True)
    client_ip = Column(String(64), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    last_seen_at = Column(DateTime, server_default=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked_at = Column(DateTime, nullable=True, index=True)
    revoke_reason = Column(String(64), nullable=True)

    user = relationship("User", foreign_keys=[user_id])


class AuthLoginAttempt(Base):
    __tablename__ = "auth_login_attempts"
    key_hash = Column(String(64), primary_key=True)
    failures = Column(Integer, nullable=False, default=0)
    first_failure_at = Column(DateTime, nullable=False)
    blocked_until = Column(DateTime, nullable=True, index=True)
    updated_at = Column(DateTime, server_default=func.now(), nullable=False)


class VMTemplate(Base):
    __tablename__ = "vm_templates"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "name", name="uq_vm_templates_organization_name"
        ),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=False, index=True
    )
    proxmox_cluster_id = Column(
        Integer, ForeignKey("proxmox_clusters.id"), nullable=True, index=True
    )
    name = Column(String(100), nullable=False)
    proxmox_node = Column(String(50), nullable=False)
    source_vmid = Column(Integer, nullable=False)
    enabled = Column(Boolean, default=True)


class TemplateGuestCredential(Base):
    __tablename__ = "template_guest_credentials"
    template_id = Column(Integer, ForeignKey("vm_templates.id"), primary_key=True)
    encrypted_credentials = Column(Text, nullable=False)
    auto_connect = Column(Boolean, nullable=False, default=True, server_default="true")
    student_visible = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    revision = Column(Integer, nullable=False, default=1, server_default="1")


class Permission(Base):
    __tablename__ = "permissions"
    __table_args__ = (
        UniqueConstraint("user_id", "template_id", name="uq_permissions_user_template"),
    )
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("vm_templates.id"), nullable=False)


class StudentVM(Base):
    __tablename__ = "student_vms"
    __table_args__ = (
        UniqueConstraint(
            "proxmox_cluster_id", "vmid", name="uq_student_vms_cluster_vmid"
        ),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=False, index=True
    )
    proxmox_cluster_id = Column(
        Integer, ForeignKey("proxmox_clusters.id"), nullable=True, index=True
    )
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("vm_templates.id"), nullable=False)
    vm_name = Column(String(100), nullable=False)
    vmid = Column(Integer, nullable=False)
    proxmox_node = Column(String(50), nullable=False)
    status = Column(String(20), default="provisioning")
    operating_system = Column(String(50), nullable=True)
    access_protocols = Column(String(255), nullable=True)
    ssh_enabled = Column(Boolean, default=True)
    rdp_enabled = Column(Boolean, default=False)
    spice_enabled = Column(Boolean, default=False)
    console_enabled = Column(Boolean, default=True)
    default_username = Column(String(100), nullable=True)
    assigned_ip = Column(String(64), nullable=True)
    hostname = Column(String(255), nullable=True)
    ssh_username = Column(String(100), nullable=True)
    ssh_auth_method = Column(String(50), nullable=True)
    ssh_port = Column(Integer, default=22)
    created_at = Column(DateTime, server_default=func.now())
    deleted_at = Column(DateTime, nullable=True, index=True)


class VMRemoteProfile(Base):
    __tablename__ = "vm_remote_profiles"
    vm_id = Column(Integer, ForeignKey("student_vms.id"), primary_key=True)
    protocol = Column(String(8), nullable=False)
    address = Column(String(64), nullable=False)
    port = Column(Integer, nullable=False)
    mac_address = Column(String(17), nullable=False)
    server_identity = Column(Text, nullable=False)
    encrypted_credentials = Column(Text, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    revision = Column(Integer, nullable=False, default=1, server_default="1")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=True, index=True
    )
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    target_type = Column(String(50), nullable=False)
    target_id = Column(String(100), nullable=False)
    outcome = Column(String(32), nullable=False, default="success")
    message = Column(String(512), nullable=True)
    request_id = Column(String(100), nullable=True, index=True)
    source_ip = Column(String(64), nullable=True)
    metadata_json = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class ConnectionLaunch(Base):
    __tablename__ = "connection_launches"
    id = Column(Integer, primary_key=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vm_id = Column(Integer, ForeignKey("student_vms.id"), nullable=False)
    protocol = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="success")
    details = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class VMSession(Base):
    __tablename__ = "vm_sessions"
    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vm_id = Column(Integer, ForeignKey("student_vms.id"), nullable=False)
    pool_id = Column(Integer, nullable=True)
    connection_launch_id = Column(
        Integer, ForeignKey("connection_launches.id"), nullable=True
    )
    protocol = Column(String(50), nullable=False)
    state = Column(String(32), nullable=False)
    node = Column(String(50), nullable=True)
    proxmox_vmid = Column(Integer, nullable=True)
    started_at = Column(DateTime, server_default=func.now(), nullable=False)
    launched_at = Column(DateTime, nullable=True)
    disconnected_at = Column(DateTime, nullable=True)
    expired_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    last_heartbeat_at = Column(DateTime, nullable=True)
    failure_reason = Column(String(255), nullable=True)
    client_ip = Column(String(64), nullable=True)
    user_agent = Column(String(255), nullable=True)
    request_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), nullable=False)


class TelemetryEvent(Base):
    __tablename__ = "telemetry_events"
    id = Column(Integer, primary_key=True)
    event_type = Column(String(64), nullable=False, index=True)
    severity = Column(String(20), nullable=False, default="info", index=True)
    source = Column(String(64), nullable=False)
    user_id = Column(Integer, nullable=True, index=True)
    vm_id = Column(Integer, nullable=True, index=True)
    session_id = Column(Integer, nullable=True, index=True)
    request_id = Column(String(100), nullable=True, index=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)


class DesktopPool(Base):
    __tablename__ = "desktop_pools"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "name", name="uq_desktop_pools_organization_name"
        ),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=False, index=True
    )
    name = Column(String(120), nullable=False, index=True)
    description = Column(String(255), nullable=True)
    pool_type = Column(String(32), nullable=False, index=True)
    template_vmid = Column(Integer, nullable=True)
    template_node = Column(String(50), nullable=True)
    default_protocol = Column(String(50), nullable=False)
    target_node = Column(String(50), nullable=True)
    storage = Column(String(100), nullable=True)
    bridge = Column(String(100), nullable=True)
    vlan_tag = Column(Integer, nullable=True)
    vmid_start = Column(Integer, nullable=True)
    vmid_end = Column(Integer, nullable=True)
    naming_pattern = Column(String(100), nullable=True)
    desired_size = Column(Integer, nullable=False, default=0)
    maintenance_mode = Column(Boolean, nullable=False, default=False, index=True)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), nullable=False)


class WorkerRun(Base):
    __tablename__ = "worker_runs"
    id = Column(Integer, primary_key=True)
    worker_name = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, index=True)
    started_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    finished_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    summary_json = Column(Text, nullable=True)
    error = Column(String(255), nullable=True)
    request_id = Column(String(100), nullable=True)


class ProxmoxCluster(Base):
    __tablename__ = "proxmox_clusters"
    __table_args__ = (
        Index(
            "uq_proxmox_clusters_single_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False, unique=True)
    api_url = Column(String(255), nullable=False)
    verify_ssl = Column(Boolean, nullable=False, default=True)
    auth_mode = Column(String(32), nullable=False, default="token")
    root_username = Column(String(120), nullable=True)
    token_user = Column(String(120), nullable=True)
    token_id = Column(String(120), nullable=True)
    encrypted_token_secret = Column(Text, nullable=True)
    token_created_by_app = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=False)
    last_validated_at = Column(DateTime, nullable=True)
    last_validation_status = Column(String(32), nullable=True)
    last_validation_error = Column(String(512), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), nullable=False)


class ProxmoxNode(Base):
    __tablename__ = "proxmox_nodes"
    id = Column(Integer, primary_key=True)
    cluster_id = Column(
        Integer, ForeignKey("proxmox_clusters.id"), nullable=False, index=True
    )
    node_name = Column(String(120), nullable=False)
    status = Column(String(32), nullable=True)
    cpu_total = Column(Integer, nullable=True)
    cpu_used = Column(Integer, nullable=True)
    memory_total = Column(Integer, nullable=True)
    memory_used = Column(Integer, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    raw_summary_json = Column(Text, nullable=True)


class ProxmoxClusterDefault(Base):
    __tablename__ = "proxmox_cluster_defaults"
    __table_args__ = (
        UniqueConstraint("cluster_id", name="uq_proxmox_cluster_defaults_cluster_id"),
    )
    id = Column(Integer, primary_key=True)
    cluster_id = Column(
        Integer,
        ForeignKey("proxmox_clusters.id"),
        nullable=False,
        index=True,
    )
    default_node = Column(String(120), nullable=True)
    default_storage = Column(String(120), nullable=True)
    default_bridge = Column(String(120), nullable=True)
    default_template_vmid = Column(Integer, nullable=True)
    clone_mode = Column(String(50), nullable=True)
    placement_policy = Column(String(50), nullable=True)
    notes = Column(String(500), nullable=True)


class Group(Base):
    __tablename__ = "groups"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_groups_organization_name"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=False, index=True
    )
    name = Column(String(120), nullable=False)
    description = Column(String(255), nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), nullable=False)


class GroupMembership(Base):
    __tablename__ = "group_memberships"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_memberships_group_user"),
    )
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role_in_group = Column(String(50), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class GroupTemplatePermission(Base):
    __tablename__ = "group_template_permissions"
    __table_args__ = (
        UniqueConstraint(
            "group_id",
            "template_id",
            name="uq_group_template_permissions_group_template",
        ),
    )
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False, index=True)
    template_id = Column(
        Integer, ForeignKey("vm_templates.id"), nullable=False, index=True
    )
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class AssetCatalog(Base):
    __tablename__ = "asset_catalog"
    id = Column(Integer, primary_key=True)
    asset_type = Column(
        String(32), nullable=False, index=True
    )  # iso|ct_template|vm_template
    name = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=True)
    storage_id = Column(String(120), nullable=True)
    content_type = Column(String(32), nullable=True)  # iso|vztmpl
    source_node = Column(String(120), nullable=True)
    source_vmid = Column(Integer, nullable=True)
    source_url = Column(String(1024), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    sha256 = Column(String(128), nullable=True)
    is_required = Column(Boolean, nullable=False, default=True)
    sync_method = Column(String(64), nullable=False, default="download-url")
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), nullable=False)


class AssetNodeState(Base):
    __tablename__ = "asset_node_state"
    __table_args__ = (
        UniqueConstraint(
            "asset_id", "node_name", name="uq_asset_node_state_asset_node"
        ),
    )
    id = Column(Integer, primary_key=True)
    asset_id = Column(
        Integer, ForeignKey("asset_catalog.id"), nullable=False, index=True
    )
    node_name = Column(String(120), nullable=False, index=True)
    state = Column(String(32), nullable=False, default="missing")
    target_vmid = Column(Integer, nullable=True)
    target_volid = Column(String(255), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    sha256 = Column(String(128), nullable=True)
    last_checked_at = Column(DateTime, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)
    last_error = Column(String(1024), nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), nullable=False)


class AssetSyncJob(Base):
    __tablename__ = "asset_sync_jobs"
    id = Column(Integer, primary_key=True)
    asset_id = Column(Integer, ForeignKey("asset_catalog.id"), nullable=True)
    target_node = Column(String(120), nullable=False)
    state = Column(String(32), nullable=False, default="queued")
    method = Column(String(64), nullable=False)
    source_node = Column(String(120), nullable=True)
    source_vmid = Column(Integer, nullable=True)
    target_vmid = Column(Integer, nullable=True)
    proxmox_upid = Column(String(255), nullable=True)
    lease_owner = Column(String(128), nullable=True, index=True)
    lease_expires_at = Column(DateTime, nullable=True, index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    error = Column(String(2048), nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class AssetSyncJobEvent(Base):
    __tablename__ = "asset_sync_job_events"
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("asset_sync_jobs.id"), nullable=False)
    level = Column(String(16), nullable=False, default="info")
    message = Column(String(2048), nullable=False)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class Class(Base):
    __tablename__ = "classes"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "name", name="uq_classes_organization_name"
        ),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=False, index=True
    )
    name = Column(String(120), nullable=False)
    term = Column(String(120), nullable=True)
    instructor_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    join_code = Column(String(64), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), nullable=False)


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("class_id", "user_id", name="uq_enrollments_class_user"),
    )
    id = Column(Integer, primary_key=True)
    class_id = Column(
        Integer,
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(32), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class Lab(Base):
    __tablename__ = "labs"
    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=False, index=True
    )
    class_id = Column(
        Integer,
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(120), nullable=False)
    description = Column(String(255), nullable=True)
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    default_pool_id = Column(
        Integer, ForeignKey("desktop_pools.id"), nullable=False, index=True
    )
    student_can_reset = Column(Boolean, nullable=False, default=False)
    student_can_power_off = Column(Boolean, nullable=False, default=False)
    terminal_enabled = Column(Boolean, nullable=False, default=False)
    console_enabled = Column(Boolean, nullable=False, default=False)
    rdp_enabled = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), nullable=False)


class LabRun(Base):
    __tablename__ = "lab_runs"
    __table_args__ = (
        CheckConstraint(
            "state IN ('draft', 'scheduled', 'active', 'ended', 'cancelled')",
            name="ck_lab_runs_state",
        ),
        CheckConstraint(
            "max_vms_per_student >= 1 AND max_vms_per_student <= 10",
            name="ck_lab_runs_vm_quota",
        ),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=False, index=True
    )
    lab_id = Column(Integer, ForeignKey("labs.id"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    state = Column(String(32), nullable=False, default="draft", index=True)
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    max_vms_per_student = Column(Integer, nullable=False, default=1)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    activated_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), nullable=False)


class LabAssignment(Base):
    __tablename__ = "lab_assignments"
    __table_args__ = (
        UniqueConstraint(
            "lab_run_id",
            "user_id",
            "slot_index",
            name="uq_lab_assignments_run_user_slot",
        ),
        UniqueConstraint("student_vm_id", name="lab_assignments_student_vm_id_key"),
        Index("ix_lab_assignments_student_vm_id", "student_vm_id", unique=True),
        CheckConstraint(
            "status IN ('assigned', 'ready', 'expired', 'revoked')",
            name="ck_lab_assignments_status",
        ),
        CheckConstraint("slot_index >= 1", name="ck_lab_assignments_slot"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=False, index=True
    )
    lab_run_id = Column(Integer, ForeignKey("lab_runs.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    template_id = Column(
        Integer, ForeignKey("vm_templates.id"), nullable=False, index=True
    )
    slot_index = Column(Integer, nullable=False, default=1)
    status = Column(String(32), nullable=False, default="assigned", index=True)
    student_vm_id = Column(Integer, ForeignKey("student_vms.id"), nullable=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), nullable=False)


class ProxmoxHostAccess(Base):
    __tablename__ = "proxmox_host_access"
    __table_args__ = (
        UniqueConstraint("cluster_id", "node_name", name="uq_host_access_cluster_node"),
    )
    id = Column(Integer, primary_key=True)
    cluster_id = Column(
        Integer,
        ForeignKey("proxmox_clusters.id", ondelete="CASCADE"),
        nullable=False,
    )
    node_name = Column(String(120), nullable=False)
    runner_user = Column(String(120), nullable=False, default="labgoblin-runner")
    auth_method = Column(String(32), nullable=False, default="ssh_key")
    encrypted_private_key = Column(String, nullable=True)
    key_ref = Column(String(255), nullable=True)
    public_key_fingerprint = Column(String(255), nullable=True)
    capabilities_json = Column(String, nullable=True)
    status = Column(String(32), nullable=False, default="api_only")
    last_checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), nullable=False)
