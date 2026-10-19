from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    HR = "HR"
    MANAGER = "MANAGER"
    EMPLOYEE = "EMPLOYEE"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("email = lower(email)", name="ck_users_normalized_email"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, create_constraint=True, name="ck_users_role")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
