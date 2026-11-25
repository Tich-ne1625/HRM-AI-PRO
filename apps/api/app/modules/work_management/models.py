"""Append-only plan/evidence revisions and explicitly versioned work aggregates."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WorkPlan(Base):
    __tablename__ = "work_plans"
    __table_args__ = (
        UniqueConstraint("participant_id", name="uq_work_plans_participant"),
        CheckConstraint("version >= 1 AND revision >= 1", name="ck_work_plans_version"),
        CheckConstraint("measurement_version >= 0", name="ck_work_plans_measurement_version"),
        CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','CHANGES_REQUESTED','APPROVED')",
            name="ck_work_plans_status",
        ),
        CheckConstraint(
            "acknowledged_revision IS NULL OR acknowledged_revision = revision",
            name="ck_work_plans_ack",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    participant_id: Mapped[UUID] = mapped_column(ForeignKey("cycle_participants.id"))
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    revision: Mapped[int] = mapped_column(default=1, server_default="1")
    measurement_version: Mapped[int] = mapped_column(default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(24), default="DRAFT", server_default="DRAFT")
    acknowledged_revision: Mapped[int | None]
    approved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlanRevision(Base):
    __tablename__ = "work_plan_revisions"
    __table_args__ = (
        UniqueConstraint("plan_id", "number", name="uq_work_plan_revision"),
        CheckConstraint("number >= 1", name="ck_work_plan_revision_number"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("work_plans.id"))
    number: Mapped[int]
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    objective: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkGoal(Base):
    __tablename__ = "work_goals"
    __table_args__ = (
        UniqueConstraint("id", "plan_id", "revision", name="uq_work_goal_revision"),
        ForeignKeyConstraint(
            ["plan_id", "revision"], ["work_plan_revisions.plan_id", "work_plan_revisions.number"]
        ),
        CheckConstraint("jsonb_typeof(specification) = 'object'", name="ck_work_goal_spec"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_id: Mapped[UUID]
    revision: Mapped[int]
    definition_id: Mapped[UUID] = mapped_column(ForeignKey("kpi_definitions.id"))
    specification: Mapped[dict[str, object]] = mapped_column(JSONB)


class WorkItem(Base):
    __tablename__ = "work_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["plan_id", "plan_revision"],
            ["work_plan_revisions.plan_id", "work_plan_revisions.number"],
        ),
        UniqueConstraint("id", "plan_id", name="uq_work_items_plan_id"),
        ForeignKeyConstraint(
            ["goal_id", "plan_id", "plan_revision"],
            ["work_goals.id", "work_goals.plan_id", "work_goals.revision"],
        ),
        CheckConstraint("version >= 1", name="ck_work_items_version"),
        CheckConstraint(
            "status IN ('PROPOSED','TODO','IN_PROGRESS','SUBMITTED',"
            "'CHANGES_REQUESTED','ACCEPTED','CANCELLED')",
            name="ck_work_items_status",
        ),
        CheckConstraint("priority IN ('LOW','NORMAL','HIGH')", name="ck_work_items_priority"),
        CheckConstraint(
            "NOT blocked OR length(btrim(blocked_reason)) > 0", name="ck_work_items_blocked"
        ),
        UniqueConstraint("plan_id", "source_key", name="uq_work_items_source"),
        Index("ix_work_items_plan", "plan_id", "created_at", "id"),
        Index("ix_work_items_inbox", "status", "due_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("work_plans.id"))
    plan_revision: Mapped[int]
    goal_id: Mapped[UUID | None]
    source_key: Mapped[str] = mapped_column(String(120))
    reviewer_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    acceptance: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(12))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24))
    blocked: Mapped[bool] = mapped_column(default=False, server_default="false")
    blocked_reason: Mapped[str] = mapped_column(Text, default="", server_default="")
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvidenceSubmission(Base):
    __tablename__ = "work_submissions"
    __table_args__ = (
        UniqueConstraint("work_item_id", "number", name="uq_work_submission_number"),
        CheckConstraint("number >= 1", name="ck_work_submission_number"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    work_item_id: Mapped[UUID] = mapped_column(ForeignKey("work_items.id"))
    number: Mapped[int]
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkEvent(Base):
    __tablename__ = "work_events"
    __table_args__ = (
        ForeignKeyConstraint(["work_item_id", "plan_id"], ["work_items.id", "work_items.plan_id"]),
        CheckConstraint("revision >= 1", name="ck_work_events_revision"),
        CheckConstraint(
            "kind IN ('plan_saved','plan_submit','plan_approve','plan_clarify',"
            "'plan_acknowledge','plan_comment','created','publish','start','update',"
            "'block','unblock','submit','return','accept','cancel','reopen','comment',"
            "'request_change')",
            name="ck_work_events_kind",
        ),
        UniqueConstraint("actor_id", "client_request_id", name="uq_work_events_request"),
        Index("ix_work_events_history", "plan_id", "created_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("work_plans.id"))
    work_item_id: Mapped[UUID | None] = mapped_column(ForeignKey("work_items.id"))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    client_request_id: Mapped[UUID]
    request_hash: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(40))
    body: Mapped[str] = mapped_column(Text)
    revision: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
