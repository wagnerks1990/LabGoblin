from typing import Literal
from uuid import UUID
from urllib.parse import urlsplit

from pydantic import BaseModel, EmailStr, Field, SecretStr, field_validator


class EmailConfiguration(BaseModel):
    enabled: bool = False
    receiving_enabled: bool = False
    notifications_enabled: bool = False
    public_origin: str = Field(max_length=255)
    sender: EmailStr
    support_address: EmailStr
    api_key: SecretStr | None = None
    webhook_secret: SecretStr | None = None

    @field_validator("public_origin")
    @classmethod
    def validate_origin(cls, origin):
        value = urlsplit(origin)
        if (
            value.scheme != "https"
            or not value.hostname
            or value.username
            or value.password
            or value.path not in {"", "/"}
            or value.query
            or value.fragment
            or value.port not in {None, 443}
        ):
            raise ValueError("Public origin must be an exact HTTPS origin")
        return f"https://{value.hostname.lower()}"


class RecoveryRequest(BaseModel):
    email: EmailStr


class RecoveryComplete(RecoveryRequest):
    code: SecretStr
    new_password: SecretStr


class InvitationRequest(BaseModel):
    user_id: int = Field(gt=0)


class EmailReply(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    request_id: UUID


class EmailPreferences(BaseModel):
    notifications_enabled: bool = True


class InboxState(BaseModel):
    state: Literal["received", "archived"]
