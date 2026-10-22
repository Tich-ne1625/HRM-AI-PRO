import json
import unicodedata
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.core.decimal_types import Version
from app.modules.organization.schemas import Input


class Audience(StrEnum):
    PUBLIC = "PUBLIC"
    HR_PRIVATE = "HR_PRIVATE"


class GenerateInput(Input):
    client_request_id: UUID
    expected_calculation_version: Version
    expected_evidence_version: Version
    audience: Audience = Audience.PUBLIC
    regenerate: StrictBool = False
    expected_latest_generation: Annotated[StrictInt, Field(ge=0)] | None = None

    @model_validator(mode="after")
    def confirmation(self) -> Self:
        if self.regenerate and self.expected_latest_generation is None:
            raise ValueError("Regeneration requires the reviewed latest generation")
        if not self.regenerate and self.expected_latest_generation is not None:
            raise ValueError("Latest generation is only accepted for regeneration")
        return self


Text = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=400)
]


class AnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    summary: Annotated[
        str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=1500)
    ]
    strengths: Annotated[list[Text], Field(max_length=5)]
    improvement_areas: Annotated[list[Text], Field(max_length=5)]
    feedback_themes: Annotated[list[Text], Field(max_length=5)]
    recommended_actions: Annotated[list[Text], Field(max_length=5)]
    caveats: Annotated[list[Text], Field(min_length=1, max_length=5)]

    @field_validator(
        "summary",
        "strengths",
        "improvement_areas",
        "feedback_themes",
        "recommended_actions",
        "caveats",
    )
    @classmethod
    def plain_text(cls, value: Any) -> Any:
        for item in [value] if isinstance(value, str) else value:
            if any(unicodedata.category(c).startswith("C") and c not in "\n\t" for c in item):
                raise ValueError("Unsupported control character")
        return value


def parse_output(raw: str) -> AnalysisOutput:
    if len(raw.encode("utf-8")) > 32768:
        raise ValueError("Output too large")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def invalid(value: str) -> None:
        raise ValueError("Non-finite JSON value")

    return AnalysisOutput.model_validate(
        json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)
    )


class AnalysisView(BaseModel):
    id: UUID
    audience: Audience
    generation_version: int
    calculation_version: int
    evidence_version: int
    status: str
    model: str
    prompt_version: str
    reserved_at: datetime
    generated_at: datetime | None
    error_code: str | None
    output: AnalysisOutput | None
    input_sampled: bool
    advisory: bool = True


class AnalysisState(BaseModel):
    audience: Audience
    state: str
    configured: bool
    can_generate: bool
    can_retry: bool
    current_analysis: AnalysisView | None
    last_successful_analysis: AnalysisView | None
    latest_attempt: AnalysisView | None
