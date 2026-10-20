from decimal import Decimal
from typing import Literal, Self

from pydantic import field_validator, model_validator

from app.core.decimal_types import Cap, Percentage, Version
from app.modules.organization.schemas import Input


class ScoringPolicy(Input):
    schema_version: Literal[1] = 1
    kpi_weight: Percentage = Decimal("70.00")
    feedback_weight: Percentage = Decimal("30.00")
    kpi_cap: Cap | None = Decimal("100.00")

    @field_validator("schema_version", mode="before")
    @classmethod
    def strict_schema_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("schema_version must be an integer")
        return value

    @model_validator(mode="after")
    def exact_sum(self) -> Self:
        if self.kpi_weight + self.feedback_weight != 100:
            raise ValueError("Component weights must sum to 100.00")
        return self


class ScoringUpdate(Input):
    expected_version: Version
    policy: ScoringPolicy


class ScoringView(Input):
    version: int
    policy: ScoringPolicy
