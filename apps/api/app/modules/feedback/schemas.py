from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, Field, StrictBool, StrictInt, model_validator

from app.core.decimal_types import Version
from app.modules.feedback.models import AssignmentStatus, Relationship
from app.modules.organization.schemas import Input, Patch
from app.modules.review_cycles.models import CycleStatus


def aware_deadline(value: object) -> datetime:
    if not isinstance(value, str | datetime):
        raise ValueError("Deadline must be an ISO datetime with a timezone")
    try:
        parsed = (
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            if isinstance(value, str)
            else value
        )
    except ValueError as exc:
        raise ValueError("Deadline must be an ISO datetime with a timezone") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Deadline must include a timezone")
    return parsed.astimezone(UTC)


def plain_comment(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Comment must be plain text")
    value = value.replace("\r\n", "\n").strip()
    if len(value) > 2000 or any((ord(c) < 32 and c not in "\n\t") or ord(c) == 127 for c in value):
        raise ValueError("Comment is too long or contains unsupported control characters")
    return value


Deadline = Annotated[datetime, BeforeValidator(aware_deadline)]
Comment = Annotated[str, BeforeValidator(plain_comment)]


class ReasonCode(StrEnum):
    WRONG_SELECTION = "WRONG_SELECTION"
    REVIEWER_UNAVAILABLE = "REVIEWER_UNAVAILABLE"
    NO_LONGER_REQUIRED = "NO_LONGER_REQUIRED"


class EvidenceVersion(Input):
    expected_evidence_version: Version


class AssignmentVersions(EvidenceVersion):
    expected_assignment_version: Version


class AssignmentCreate(EvidenceVersion):
    participant_id: UUID
    reviewer_id: UUID
    relationship: Relationship
    required: StrictBool
    due_at: Deadline | None = None

    @model_validator(mode="after")
    def mandatory_required(self) -> Self:
        if self.relationship in (Relationship.SELF, Relationship.MANAGER) and not self.required:
            raise ValueError("SELF and MANAGER assignments must be required")
        return self


class AssignmentUpdate(Patch, AssignmentVersions):
    nullable_fields = frozenset({"due_at"})
    required: StrictBool | None = None
    due_at: Deadline | None = None
    status: Literal[AssignmentStatus.OPEN] | None = None

    @model_validator(mode="after")
    def has_change(self) -> Self:
        if not self.model_fields_set - {"expected_assignment_version", "expected_evidence_version"}:
            raise ValueError("Provide at least one assignment change")
        return self


class AssignmentCancel(AssignmentVersions):
    reason_code: ReasonCode


class AssignmentReplace(AssignmentCancel):
    reviewer_id: UUID
    due_at: Deadline | None = None


class FeedbackCreate(AssignmentVersions):
    assignment_id: UUID
    rating: Annotated[StrictInt, Field(ge=1, le=5)]
    comment: Comment = ""


class SubmissionView(BaseModel):
    rating: int
    comment: str
    submitted_at: datetime


class AssignmentView(BaseModel):
    id: UUID
    participant_id: UUID
    cycle_id: UUID
    cycle_name: str
    cycle_status: CycleStatus
    start_date: str
    end_date: str
    employee_id: UUID
    employee_code: str
    display_name: str
    relationship: Relationship
    required: bool
    status: AssignmentStatus
    due_at: datetime | None
    version: int
    evidence_version: int
    finalized: bool
    submission: SubmissionView | None


class AdministrationView(AssignmentView):
    reviewer_id: UUID
    reviewer_employee_id: UUID
    reviewer_name: str
    reviewer_active: bool


class ReviewerOption(BaseModel):
    reviewer_id: UUID
    employee_id: UUID
    employee_code: str
    display_name: str
    is_active: bool
    existing_assignment_id: UUID | None
    existing_status: AssignmentStatus | None


class CoverageView(BaseModel):
    ready: bool
    missing_relationships: list[Relationship]
    pending_required: int
    blocked_required: int
    pending_assignment_ids: list[UUID]
    blocked_assignment_ids: list[UUID]


class RatingGroup(BaseModel):
    relationship: Relationship
    suppressed: bool
    count: int | None
    mean: str | None


class SummaryView(BaseModel):
    participant_id: UUID
    employee_id: UUID
    cycle_id: UUID
    evidence_version: int
    ready: bool
    count: int
    mean: str | None
    groups: list[RatingGroup]
    own_submission: SubmissionView | None


class AdministrationContext(BaseModel):
    participant_id: UUID
    cycle_id: UUID
    employee_id: UUID
    employee_code: str
    display_name: str
    evidence_version: int
    cycle_status: CycleStatus
    finalized: bool
    coverage: CoverageView
