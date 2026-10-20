"""Add explicit reviewer assignments and immutable feedback; no history backfill.

Revision ID: 20261020_0005
Revises: 20261020_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "20261020_0005"
down_revision: str | None = "20261020_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feedback_assignments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "participant_id",
            sa.Uuid(),
            sa.ForeignKey("cycle_participants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "reviewer_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "reviewer_employee_id",
            sa.Uuid(),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "relationship",
            sa.Enum(
                "SELF",
                "MANAGER",
                "PEER",
                "SUBORDINATE",
                native_enum=False,
                create_constraint=True,
                name="ck_feedback_assignments_relationship",
            ),
            nullable=False,
        ),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column(
            "status",
            sa.Enum(
                "OPEN",
                "SUBMITTED",
                "CANCELLED",
                native_enum=False,
                create_constraint=True,
                name="ck_feedback_assignments_status",
            ),
            server_default="OPEN",
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("eligibility_snapshot", JSONB(none_as_null=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "participant_id", "reviewer_id", name="uq_feedback_assignments_reviewer"
        ),
        sa.CheckConstraint("version >= 1", name="ck_feedback_assignments_version"),
        sa.CheckConstraint(
            "relationship NOT IN ('SELF', 'MANAGER') OR required",
            name="ck_feedback_assignments_required",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(eligibility_snapshot) = 'object'", name="ck_feedback_assignments_snapshot"
        ),
    )
    op.create_index(
        "uq_feedback_assignments_mandatory",
        "feedback_assignments",
        ["participant_id", "relationship"],
        unique=True,
        postgresql_where=sa.text("status != 'CANCELLED' AND relationship IN ('SELF', 'MANAGER')"),
    )
    op.create_index(
        "ix_feedback_assignments_inbox", "feedback_assignments", ["reviewer_id", "status", "due_at"]
    )
    op.create_table(
        "feedback",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "assignment_id",
            sa.Uuid(),
            sa.ForeignKey("feedback_assignments.id", ondelete="RESTRICT"),
            unique=True,
            nullable=False,
        ),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.String(2000), server_default="", nullable=False),
        sa.Column(
            "submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_feedback_rating"),
    )


def downgrade() -> None:
    op.drop_table("feedback")
    op.drop_table("feedback_assignments")
