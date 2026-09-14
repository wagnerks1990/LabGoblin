from datetime import datetime
from pydantic import BaseModel


class ClassBase(BaseModel):
    name: str
    term: str | None = None
    instructor_id: int | None = None
    join_code: str | None = None


class ClassCreate(ClassBase):
    pass


class ClassPatch(BaseModel):
    name: str | None = None
    term: str | None = None
    instructor_id: int | None = None
    join_code: str | None = None


class ClassOut(ClassBase):
    id: int
    created_at: datetime
    updated_at: datetime


class EnrollmentCreate(BaseModel):
    user_id: int
    role: str | None = None


class EnrollmentOut(BaseModel):
    id: int
    class_id: int
    user_id: int
    role: str | None = None
    is_active: bool = True
    created_at: datetime


class LabBase(BaseModel):
    class_id: int
    name: str
    description: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    default_pool_id: int
    student_can_reset: bool = False
    student_can_power_off: bool = False
    terminal_enabled: bool = False
    console_enabled: bool = False
    rdp_enabled: bool = False


class LabCreate(LabBase):
    pass


class LabPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    default_pool_id: int | None = None
    student_can_reset: bool | None = None
    student_can_power_off: bool | None = None
    terminal_enabled: bool | None = None
    console_enabled: bool | None = None
    rdp_enabled: bool | None = None


class LabOut(LabBase):
    id: int
    created_at: datetime
    updated_at: datetime
    readiness_status: str | None = None
    placement_warning: str | None = None
    asset_ready_nodes: list[str] | None = None
    constrained_nodes: list[str] | None = None
    missing_templates_by_node: dict | None = None
    missing_isos_by_node: dict | None = None
    missing_ct_templates_by_node: dict | None = None
    vm_template_vmid_by_node: dict | None = None
    recommended_next_steps: list[str] | None = None
    assets_page_hint: str | None = None


class LabRunCreate(BaseModel):
    lab_id: int
    name: str
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    max_vms_per_student: int = 1


class LabRunOut(LabRunCreate):
    id: int
    organization_id: int
    state: str
    created_by: int
    activated_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    effective_open: bool = False
    assignment_count: int = 0


class LabRunStateChange(BaseModel):
    action: str
    confirmation: str | None = None


class LabAssignmentCreate(BaseModel):
    user_id: int
    template_id: int | None = None
    slot_index: int | None = None


class LabAssignmentBulkCreate(BaseModel):
    slots_per_student: int = 1


class LabAssignmentOut(BaseModel):
    id: int
    organization_id: int
    lab_run_id: int
    user_id: int
    template_id: int
    slot_index: int
    status: str
    student_vm_id: int | None = None
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    run_name: str | None = None
    lab_name: str | None = None
    template_name: str | None = None
    username: str | None = None
    can_provision: bool = False
    access_open: bool = False
    instructions: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    run_state: str | None = None
