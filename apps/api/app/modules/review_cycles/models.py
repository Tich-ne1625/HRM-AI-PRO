from datetime import date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.organization.models import Timestamps


class CycleStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class ReviewCycle(Timestamps, Base):
    __tablename__ = "review_cycles"
    __table_args__ = (
        CheckConstraint("start_date <= end_date", name="ck_review_cycles_dates"),
        CheckConstraint("name ~ '[^[:space:]]'", name="ck_review_cycles_name"),
        CheckConstraint("version >= 1", name="ck_review_cycles_version"),
        CheckConstraint(
            "(status = 'DRAFT' AND scoring_policy_snapshot IS NULL "
            "AND policy_source_version IS NULL AND activated_at IS NULL) OR "
            "(status IN ('ACTIVE', 'CLOSED') AND scoring_policy_snapshot IS NOT NULL "
            "AND jsonb_typeof(scoring_policy_snapshot) = 'object' "
            "AND policy_source_version IS NOT NULL AND policy_source_version >= 1 "
            "AND activated_at IS NOT NULL)",
            name="ck_review_cycles_snapshot",
        ),
        Index(
            "uq_review_cycles_one_active",
            "status",
            unique=True,
            postgresql_where=sql_text("status = 'ACTIVE'"),
        ),
        Index("ix_review_cycles_start_date", "start_date"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200))
    start_date: Mapped[date]
    end_date: Mapped[date]
    status: Mapped[CycleStatus] = mapped_column(
        Enum(
            CycleStatus,
            native_enum=False,
            create_constraint=True,
            name="ck_review_cycles_status",
        ),
        default=CycleStatus.DRAFT,
        server_default="DRAFT",
    )
    version: Mapped[int] = mapped_column(default=1, server_default=sql_text("1"))
    scoring_policy_snapshot: Mapped[dict[str, object] | None] = mapped_column(
        JSONB(none_as_null=True),
        nullable=True,
    )
    policy_source_version: Mapped[int | None]
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CycleParticipant(Timestamps, Base):
    __tablename__ = "cycle_participants"
    __table_args__ = (
        UniqueConstraint("cycle_id", "employee_id", name="uq_cycle_participants_employee"),
        CheckConstraint("evidence_version >= 1", name="ck_cycle_participants_version"),
        CheckConstraint(
            "snapshot IS NULL OR jsonb_typeof(snapshot) = 'object'",
            name="ck_cycle_participants_snapshot",
        ),
        Index("ix_cycle_participants_employee_id", "employee_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    cycle_id: Mapped[UUID] = mapped_column(ForeignKey("review_cycles.id", ondelete="RESTRICT"))
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id", ondelete="RESTRICT"))
    evidence_version: Mapped[int] = mapped_column(default=1, server_default=sql_text("1"))
    snapshot: Mapped[dict[str, object] | None] = mapped_column(JSONB(none_as_null=True))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
