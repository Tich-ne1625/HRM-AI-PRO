from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class CycleOption(BaseModel):
    id: UUID
    name: str
    status: str


class DepartmentMetric(BaseModel):
    id: str
    name: str
    participants: int
    sample_size: int
    average: Decimal | None


class Activity(BaseModel):
    id: UUID
    action: str
    occurred_at: datetime
    employee_id: UUID | None = None
    display_name: str | None = None
    cycle_id: UUID | None = None


class AdminDashboard(BaseModel):
    role: str
    pending_feedback: int
    active_accounts: int
    inactive_accounts: int
    account_roles: dict[str, int]
    recent_activities: list[Activity] = Field(default_factory=list)


class Dashboard(BaseModel):
    role: str
    pending_feedback: int
    recent_activities: list[Activity] = Field(default_factory=list)
    active_employees: int | None = None
    cycles: list[CycleOption] = Field(default_factory=list)
    cycles_truncated: bool = False
    selected_cycle: CycleOption | None = None
    participants: int = 0
    finalized: int = 0
    current: int = 0
    stale: int = 0
    not_calculated: int = 0
    awaiting_completion: int = 0
    sample_size: int = 0
    average: Decimal | None = None
    score_bands: dict[str, int] = Field(default_factory=dict)
    kpis_assigned: int = 0
    kpis_entered: int = 0
    kpi_entry_percent: Decimal | None = None
    departments: list[DepartmentMetric] = Field(default_factory=list)
    departments_truncated: bool = False
