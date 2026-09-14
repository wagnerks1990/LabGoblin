from pydantic import BaseModel, Field, SecretStr


class ConsoleLaunchResponse(BaseModel):
    type: str
    url: str | None = None
    host: str | None = None
    rdp_file: str | None = None
    novnc_url: str | None = None
    port: int | None = None
    vmid: int | None = None
    node: str | None = None
    launch_url: str | None = None
    session_id: int | None = None
    protocol: str | None = None
    state: str | None = None
    reconnect_token: str | None = None
    heartbeat_interval_seconds: int | None = None
    expires_at: int | None = None


class ConnectionOptionsResponse(BaseModel):
    vm_id: int
    vm_name: str
    operating_system: str
    running: bool
    vnc: bool
    terminal: bool
    rdp: bool
    native_rdp: bool
    can_configure: bool
    hint: str


class RemoteProfileRequest(BaseModel):
    address: str = Field(max_length=64)
    port: int = Field(ge=1, le=65535)
    mac_address: str = Field(max_length=17)
    server_identity: str = Field(max_length=8192)
    username: str = Field(default="", max_length=128)
    password: SecretStr = Field(default=SecretStr(""), max_length=4096)
    use_template_credentials: bool = False
    domain: str = Field(default="", max_length=128)
    enabled: bool = True


class GuestAddressObservation(BaseModel):
    address: str
    mac_address: str
    matches_cloud_init: bool


class RemoteProfileResponse(BaseModel):
    configured: bool
    protocol: str | None = None
    address: str | None = None
    port: int | None = None
    mac_address: str | None = None
    server_identity: str | None = None
    enabled: bool = False
    observed_addresses: list[GuestAddressObservation] = Field(default_factory=list)
    discovery_hint: str | None = None
    template_credentials_available: bool = False
    use_template_credentials: bool = False


class RemoteProbeRequest(BaseModel):
    address: str = Field(max_length=64)
    port: int = Field(ge=1, le=65535)
    confirm_reserved_address: bool


class RemoteProbeResponse(BaseModel):
    protocol: str
    reachable: bool
    server_identity: str | None = None
    mac_addresses: list[str]
    hint: str
