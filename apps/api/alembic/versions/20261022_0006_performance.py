"""Versioned performance calculations and finalization; no historical backfill."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "20261022_0006"
down_revision: str | None = "20261020_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def fields() -> list[sa.Column]:
    return [
        sa.Column("calculation_version", sa.Integer(), nullable=False),
        sa.Column("evidence_version", sa.Integer(), nullable=False),
        sa.Column("engine_version", sa.String(16), nullable=False),
        sa.Column("evidence_hash", sa.String(64), nullable=False),
        *(
            sa.Column(name, sa.Numeric(20, 2), nullable=False)
            for name in ("kpi_score", "feedback_score", "final_score")
        ),
        sa.Column("evidence_snapshot", JSONB(none_as_null=True), nullable=False),
        sa.Column("policy_snapshot", JSONB(none_as_null=True), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def checks(prefix: str) -> list[sa.CheckConstraint]:
    return [
        sa.CheckConstraint(
            "calculation_version >= 1 AND evidence_version >= 1", name=f"ck_{prefix}_versions"
        ),
        sa.CheckConstraint(
            "evidence_hash ~ '^[0-9a-f]{64}$' AND engine_version ~ '^[0-9]+$'",
            name=f"ck_{prefix}_hash",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(evidence_snapshot) = 'object' "
            "AND jsonb_typeof(policy_snapshot) = 'object'",
            name=f"ck_{prefix}_snapshots",
        ),
        *(
            sa.CheckConstraint(
                f"{name} >= 0 AND {name} != 'NaN'::numeric", name=f"ck_{prefix}_{name}"
            )
            for name in ("kpi_score", "feedback_score", "final_score")
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "performance_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "participant_id",
            sa.Uuid(),
            sa.ForeignKey("cycle_participants.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        *fields(),
        sa.Column("finalized_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        *checks("performance_reviews"),
    )
    op.create_table(
        "performance_review_revisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "review_id",
            sa.Uuid(),
            sa.ForeignKey("performance_reviews.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        *fields(),
        sa.UniqueConstraint("review_id", "calculation_version", name="uq_review_revision_version"),
        *checks("review_revisions"),
    )


def downgrade() -> None:
    op.drop_table("performance_review_revisions")
    op.drop_table("performance_reviews")
