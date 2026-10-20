from datetime import date, datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.core.decimal_types import Version
from app.modules.employees.models import EmploymentStatus
from app.modules.organization.schemas import Input, Label, Patch
from app.modules.review_cycles.models import CycleStatus
from app.modules.settings.schemas import ScoringPolicy


class CycleCreate(Input):
    name: Label
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def date_order(self) -> Self:
        if self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")
        return self


class ExpectedVersion(Input):
    expected_version: Version


class CycleUpdate(Patch):
    expected_version: Version
    name: Label | None = None
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def has_change(self) -> Self:
        if not self.model_fields_set - {"expected_version"}:
            raise ValueError("Provide at least one metadata change")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")
        return self


class Enrollment(ExpectedVersion):
    employee_ids: list[UUID] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_employees(self) -> Self:
        if len(set(self.employee_ids)) != len(self.employee_ids):
            raise ValueError("employee_ids must be unique")
        return self


class RelationshipSnapshot(Input):
    employee_id: UUID
    user_id: UUID | None
    employment_status: EmploymentStatus


class ParticipantSnapshot(Input):
    schema_version: Literal[1] = 1
    employee_id: UUID
    user_id: UUID
    employee_code: str
    display_name: str
    department_id: UUID
    department_code: str
    department_name: str
    position_id: UUID
    position_code: str
    position_title: str
    manager_id: UUID
    manager_user_id: UUID
    manager_display_name: str
    direct_reports: list[RelationshipSnapshot]


class CycleView(BaseModel):
    id: UUID
    name: str
    start_date: date
    end_date: date
    status: CycleStatus
    version: int
    policy: ScoringPolicy
    policy_source_version: int
    policy_is_preview: bool
    participant_count: int
    can_edit: bool
    can_activate: bool
    activated_at: datetime | None


class ParticipantView(BaseModel):
    id: UUID
    cycle_id: UUID
    employee_id: UUID
    employee_code: str
    display_name: str
    department_id: UUID
    department_name: str
    position_title: str
    evidence_version: int
    is_snapshot: bool
    can_manage_kpis: bool


class EnrollmentResult(BaseModel):
    version: int
    count: int
