from datetime import date
from typing import Self
from uuid import UUID

from pydantic import Field, model_validator

from app.core.decimal_types import Version
from app.modules.organization.schemas import Input, Label, Patch


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
