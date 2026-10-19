from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Department(Timestamps, Base):
    __tablename__ = "departments"
    __table_args__ = (
        CheckConstraint("code ~ '^[A-Z0-9][A-Z0-9_-]{1,31}$'", name="ck_departments_code"),
        CheckConstraint("name ~ '[^[:space:]]'", name="ck_departments_name"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class Position(Timestamps, Base):
    __tablename__ = "positions"
    __table_args__ = (
        CheckConstraint("code ~ '^[A-Z0-9][A-Z0-9_-]{1,31}$'", name="ck_positions_code"),
        CheckConstraint("title ~ '[^[:space:]]'", name="ck_positions_title"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
