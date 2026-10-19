from datetime import datetime
from typing import Annotated, ClassVar, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)


def normalize_code(value: object) -> object:
    return value.strip().upper() if isinstance(value, str) else value


Code = Annotated[str, BeforeValidator(normalize_code), Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{1,31}$")]
Label = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=200,
        pattern=r"^[^\x00-\x1f\x7f]+$",
    ),
]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Patch(Input):
    nullable_fields: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def require_supported_changes(self) -> Self:
        if not self.model_fields_set or any(
            getattr(self, key) is None for key in self.model_fields_set - self.nullable_fields
        ):
            raise ValueError(
                "Provide at least one supported change; required fields cannot be null"
            )
        return self


class DepartmentCreate(Input):
    code: Code
    name: Label
    is_active: bool = True


class PositionCreate(Input):
    code: Code
    title: Label
    is_active: bool = True


class DepartmentUpdate(Patch):
    code: Code | None = None
    name: Label | None = None
    is_active: bool | None = None


class PositionUpdate(Patch):
    code: Code | None = None
    title: Label | None = None
    is_active: bool | None = None


class ReferenceBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DepartmentView(ReferenceBase):
    name: str


class PositionView(ReferenceBase):
    title: str


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
