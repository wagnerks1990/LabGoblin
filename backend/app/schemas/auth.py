from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr | None = None
    username: str | None = None
    password: str


class BootstrapAdminRequest(BaseModel):
    token: str
    username: str | None = None
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class SessionResponse(BaseModel):
    id: int
    current: bool = False
    client_ip: str | None = None
    user_agent: str | None = None
    created_at: str | None = None
    expires_at: str | None = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str
    role_id: int | None = None
    is_active: bool = True
    force_password_change: bool = False
