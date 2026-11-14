from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Body = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class ContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    body: Body
    mentions: list[UUID] = Field(default_factory=list, max_length=10)


class PostInput(ContentInput):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]
    department_id: UUID | None = None


class ReadInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    through_id: UUID
