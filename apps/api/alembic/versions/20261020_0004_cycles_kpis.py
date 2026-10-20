"""Add review cycles, historical participants, KPI evidence and scoring defaults.

Revision ID: 20261020_0004
Revises: 20261019_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "20261020_0004"
down_revision: str | None = "20261019_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column[sa.DateTime]]:
    return [
        sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
        for name in ("created_at", "updated_at")
    ]


def upgrade() -> None:
    config = op.create_table(
        "system_config",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("scoring_policy", JSONB(none_as_null=True), nullable=False),
        *timestamps(),
        sa.CheckConstraint("id = 1", name="ck_system_config_singleton"),
        sa.CheckConstraint("version >= 1", name="ck_system_config_version"),
        sa.CheckConstraint(
            "jsonb_typeof(scoring_policy) = 'object'", name="ck_system_config_policy"
        ),
    )
    op.bulk_insert(
        config,
        [
            {
                "id": 1,
                "version": 1,
                "scoring_policy": {
                    "schema_version": 1,
                    "kpi_weight": "70.00",
                    "feedback_weight": "30.00",
                    "kpi_cap": "100.00",
                },
            }
        ],
    )
    op.create_table(
        "review_cycles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "ACTIVE",
                "CLOSED",
                native_enum=False,
                create_constraint=True,
                name="ck_review_cycles_status",
            ),
            server_default="DRAFT",
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("scoring_policy_snapshot", JSONB(none_as_null=True)),
        sa.Column("policy_source_version", sa.Integer()),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.CheckConstraint("start_date <= end_date", name="ck_review_cycles_dates"),
        sa.CheckConstraint("name ~ '[^[:space:]]'", name="ck_review_cycles_name"),
        sa.CheckConstraint("version >= 1", name="ck_review_cycles_version"),
        sa.CheckConstraint(
            "(status = 'DRAFT' AND scoring_policy_snapshot IS NULL "
            "AND policy_source_version IS NULL AND activated_at IS NULL) OR "
            "(status IN ('ACTIVE', 'CLOSED') AND scoring_policy_snapshot IS NOT NULL "
            "AND jsonb_typeof(scoring_policy_snapshot) = 'object' "
            "AND policy_source_version IS NOT NULL AND policy_source_version >= 1 "
            "AND activated_at IS NOT NULL)",
            name="ck_review_cycles_snapshot",
        ),
    )
    op.create_index(
        "uq_review_cycles_one_active",
        "review_cycles",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_index("ix_review_cycles_start_date", "review_cycles", ["start_date"])
    op.create_table(
        "cycle_participants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "cycle_id",
            sa.Uuid(),
            sa.ForeignKey("review_cycles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "employee_id",
            sa.Uuid(),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("evidence_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("snapshot", JSONB(none_as_null=True)),
        sa.Column("finalized_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.UniqueConstraint("cycle_id", "employee_id", name="uq_cycle_participants_employee"),
        sa.CheckConstraint("evidence_version >= 1", name="ck_cycle_participants_version"),
        sa.CheckConstraint(
            "snapshot IS NULL OR jsonb_typeof(snapshot) = 'object'",
            name="ck_cycle_participants_snapshot",
        ),
    )
    op.create_index("ix_cycle_participants_employee_id", "cycle_participants", ["employee_id"])
    op.create_table(
        "kpi_definitions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(32), unique=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(2000), server_default="", nullable=False),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column(
            "direction",
            sa.Enum(
                "HIGHER_IS_BETTER",
                "LOWER_IS_BETTER",
                native_enum=False,
                create_constraint=True,
                name="ck_kpi_definitions_direction",
            ),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        *timestamps(),
        sa.CheckConstraint("code ~ '^[A-Z0-9][A-Z0-9_-]{1,31}$'", name="ck_kpi_definitions_code"),
        sa.CheckConstraint("name ~ '[^[:space:]]'", name="ck_kpi_definitions_name"),
        sa.CheckConstraint("unit ~ '[^[:space:]]'", name="ck_kpi_definitions_unit"),
        sa.CheckConstraint("version >= 1", name="ck_kpi_definitions_version"),
    )
    op.create_table(
        "employee_kpis",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "participant_id",
            sa.Uuid(),
            sa.ForeignKey("cycle_participants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "definition_id",
            sa.Uuid(),
            sa.ForeignKey("kpi_definitions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("definition_snapshot", JSONB(none_as_null=True), nullable=False),
        sa.Column("target", sa.Numeric(14, 4), nullable=False),
        sa.Column("actual", sa.Numeric(14, 4)),
        sa.Column("weight", sa.Numeric(5, 2), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("participant_id", "definition_id", name="uq_employee_kpis_definition"),
        sa.CheckConstraint(
            "target > 0 AND target != 'NaN'::numeric", name="ck_employee_kpis_target"
        ),
        sa.CheckConstraint(
            "actual IS NULL OR (actual >= 0 AND actual != 'NaN'::numeric)",
            name="ck_employee_kpis_actual",
        ),
        sa.CheckConstraint("weight > 0 AND weight <= 100", name="ck_employee_kpis_weight"),
        sa.CheckConstraint(
            "jsonb_typeof(definition_snapshot) = 'object'", name="ck_employee_kpis_snapshot"
        ),
    )


def downgrade() -> None:
    for table in (
        "employee_kpis",
        "kpi_definitions",
        "cycle_participants",
        "review_cycles",
        "system_config",
    ):
        op.drop_table(table)
