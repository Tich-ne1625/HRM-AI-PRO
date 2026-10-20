from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.organization.models import Timestamps


class Relationship(StrEnum):
    SELF = "SELF"
    MANAGER = "MANAGER"
    PEER = "PEER"
    SUBORDINATE = "SUBORDINATE"


class AssignmentStatus(StrEnum):
    OPEN = "OPEN"
    SUBMITTED = "SUBMITTED"
    CANCELLED = "CANCELLED"


class FeedbackAssignment(Timestamps, Base):
    __tablename__ = "feedback_assignments"
    __table_args__ = (
        UniqueConstraint("participant_id", "reviewer_id", name="uq_feedback_assignments_reviewer"),
        CheckConstraint("version >= 1", name="ck_feedback_assignments_version"),
        CheckConstraint(
            "relationship NOT IN ('SELF', 'MANAGER') OR required",
            name="ck_feedback_assignments_required",
        ),
        CheckConstraint(
            "jsonb_typeof(eligibility_snapshot) = 'object'",
            name="ck_feedback_assignments_snapshot",
        ),
        Index(
            "uq_feedback_assignments_mandatory",
            "participant_id",
            "relationship",
            unique=True,
            postgresql_where=sql_text(
                "status != 'CANCELLED' AND relationship IN ('SELF', 'MANAGER')"
            ),
        ),
        Index("ix_feedback_assignments_inbox", "reviewer_id", "status", "due_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    participant_id: Mapped[UUID] = mapped_column(
        ForeignKey("cycle_participants.id", ondelete="RESTRICT")
    )
    reviewer_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reviewer_employee_id: Mapped[UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT")
    )
    relationship: Mapped[Relationship] = mapped_column(
        Enum(
            Relationship,
            native_enum=False,
            create_constraint=True,
            name="ck_feedback_assignments_relationship",
        )
    )
    required: Mapped[bool]
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(
            AssignmentStatus,
            native_enum=False,
            create_constraint=True,
            name="ck_feedback_assignments_status",
        ),
        default=AssignmentStatus.OPEN,
        server_default="OPEN",
    )
    version: Mapped[int] = mapped_column(default=1, server_default=sql_text("1"))
    eligibility_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB(none_as_null=True))


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="ck_feedback_rating"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    assignment_id: Mapped[UUID] = mapped_column(
        ForeignKey("feedback_assignments.id", ondelete="RESTRICT"), unique=True
    )
    rating: Mapped[int]
    comment: Mapped[str] = mapped_column(String(2000), default="", server_default="")
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sql_text("now()")
    )
