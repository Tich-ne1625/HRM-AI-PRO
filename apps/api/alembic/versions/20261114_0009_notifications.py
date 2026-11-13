"""Durable per-recipient notifications; existing business evidence is untouched."""

import sqlalchemy as sa

from alembic import op

revision = "20261114_0009"
down_revision = "20261024_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "event_id",
            sa.Uuid(),
            sa.ForeignKey("audit_logs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "recipient_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("recipient_role", sa.String(16), nullable=False),
        sa.Column("kind", sa.String(100), nullable=False),
        sa.Column("employee_id", sa.Uuid(), sa.ForeignKey("employees.id", ondelete="RESTRICT")),
        sa.Column("cycle_id", sa.Uuid(), sa.ForeignKey("review_cycles.id", ondelete="RESTRICT")),
        sa.Column(
            "assignment_id",
            sa.Uuid(),
            sa.ForeignKey("feedback_assignments.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("event_id", "recipient_id", name="uq_notifications_event_recipient"),
    )
    op.create_index("ix_notifications_inbox", "notifications", ["recipient_id", "created_at", "id"])


def downgrade() -> None:
    op.drop_table("notifications")
