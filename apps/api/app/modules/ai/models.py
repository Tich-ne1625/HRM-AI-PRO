from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.ai.schemas import Audience


class AnalysisStatus(StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"
    __table_args__ = (
        ForeignKeyConstraint(
            ["review_id", "calculation_version"],
            [
                "performance_review_revisions.review_id",
                "performance_review_revisions.calculation_version",
            ],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("review_id", "audience", "generation_version", name="uq_ai_generation"),
        UniqueConstraint("requested_by", "client_request_id", name="uq_ai_idempotency"),
        Index(
            "uq_ai_running_review",
            "review_id",
            unique=True,
            postgresql_where=text("status='RUNNING'"),
        ),
        CheckConstraint(
            "generation_version >= 1 AND calculation_version >= 1 AND evidence_version >= 1",
            name="ck_ai_versions",
        ),
        CheckConstraint(
            "evidence_hash ~ '^[0-9a-f]{64}$' AND input_hash ~ '^[0-9a-f]{64}$' "
            "AND request_fingerprint ~ '^[0-9a-f]{64}$'",
            name="ck_ai_hashes",
        ),
        CheckConstraint("lease_until > reserved_at", name="ck_ai_lease"),
        CheckConstraint(
            "(status='RUNNING' AND output IS NULL AND error_code IS NULL "
            "AND completed_at IS NULL AND generated_at IS NULL) OR "
            "(status='SUCCEEDED' AND output IS NOT NULL AND jsonb_typeof(output)='object' "
            "AND error_code IS NULL AND completed_at IS NOT NULL "
            "AND generated_at IS NOT NULL AND generated_at=completed_at) OR "
            "(status='FAILED' AND output IS NULL "
            "AND error_code IS NOT NULL AND completed_at IS NOT NULL AND generated_at IS NULL)",
            name="ck_ai_result",
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= reserved_at", name="ck_ai_completion"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    review_id: Mapped[UUID] = mapped_column(
        ForeignKey("performance_reviews.id", ondelete="RESTRICT")
    )
    audience: Mapped[Audience] = mapped_column(
        Enum(Audience, native_enum=False, create_constraint=True, name="ck_ai_audience")
    )
    status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus, native_enum=False, create_constraint=True, name="ck_ai_status")
    )
    generation_version: Mapped[int]
    calculation_version: Mapped[int]
    evidence_version: Mapped[int]
    engine_version: Mapped[str] = mapped_column(String(16))
    evidence_hash: Mapped[str] = mapped_column(String(64))
    input_hash: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(16))
    redaction_version: Mapped[str] = mapped_column(String(16))
    schema_version: Mapped[str] = mapped_column(String(16))
    model: Mapped[str] = mapped_column(String(128))
    actual_model: Mapped[str | None] = mapped_column(String(128))
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    client_request_id: Mapped[UUID]
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    reserved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fencing_token: Mapped[UUID] = mapped_column(default=uuid4)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    output: Mapped[dict[str, object] | None] = mapped_column(JSONB(none_as_null=True))
    input_sampled: Mapped[bool]
