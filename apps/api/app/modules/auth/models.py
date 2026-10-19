from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        Index(
            "ix_auth_sessions_active_family",
            "family_id",
            postgresql_where=text("consumed_at IS NULL AND revoked_at IS NULL"),
        ),
        Index("ix_auth_sessions_expires_at", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    family_id: Mapped[UUID] = mapped_column()
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replacement_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("auth_sessions.id", ondelete="RESTRICT")
    )
