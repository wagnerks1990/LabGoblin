from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, SecretStr, model_validator


class SetupStudent(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    email: str = Field(min_length=3, max_length=255)
    password: SecretStr = Field(min_length=1, max_length=4096)
    display_name: str = Field(default="", max_length=120)


class LabSetupWrite(BaseModel):
    request_id: UUID
    expected_etag: str | None = None
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=255)
    class_id: int | None = None
    class_name: str = Field(default="", max_length=120)
    term: str = Field(default="", max_length=120)
    pool_id: int | None = None
    template_id: int | None = None
    student_ids: list[int] = Field(default_factory=list, max_length=500)
    new_students: list[SetupStudent] = Field(default_factory=list, max_length=100)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    slots: int = Field(default=1, ge=1, le=10)
    console_enabled: bool = True
    rdp_enabled: bool = True
    terminal_enabled: bool = True
    student_can_power_off: bool = False
    student_can_reset: bool = False
    state: Literal["draft", "scheduled", "active"] = "draft"
    reviewed: bool = False

    @model_validator(mode="after")
    def validate_choices(self):
        if not self.name.strip():
            raise ValueError("Enter a lab name")
        if not self.class_id and not self.class_name.strip():
            raise ValueError("Choose a class or enter a new class name")
        if not self.pool_id and not self.template_id:
            raise ValueError("Choose an existing pool or a template")
        if self.pool_id and self.template_id:
            raise ValueError("Choose either a pool or a template")
        if not self.reviewed:
            raise ValueError("Review the setup before saving")
        return self


class LabSetupOut(BaseModel):
    run_id: int
    lab_id: int
    name: str
    description: str
    class_id: int
    class_name: str
    term: str
    pool_id: int
    pool_name: str
    student_ids: list[int]
    starts_at: datetime | None
    ends_at: datetime | None
    slots: int
    console_enabled: bool
    rdp_enabled: bool
    terminal_enabled: bool
    student_can_power_off: bool
    student_can_reset: bool
    state: str
    etag: str
    assignment_count: int


class SetupChoice(BaseModel):
    id: int
    name: str
    enabled: bool = True
    term: str | None = None
    source_vmid: int | None = None
    template_vmid: int | None = None
    maintenance_mode: bool = False
    state: str | None = None
    assignment_count: int = 0
    max_vms_per_student: int = 1


class SetupMember(BaseModel):
    user_id: int
    username: str
    role: str
    is_active: bool


class LabSetupCatalog(BaseModel):
    classes: list[SetupChoice]
    pools: list[SetupChoice]
    templates: list[SetupChoice]
    members: list[SetupMember]
    runs: list[SetupChoice]
