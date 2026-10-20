from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, FieldSerializationInfo, field_serializer

from app.core.decimal_types import four_places, two_places
from app.modules.kpis.models import KPIDirection
from app.modules.organization.schemas import Input
from app.modules.review_cycles.models import CycleStatus
from app.modules.review_cycles.schemas import ParticipantView


class DefinitionSnapshot(Input):
    schema_version: Literal[1] = 1
    version: int
    code: str
    name: str
    description: str
    unit: str
    direction: KPIDirection


class AllocationLine(BaseModel):
    id: UUID
    definition_id: UUID
    definition: DefinitionSnapshot
    target: Decimal
    actual: Decimal | None
    weight: Decimal

    @field_serializer("target", "actual", "weight", when_used="json")
    def serialize_number(self, value: Decimal | None, info: FieldSerializationInfo) -> str | None:
        if value is None:
            return None
        return two_places(value) if info.field_name == "weight" else four_places(value)


class AllocationView(BaseModel):
    participant: ParticipantView
    cycle_status: CycleStatus
    items: list[AllocationLine]
