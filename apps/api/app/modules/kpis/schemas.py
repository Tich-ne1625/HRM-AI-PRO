from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.core.decimal_types import PositiveQuantity, PositiveWeight, Quantity, Version
from app.modules.kpis.models import KPIDirection
from app.modules.organization.schemas import Code, Input, Label, Patch

Unit = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=50,
        pattern=r"^[^\x00-\x1f\x7f]+$",
    ),
]
Description = Annotated[
    str,
    StringConstraints(
        max_length=2000,
        pattern=r"^[^\x00-\x08\x0b-\x1f\x7f]*$",
    ),
]


class DefinitionCreate(Input):
    code: Code
    name: Label
    description: Description = ""
    unit: Unit
    direction: KPIDirection
    is_active: bool = True


class DefinitionUpdate(Patch):
    expected_version: Version
    code: Code | None = None
    name: Label | None = None
    description: Description | None = None
    unit: Unit | None = None
    direction: KPIDirection | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def has_change(self) -> Self:
        if not self.model_fields_set - {"expected_version"}:
            raise ValueError("Provide at least one definition change")
        return self


class AllocationItem(Input):
    definition_id: UUID
    target: PositiveQuantity
    weight: PositiveWeight


class AllocationReplace(Input):
    expected_evidence_version: Version
    items: list[AllocationItem] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def complete_allocation(self) -> Self:
        if len({item.definition_id for item in self.items}) != len(self.items):
            raise ValueError("definition_id must be unique")
        if sum(item.weight for item in self.items) != 100:
            raise ValueError("Allocation weights must sum to 100.00")
        return self


class ActualUpdate(Input):
    expected_evidence_version: Version
    actual: Quantity | None


class DefinitionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    name: str
    description: str
    unit: str
    direction: KPIDirection
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime
