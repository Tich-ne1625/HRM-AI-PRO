from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel

from app.modules.employees.models import EmploymentStatus
from app.modules.organization.schemas import Code, Input, Label, Patch


class EmployeeCreate(Input):
    employee_code: Code
    display_name: Label
    department_id: UUID
    position_id: UUID
    manager_id: UUID | None = None
    user_id: UUID | None = None
    employment_status: EmploymentStatus = EmploymentStatus.ACTIVE


class EmployeeUpdate(Patch):
    nullable_fields: ClassVar[frozenset[str]] = frozenset({"manager_id", "user_id"})
    employee_code: Code | None = None
    display_name: Label | None = None
    department_id: UUID | None = None
    position_id: UUID | None = None
    manager_id: UUID | None = None
    user_id: UUID | None = None
    employment_status: EmploymentStatus | None = None


class EmployeeView(BaseModel):
    id: UUID
    employee_code: str
    display_name: str
    department_id: UUID
    department_name: str
    position_id: UUID
    position_title: str
    manager_id: UUID | None
    manager_name: str | None
    user_id: UUID | None
    employment_status: EmploymentStatus
    created_at: datetime
    updated_at: datetime


class AccountLookup(BaseModel):
    id: UUID
    email: str
    is_active: bool
    employee_id: UUID | None


class AccountMatches(BaseModel):
    items: list[AccountLookup]
