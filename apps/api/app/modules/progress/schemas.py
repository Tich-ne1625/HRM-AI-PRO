from datetime import date
from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, HttpUrl, model_validator

from app.modules.work_management.schemas import Command, Number, Text, Title


class MeasurementDraft(Command):
    source_kind: Literal["WORK", "EXTERNAL_REFERENCE"] = "EXTERNAL_REFERENCE"
    source_key: str = Field(min_length=1, max_length=120)
    work_item_id: UUID | None = None
    occurred_at: AwareDatetime
    milestone: int | None = Field(default=None, ge=0, le=29)
    kind: Literal["VALUE", "VOID"] = "VALUE"
    value: Number | None = None
    numerator: Number | None = None
    denominator: Number | None = None
    body: Text
    url: HttpUrl | None = None

    @model_validator(mode="after")
    def source(self) -> Self:
        if (self.source_kind == "WORK") != (self.work_item_id is not None):
            raise ValueError("Work sources require a work item")
        if self.kind == "VOID" and any(
            v is not None for v in (self.value, self.numerator, self.denominator)
        ):
            raise ValueError("Void does not contain a numeric value")
        return self


class MeasurementCommand(Command):
    action: Literal["submit", "verify", "return", "reject"]
    body: Text | None = None

    @model_validator(mode="after")
    def decision(self) -> Self:
        if self.action in {"verify", "return", "reject"} and not self.body:
            raise ValueError("A decision requires an explanation")
        return self


class CheckinCreate(Command):
    title: Title
    scheduled_at: AwareDatetime
    period_start: date
    period_end: date


class CheckinCommand(Command):
    action: Literal["open", "publish", "cancel", "acknowledge", "clarify", "addendum", "reschedule"]
    body: Text | None = None
    publication: int = Field(default=0, ge=0)
    scheduled_at: AwareDatetime | None = None


class PreparationDraft(Command):
    body: Text
    shared: bool = False


class FollowupCreate(Command):
    body: Text
    owner_id: UUID
    due_at: AwareDatetime
    replaces_id: UUID | None = None


class FollowupCommand(Command):
    action: Literal["start", "submit", "return", "complete", "cancel"]
    body: Text
