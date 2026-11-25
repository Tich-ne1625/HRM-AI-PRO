from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MetricRule(Base):
    __tablename__ = "metric_rules"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "plan_id", "plan_revision"],
            ["work_goals.id", "work_goals.plan_id", "work_goals.revision"],
        ),
        UniqueConstraint("goal_id", name="uq_metric_rules_goal"),
        UniqueConstraint("id", "plan_id", name="uq_metric_rules_plan"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    goal_id: Mapped[UUID]
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("work_plans.id"))
    plan_revision: Mapped[int]
    algorithm: Mapped[str] = mapped_column(String(40), default="measurements-v1")
    specification: Mapped[dict[str, Any]] = mapped_column(JSONB)


class Measurement(Base):
    __tablename__ = "measurements"
    __table_args__ = (
        ForeignKeyConstraint(["rule_id", "plan_id"], ["metric_rules.id", "metric_rules.plan_id"]),
        ForeignKeyConstraint(["work_item_id", "plan_id"], ["work_items.id", "work_items.plan_id"]),
        UniqueConstraint("rule_id", "source_key", name="uq_measurements_source"),
        Index(
            "uq_measurements_milestone",
            "rule_id",
            "milestone",
            unique=True,
            postgresql_where=text("NOT retired"),
        ),
        Index(
            "uq_measurements_last",
            "rule_id",
            "snapshot_at",
            unique=True,
            postgresql_where=text("NOT retired"),
        ),
        UniqueConstraint("id", "plan_id", name="uq_measurements_plan"),
        CheckConstraint("version >= 1 AND number >= 1", name="ck_measurements_version"),
        CheckConstraint(
            "effective_number IS NULL OR (effective_number >= 1 AND effective_number <= number)",
            name="ck_measurements_effective",
        ),
        CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','RETURNED','REJECTED','VERIFIED')",
            name="ck_measurements_status",
        ),
        CheckConstraint(
            "source_kind IN ('WORK','EXTERNAL_REFERENCE')", name="ck_measurements_source"
        ),
        CheckConstraint(
            "(source_kind = 'WORK') = (work_item_id IS NOT NULL)", name="ck_measurements_work"
        ),
        Index("ix_measurements_inbox", "plan_id", "status", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_id: Mapped[UUID]
    rule_id: Mapped[UUID]
    source_key: Mapped[str] = mapped_column(String(120))
    source_label: Mapped[str] = mapped_column(String(120))
    source_kind: Mapped[str] = mapped_column(String(24))
    work_item_id: Mapped[UUID | None]
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    snapshot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    milestone: Mapped[int | None]
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    number: Mapped[int] = mapped_column(default=1, server_default="1")
    status: Mapped[str] = mapped_column(String(16), default="DRAFT")
    effective_number: Mapped[int | None]
    suspended: Mapped[bool] = mapped_column(default=False, server_default="false")
    retired: Mapped[bool] = mapped_column(default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MeasurementRevision(Base):
    __tablename__ = "measurement_revisions"
    __table_args__ = (
        UniqueConstraint("measurement_id", "number", name="uq_measurement_revisions_number"),
        CheckConstraint("number >= 1", name="ck_measurement_revisions_number"),
        CheckConstraint("kind IN ('VALUE','VOID')", name="ck_measurement_revisions_kind"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    measurement_id: Mapped[UUID] = mapped_column(ForeignKey("measurements.id"))
    number: Mapped[int]
    kind: Mapped[str] = mapped_column(String(8))
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProgressSnapshot(Base):
    __tablename__ = "progress_snapshots"
    __table_args__ = (
        UniqueConstraint("plan_id", "version", name="uq_progress_snapshots_version"),
        CheckConstraint("version >= 0", name="ck_progress_snapshots_version"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("work_plans.id"))
    version: Mapped[int]
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Checkin(Base):
    __tablename__ = "checkins"
    __table_args__ = (
        UniqueConstraint("id", "plan_id", name="uq_checkins_plan"),
        CheckConstraint("period_start <= period_end", name="ck_checkins_period"),
        CheckConstraint("version >= 1 AND publication >= 0", name="ck_checkins_version"),
        CheckConstraint(
            "status IN ('SCHEDULED','OPEN','PUBLISHED','CANCELLED')", name="ck_checkins_status"
        ),
        Index("ix_checkins_schedule", "plan_id", "scheduled_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("work_plans.id"))
    title: Mapped[str] = mapped_column(String(200))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="SCHEDULED")
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    publication: Mapped[int] = mapped_column(default=0, server_default="0")
    acknowledged_publication: Mapped[int | None]
    clarification_pending: Mapped[bool] = mapped_column(default=False, server_default="false")
    snapshot_id: Mapped[UUID | None] = mapped_column(ForeignKey("progress_snapshots.id"))


class CheckinPreparation(Base):
    __tablename__ = "checkin_preparations"
    __table_args__ = (
        UniqueConstraint("checkin_id", "author_id", name="uq_checkin_preparations_author"),
        CheckConstraint("version >= 1", name="ck_checkin_preparations_version"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    checkin_id: Mapped[UUID] = mapped_column(ForeignKey("checkins.id"))
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    shared: Mapped[bool] = mapped_column(default=False, server_default="false")
    version: Mapped[int] = mapped_column(default=1, server_default="1")


class CheckinPublication(Base):
    __tablename__ = "checkin_publications"
    __table_args__ = (
        UniqueConstraint("checkin_id", "number", name="uq_checkin_publications_number"),
        CheckConstraint("number >= 1", name="ck_checkin_publications_number"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    checkin_id: Mapped[UUID] = mapped_column(ForeignKey("checkins.id"))
    number: Mapped[int]
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    shared_preparations: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CheckinAction(Base):
    __tablename__ = "checkin_actions"
    __table_args__ = (
        ForeignKeyConstraint(["checkin_id", "plan_id"], ["checkins.id", "checkins.plan_id"]),
        CheckConstraint("owner_id <> reviewer_id", name="ck_checkin_actions_reviewer"),
        CheckConstraint("version >= 1", name="ck_checkin_actions_version"),
        CheckConstraint(
            "status IN ('OPEN','IN_PROGRESS','SUBMITTED','CHANGES_REQUESTED','DONE','CANCELLED')",
            name="ck_checkin_actions_status",
        ),
        Index("ix_checkin_actions_inbox", "plan_id", "status", "due_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("work_plans.id"))
    checkin_id: Mapped[UUID]
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    reviewer_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="OPEN")
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    replaces_id: Mapped[UUID | None] = mapped_column(ForeignKey("checkin_actions.id"))


class ProgressEvent(Base):
    __tablename__ = "progress_events"
    __table_args__ = (
        UniqueConstraint("actor_id", "client_request_id", name="uq_progress_events_request"),
        Index("ix_progress_events_history", "plan_id", "created_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("work_plans.id"))
    measurement_id: Mapped[UUID | None] = mapped_column(ForeignKey("measurements.id"))
    checkin_id: Mapped[UUID | None] = mapped_column(ForeignKey("checkins.id"))
    action_id: Mapped[UUID | None] = mapped_column(ForeignKey("checkin_actions.id"))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    client_request_id: Mapped[UUID]
    request_hash: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(48))
    body: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
