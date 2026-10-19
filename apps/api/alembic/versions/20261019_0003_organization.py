"""Add organization references and employee profiles.

Revision ID: 20261019_0003
Revises: 20261003_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261019_0003"
down_revision: str | None = "20261003_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column[sa.DateTime]]:
    return [
        sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
        for name in ("created_at", "updated_at")
    ]


def upgrade() -> None:
    for table, label in (("departments", "name"), ("positions", "title")):
        op.create_table(
            table,
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("code", sa.String(32), nullable=False, unique=True),
            sa.Column(label, sa.String(200), nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            *timestamps(),
            sa.CheckConstraint("code ~ '^[A-Z0-9][A-Z0-9_-]{1,31}$'", name=f"ck_{table}_code"),
            sa.CheckConstraint(f"{label} ~ '[^[:space:]]'", name=f"ck_{table}_{label}"),
        )
    op.create_table(
        "employees",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("employee_code", sa.String(32), unique=True, nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column(
            "department_id",
            sa.Uuid(),
            sa.ForeignKey("departments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "position_id",
            sa.Uuid(),
            sa.ForeignKey("positions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("manager_id", sa.Uuid(), sa.ForeignKey("employees.id", ondelete="RESTRICT")),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), unique=True
        ),
        sa.Column(
            "employment_status",
            sa.Enum(
                "ACTIVE",
                "INACTIVE",
                native_enum=False,
                create_constraint=True,
                name="ck_employees_status",
            ),
            server_default="ACTIVE",
            nullable=False,
        ),
        *timestamps(),
        sa.CheckConstraint(
            "employee_code ~ '^[A-Z0-9][A-Z0-9_-]{1,31}$'", name="ck_employees_code"
        ),
        sa.CheckConstraint("display_name ~ '[^[:space:]]'", name="ck_employees_display_name"),
        sa.CheckConstraint("manager_id IS NULL OR manager_id <> id", name="ck_employees_manager"),
    )
    for name in ("department_id", "position_id", "manager_id"):
        op.create_index(f"ix_employees_{name}", "employees", [name])


def downgrade() -> None:
    op.drop_table("employees")
    op.drop_table("positions")
    op.drop_table("departments")
