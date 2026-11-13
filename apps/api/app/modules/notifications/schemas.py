from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class NotificationView(BaseModel):
    id: UUID
    title: str
    message: str
    href: str
    created_at: datetime
    read_at: datetime | None


class NotificationPage(BaseModel):
    items: list[NotificationView]
    total: int
    unread_count: int
    page: int
    page_size: int


class WorkItem(BaseModel):
    id: str
    title: str
    detail: str
    href: str
    waiting: bool = False


class WorkPage(BaseModel):
    items: list[WorkItem]
    truncated: bool
