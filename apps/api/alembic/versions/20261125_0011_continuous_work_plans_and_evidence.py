"""continuous work plans and evidence

Revision ID: 20261125_0011
Revises: 20261114_0010
Create Date: 2026-11-25 08:56:41.324036
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261125_0011"
down_revision: str | Sequence[str] | None = "20261114_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "work_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("participant_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=24), server_default="DRAFT", nullable=False),
        sa.Column("acknowledged_revision", sa.Integer(), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','CHANGES_REQUESTED','APPROVED')",
            name="ck_work_plans_status",
        ),
        sa.CheckConstraint(
            "acknowledged_revision IS NULL OR acknowledged_revision = revision",
            name="ck_work_plans_ack",
        ),
        sa.CheckConstraint("version >= 1 AND revision >= 1", name="ck_work_plans_version"),
        sa.ForeignKeyConstraint(
            ["approved_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["cycle_participants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("participant_id", name="uq_work_plans_participant"),
    )
    op.create_table(
        "work_plan_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("number >= 1", name="ck_work_plan_revision_number"),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["work_plans.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "number", name="uq_work_plan_revision"),
    )
    op.create_table(
        "work_goals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("definition_id", sa.Uuid(), nullable=False),
        sa.Column("specification", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint("jsonb_typeof(specification) = 'object'", name="ck_work_goal_spec"),
        sa.ForeignKeyConstraint(
            ["definition_id"],
            ["kpi_definitions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["plan_id", "revision"],
            ["work_plan_revisions.plan_id", "work_plan_revisions.number"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "plan_id", "revision", name="uq_work_goal_revision"),
    )
    op.create_table(
        "work_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("plan_revision", sa.Integer(), nullable=False),
        sa.Column("goal_id", sa.Uuid(), nullable=True),
        sa.Column("source_key", sa.String(length=120), nullable=False),
        sa.Column("reviewer_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("acceptance", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(length=12), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("blocked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("blocked_reason", sa.Text(), server_default="", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("priority IN ('LOW','NORMAL','HIGH')", name="ck_work_items_priority"),
        sa.CheckConstraint(
            "status IN ('PROPOSED','TODO','IN_PROGRESS','SUBMITTED',"
            "'CHANGES_REQUESTED','ACCEPTED','CANCELLED')",
            name="ck_work_items_status",
        ),
        sa.CheckConstraint(
            "NOT blocked OR length(btrim(blocked_reason)) > 0", name="ck_work_items_blocked"
        ),
        sa.CheckConstraint("version >= 1", name="ck_work_items_version"),
        sa.ForeignKeyConstraint(
            ["goal_id", "plan_id", "plan_revision"],
            ["work_goals.id", "work_goals.plan_id", "work_goals.revision"],
        ),
        sa.ForeignKeyConstraint(
            ["plan_id", "plan_revision"],
            ["work_plan_revisions.plan_id", "work_plan_revisions.number"],
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["work_plans.id"],
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "plan_id", name="uq_work_items_plan_id"),
        sa.UniqueConstraint("plan_id", "source_key", name="uq_work_items_source"),
    )
    op.create_index("ix_work_items_inbox", "work_items", ["status", "due_at", "id"], unique=False)
    op.create_index(
        "ix_work_items_plan", "work_items", ["plan_id", "created_at", "id"], unique=False
    )
    op.create_table(
        "work_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("work_item_id", sa.Uuid(), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("client_request_id", sa.Uuid(), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('plan_saved','plan_submit','plan_approve','plan_clarify',"
            "'plan_acknowledge','plan_comment','created','publish','start','update','block',"
            "'unblock','submit','return','accept','cancel','reopen','comment',"
            "'request_change')",
            name="ck_work_events_kind",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_work_events_revision"),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["work_plans.id"],
        ),
        sa.ForeignKeyConstraint(
            ["work_item_id", "plan_id"],
            ["work_items.id", "work_items.plan_id"],
        ),
        sa.ForeignKeyConstraint(
            ["work_item_id"],
            ["work_items.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("actor_id", "client_request_id", name="uq_work_events_request"),
    )
    op.create_index(
        "ix_work_events_history", "work_events", ["plan_id", "created_at", "id"], unique=False
    )
    op.create_table(
        "work_submissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_item_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("number >= 1", name="ck_work_submission_number"),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["work_item_id"],
            ["work_items.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("work_item_id", "number", name="uq_work_submission_number"),
    )
    op.add_column("notifications", sa.Column("work_plan_id", sa.Uuid(), nullable=True))
    op.add_column("notifications", sa.Column("work_item_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_notifications_work_plan", "notifications", "work_plans", ["work_plan_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_notifications_work_item", "notifications", "work_items", ["work_item_id"], ["id"]
    )
    op.add_column(
        "review_cycles",
        sa.Column(
            "workflow_mode",
            sa.Enum(
                "LEGACY",
                "CONTINUOUS",
                name="ck_review_cycles_workflow_mode",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="LEGACY",
            nullable=False,
        ),
    )
    op.add_column(
        "review_cycles",
        sa.Column(
            "workflow_schedule",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_review_cycles_workflow_schedule",
        "review_cycles",
        "(workflow_mode = 'LEGACY' AND workflow_schedule IS NULL) OR "
        "(workflow_mode = 'CONTINUOUS' AND workflow_schedule IS NOT NULL "
        "AND jsonb_typeof(workflow_schedule) = 'object')",
    )
    op.execute("""CREATE OR REPLACE FUNCTION preserve_work_evidence() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
        RAISE EXCEPTION 'work evidence is append only' USING ERRCODE = '23514';
        END $$""")
    for table in ("work_plan_revisions", "work_goals", "work_submissions", "work_events"):
        op.execute(
            f"CREATE TRIGGER preserve_{table} BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION preserve_work_evidence()"
        )


def downgrade() -> None:
    op.drop_constraint("ck_review_cycles_workflow_schedule", "review_cycles", type_="check")
    op.drop_constraint("ck_review_cycles_workflow_mode", "review_cycles", type_="check")
    op.drop_column("review_cycles", "workflow_schedule")
    op.drop_column("review_cycles", "workflow_mode")
    op.drop_column("notifications", "work_item_id")
    op.drop_column("notifications", "work_plan_id")
    for table in (
        "work_submissions",
        "work_events",
        "work_items",
        "work_goals",
        "work_plan_revisions",
        "work_plans",
    ):
        op.drop_table(table)
    op.execute("DROP FUNCTION preserve_work_evidence()")
