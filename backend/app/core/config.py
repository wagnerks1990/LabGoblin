import ipaddress
import re

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_DNS_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def _normalize_public_hostname(value: str) -> str:
    raw = value.strip()
    hostname = raw.lower()
    if raw != value or len(hostname) > 253 or "." not in hostname:
        raise ValueError("CLOUDFLARE_PUBLIC_HOSTNAME must be a DNS hostname")
    if any(not _DNS_LABEL.fullmatch(label) for label in hostname.split(".")):
        raise ValueError("CLOUDFLARE_PUBLIC_HOSTNAME must be a DNS hostname")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return hostname
    raise ValueError("CLOUDFLARE_PUBLIC_HOSTNAME must not be an IP address")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    password_min_length: int = 12
    login_max_failures: int = 5
    login_failure_window_seconds: int = 300
    login_lockout_seconds: int = 900
    bootstrap_admin_token: str | None = None
    auth_cookie_name: str = "labgoblin_session"
    auth_cookie_secure: bool = False
    cors_allowed_origins: str = ""
    browser_trusted_origins: str = ""

    cloudflare_tunnel_enabled: bool = False
    cloudflare_public_hostname: str = ""
    cloudflare_access_required: bool = False
    cloudflare_access_team_domain: str = ""
    cloudflare_access_audience: str = ""
    cloudflare_access_jwks_ttl_seconds: int = Field(default=3600, ge=30, le=86400)

    proxmox_base_url: str
    proxmox_token_id: str
    proxmox_token_secret: str
    proxmox_verify_ssl: bool = True
    proxmox_allow_insecure_tls: bool = False
    app_secret_key: str | None = None
    config_encryption_key: str | None = None

    lab_vm_ssh_username: str | None = None
    lab_vm_ssh_password: str | None = None
    lab_vm_ssh_known_hosts: str | None = None
    lab_vm_ssh_private_key_path: str | None = None

    guacd_host: str = "guacd"
    guacd_port: int = Field(default=4822, ge=1, le=65535)
    guacd_bridge_host: str = "api"
    guacamole_allowed_networks: str = ""

    guacamole_internal_url: str | None = None
    guacamole_base_url: str = "/guacamole"
    guacamole_admin_user: str | None = None
    guacamole_admin_password: str | None = None
    guacamole_datasource: str = "postgresql"
    guacamole_verify_ssl: bool = True

    ssh_terminal_enabled: bool = False

    heartbeat_timeout_seconds: int = 60
    session_reconnect_timeout_seconds: int = 180
    session_idle_timeout_seconds: int = 900

    reconnect_token_ttl_seconds: int = 300
    reconnect_token_secret: str | None = None

    worker_scheduler_enabled: bool = True
    session_cleanup_interval_seconds: int = 60
    health_poll_interval_seconds: int = 60
    reconciliation_interval_seconds: int = 300
    operation_poll_interval_seconds: int = 2
    operation_lease_seconds: int = 180
    operation_max_attempts: int = 3
    operation_task_timeout_seconds: int = 900
    operation_clone_timeout_seconds: int = 3600
    operation_delete_timeout_seconds: int = 900

    replay_store_backend: str = "memory"
    worker_lock_backend: str = "memory"
    redis_url: str = "redis://redis:6379/0"
    asset_source_node: str | None = None
    asset_source_iso_base_url: str | None = None
    asset_source_ct_base_url: str | None = None
    host_runner_enabled: bool = False
    host_runner_user: str = "labgoblin-runner"
    host_runner_private_key_path: str | None = None
    asset_sync_poll_interval_seconds: int = 3
    asset_sync_download_timeout_seconds: int = 7200
    asset_sync_lease_seconds: int = 180

    updater_socket_path: str = "/var/lib/labgoblin/updater/updater.sock"
    updater_token: str | None = None
    updater_repository: str = "https://github.com/wagnerks1990/labgoblin.git"
    updater_poll_interval_seconds: int = 900
    updater_allow_automatic: bool = False
    updater_require_signed_commits: bool = False

    @model_validator(mode="after")
    def validate_cloudflare_access(self):
        if self.cloudflare_tunnel_enabled:
            if not self.cloudflare_public_hostname.strip():
                raise ValueError(
                    "CLOUDFLARE_PUBLIC_HOSTNAME is required when "
                    "CLOUDFLARE_TUNNEL_ENABLED is true"
                )
            self.cloudflare_public_hostname = _normalize_public_hostname(
                self.cloudflare_public_hostname
            )
        if self.cloudflare_access_required and not (
            self.cloudflare_access_team_domain.strip()
            and self.cloudflare_access_audience.strip()
        ):
            raise ValueError(
                "CLOUDFLARE_ACCESS_TEAM_DOMAIN and CLOUDFLARE_ACCESS_AUDIENCE "
                "are required when CLOUDFLARE_ACCESS_REQUIRED is true"
            )
        return self


settings = Settings()
