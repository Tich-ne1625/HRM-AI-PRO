from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StrictInt

from app.core.decimal_types import Version
from app.modules.feedback.schemas import RatingGroup, SubmissionView
from app.modules.organization.schemas import Input
from app.modules.review_cycles.models import CycleStatus


class CalculateInput(Input):
    cycle_id: UUID
    expected_evidence_version: Version


class FinalizeInput(Input):
    expected_evidence_version: Version
    expected_calculation_version: Version
    acknowledge_open_optional_count: Annotated[StrictInt, Field(ge=0, le=100)]


class Issue(BaseModel):
    code: str
    kpi_id: UUID | None = None


class Readiness(BaseModel):
    ready: bool
    issue_count: int
    issues: list[Issue]


class HRReadiness(Readiness):
    pending_assignment_ids: list[UUID]
    blocked_assignment_ids: list[UUID]


class ScoreLine(BaseModel):
    id: UUID
    code: str
    name: str
    unit: str
    direction: str
    target: str
    actual: str
    weight: str
    raw_score: str
    normalized_score: str
    weighted_score: str


class FeedbackAggregate(BaseModel):
    count: int
    mean: str | None
    groups: list[RatingGroup]
    own_submission: SubmissionView | None


class CalculationView(BaseModel):
    calculation_version: int
    evidence_version: int
    engine_version: str
    calculated_at: datetime
    kpi_score: str
    feedback_score: str
    final_score: str
    policy: dict[str, str | int | None]
    items: list[ScoreLine]
    feedback: FeedbackAggregate


class PerformanceReport(BaseModel):
    review_id: UUID | None
    participant_id: UUID
    employee_id: UUID
    employee_code: str
    display_name: str
    cycle_id: UUID
    cycle_name: str
    cycle_status: CycleStatus
    cycle_version: int
    evidence_version: int
    state: Literal["NOT_CALCULATED", "CURRENT", "STALE", "FINALIZED"]
    current_result: CalculationView | None
    last_calculation: CalculationView | None
    readiness: Readiness
    can_calculate: bool
    can_finalize: bool
    finalized_at: datetime | None
    reused: bool = False


class FinalizationContext(BaseModel):
    review_id: UUID
    evidence_version: int
    calculation_version: int
    readiness: HRReadiness
    open_optional_count: int


class RevisionSummary(BaseModel):
    calculation_version: int
    evidence_version: int
    calculated_at: datetime
    kpi_score: str
    feedback_score: str
    final_score: str


class CloseResult(BaseModel):
    id: UUID
    status: Literal[CycleStatus.CLOSED]
    version: int
