from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("event_id", "recipient_id", name="uq_notifications_event_recipient"),
        Index("ix_notifications_inbox", "recipient_id", "created_at", "id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(ForeignKey("audit_logs.id", ondelete="RESTRICT"))
    recipient_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    recipient_role: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(100))
    employee_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT")
    )
    cycle_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("review_cycles.id", ondelete="RESTRICT")
    )
    assignment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("feedback_assignments.id", ondelete="RESTRICT")
    )
    post_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("internal_posts.id", ondelete="RESTRICT")
    )
    message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="RESTRICT")
    )
    work_plan_id: Mapped[UUID | None] = mapped_column(ForeignKey("work_plans.id"))
    work_item_id: Mapped[UUID | None] = mapped_column(ForeignKey("work_items.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
