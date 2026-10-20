from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.organization.models import Timestamps


class KPIDirection(StrEnum):
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    LOWER_IS_BETTER = "LOWER_IS_BETTER"


class KPIDefinition(Timestamps, Base):
    __tablename__ = "kpi_definitions"
    __table_args__ = (
        CheckConstraint("code ~ '^[A-Z0-9][A-Z0-9_-]{1,31}$'", name="ck_kpi_definitions_code"),
        CheckConstraint("name ~ '[^[:space:]]'", name="ck_kpi_definitions_name"),
        CheckConstraint("unit ~ '[^[:space:]]'", name="ck_kpi_definitions_unit"),
        CheckConstraint("version >= 1", name="ck_kpi_definitions_version"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(2000), default="", server_default="")
    unit: Mapped[str] = mapped_column(String(50))
    direction: Mapped[KPIDirection] = mapped_column(
        Enum(
            KPIDirection,
            native_enum=False,
            create_constraint=True,
            name="ck_kpi_definitions_direction",
        )
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    version: Mapped[int] = mapped_column(default=1, server_default=text("1"))


class EmployeeKPI(Timestamps, Base):
    __tablename__ = "employee_kpis"
    __table_args__ = (
        UniqueConstraint("participant_id", "definition_id", name="uq_employee_kpis_definition"),
        CheckConstraint("target > 0 AND target != 'NaN'::numeric", name="ck_employee_kpis_target"),
        CheckConstraint(
            "actual IS NULL OR (actual >= 0 AND actual != 'NaN'::numeric)",
            name="ck_employee_kpis_actual",
        ),
        CheckConstraint("weight > 0 AND weight <= 100", name="ck_employee_kpis_weight"),
        CheckConstraint(
            "jsonb_typeof(definition_snapshot) = 'object'", name="ck_employee_kpis_snapshot"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    participant_id: Mapped[UUID] = mapped_column(
        ForeignKey("cycle_participants.id", ondelete="RESTRICT"),
    )
    definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("kpi_definitions.id", ondelete="RESTRICT")
    )
    definition_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB(none_as_null=True))
    target: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    actual: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 2))
