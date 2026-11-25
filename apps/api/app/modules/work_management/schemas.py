from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, Field, HttpUrl, StringConstraints, model_validator

from app.core.decimal_types import Version
from app.modules.organization.schemas import Input

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=6000)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Number = Annotated[
    Decimal, Field(ge=0, le=Decimal("1000000000000"), max_digits=18, decimal_places=4)
]


class WorkflowSchedule(Input):
    timezone: str = Field(default="Asia/Ho_Chi_Minh", max_length=100)
    acknowledgement_due_at: AwareDatetime
    input_cutoff_at: AwareDatetime
    verification_due_at: AwareDatetime
    response_due_at: AwareDatetime

    @model_validator(mode="after")
    def valid_schedule(self) -> Self:
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Use an IANA timezone") from exc
        if not (
            self.acknowledgement_due_at
            < self.input_cutoff_at
            <= self.verification_due_at
            <= self.response_due_at
        ):
            raise ValueError("Workflow deadlines must be in order")
        for field in (
            "acknowledgement_due_at",
            "input_cutoff_at",
            "verification_due_at",
            "response_due_at",
        ):
            setattr(self, field, getattr(self, field).astimezone(UTC))
        return self

    def validate_window(self, start: date, end: date) -> None:
        zone = ZoneInfo(self.timezone)
        first = datetime.combine(start, time.min, zone)
        last = datetime.combine(end + timedelta(days=1), time.min, zone)
        if self.acknowledgement_due_at > first or self.input_cutoff_at < last:
            raise ValueError("Acknowledgement precedes start; cutoff follows the end date")


class Milestone(Input):
    title: Title
    weight: Annotated[Decimal, Field(gt=0, le=100, decimal_places=2)]


class GoalInput(Input):
    definition_id: UUID
    baseline: Number
    target: Annotated[
        Decimal, Field(gt=0, le=Decimal("1000000000000"), max_digits=18, decimal_places=4)
    ]
    weight: Annotated[Decimal, Field(gt=0, le=100, decimal_places=2)]
    method: Literal["SUM", "LAST", "RATIO", "MILESTONE"]
    source: Text
    acceptance: Text
    numerator: Title | None = None
    denominator: Title | None = None
    milestones: list[Milestone] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def rule(self) -> Self:
        if self.method == "RATIO" and (not self.numerator or not self.denominator):
            raise ValueError("Ratio requires numerator and denominator definitions")
        if self.method == "MILESTONE" and (
            not self.milestones or sum(m.weight for m in self.milestones) != 100
        ):
            raise ValueError("Milestones must total 100")
        if self.method != "MILESTONE" and self.milestones:
            raise ValueError("Milestones only apply to MILESTONE rules")
        return self


class Command(Input):
    client_request_id: UUID
    expected_version: Version


class PlanDraft(Command):
    objective: Text
    goals: list[GoalInput] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def weights(self) -> Self:
        if sum(goal.weight for goal in self.goals) != 100:
            raise ValueError("Goal weights must total 100")
        if len({goal.definition_id for goal in self.goals}) != len(self.goals):
            raise ValueError("Each KPI may appear once per revision")
        return self


class PlanAction(Command):
    action: Literal["submit", "approve", "clarify", "acknowledge", "comment"]
    revision: Version
    body: Text | None = None


class WorkCreate(Command):
    title: Title
    acceptance: Text
    goal_id: UUID | None = None
    source_key: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
    ]
    priority: Literal["LOW", "NORMAL", "HIGH"] = "NORMAL"
    due_at: AwareDatetime


class WorkAction(Command):
    action: Literal[
        "publish",
        "start",
        "update",
        "block",
        "unblock",
        "submit",
        "return",
        "accept",
        "cancel",
        "reopen",
        "comment",
        "request_change",
    ]
    body: Text | None = None
    url: HttpUrl | None = None

    @model_validator(mode="after")
    def explanation(self) -> Self:
        if (
            self.action
            in {
                "update",
                "block",
                "submit",
                "return",
                "accept",
                "cancel",
                "reopen",
                "comment",
                "request_change",
            }
            and not self.body
        ):
            raise ValueError("An explanation or evidence is required")
        if self.url and self.action != "submit":
            raise ValueError("URLs belong to evidence submissions")
        return self
