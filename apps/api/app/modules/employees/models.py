from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.organization.models import Timestamps


class EmploymentStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class Employee(Timestamps, Base):
    __tablename__ = "employees"
    __table_args__ = (
        CheckConstraint("employee_code ~ '^[A-Z0-9][A-Z0-9_-]{1,31}$'", name="ck_employees_code"),
        CheckConstraint("display_name ~ '[^[:space:]]'", name="ck_employees_display_name"),
        CheckConstraint("manager_id IS NULL OR manager_id <> id", name="ck_employees_manager"),
        Index("ix_employees_department_id", "department_id"),
        Index("ix_employees_position_id", "position_id"),
        Index("ix_employees_manager_id", "manager_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    employee_code: Mapped[str] = mapped_column(String(32), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    department_id: Mapped[UUID] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"))
    position_id: Mapped[UUID] = mapped_column(ForeignKey("positions.id", ondelete="RESTRICT"))
    manager_id: Mapped[UUID | None] = mapped_column(ForeignKey("employees.id", ondelete="RESTRICT"))
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), unique=True
    )
    employment_status: Mapped[EmploymentStatus] = mapped_column(
        Enum(
            EmploymentStatus, native_enum=False, create_constraint=True, name="ck_employees_status"
        ),
        default=EmploymentStatus.ACTIVE,
        server_default="ACTIVE",
    )
