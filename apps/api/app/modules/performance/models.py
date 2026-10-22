from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.organization.models import Timestamps


def score_checks(prefix: str) -> tuple[CheckConstraint, ...]:
    return (
        CheckConstraint(
            "calculation_version >= 1 AND evidence_version >= 1", name=f"ck_{prefix}_versions"
        ),
        CheckConstraint(
            "evidence_hash ~ '^[0-9a-f]{64}$' AND engine_version ~ '^[0-9]+$'",
            name=f"ck_{prefix}_hash",
        ),
        CheckConstraint(
            "jsonb_typeof(evidence_snapshot) = 'object' "
            "AND jsonb_typeof(policy_snapshot) = 'object'",
            name=f"ck_{prefix}_snapshots",
        ),
        *(
            CheckConstraint(
                f"{field} >= 0 AND {field} != 'NaN'::numeric", name=f"ck_{prefix}_{field}"
            )
            for field in ("kpi_score", "feedback_score", "final_score")
        ),
    )


class CalculationFields:
    calculation_version: Mapped[int]
    evidence_version: Mapped[int]
    engine_version: Mapped[str] = mapped_column(String(16))
    evidence_hash: Mapped[str] = mapped_column(String(64))
    kpi_score: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    feedback_score: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    final_score: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    evidence_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB(none_as_null=True))
    policy_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB(none_as_null=True))
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PerformanceReview(CalculationFields, Timestamps, Base):
    __tablename__ = "performance_reviews"
    __table_args__ = score_checks("performance_reviews")
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    participant_id: Mapped[UUID] = mapped_column(
        ForeignKey("cycle_participants.id", ondelete="RESTRICT"), unique=True
    )
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PerformanceReviewRevision(CalculationFields, Base):
    __tablename__ = "performance_review_revisions"
    __table_args__ = (
        UniqueConstraint("review_id", "calculation_version", name="uq_review_revision_version"),
        *score_checks("review_revisions"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    review_id: Mapped[UUID] = mapped_column(
        ForeignKey("performance_reviews.id", ondelete="RESTRICT")
    )
