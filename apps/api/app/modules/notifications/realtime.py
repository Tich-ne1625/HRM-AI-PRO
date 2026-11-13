"""One reconnecting PostgreSQL listener per API process; bounded, coalescing SSE queues."""

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import suppress
from datetime import UTC, datetime
from uuid import UUID

import psycopg
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import InvalidAccessToken, TokenService
from app.modules.auth.models import AuthSession
from app.modules.users.models import User, UserRole


class NotificationHub:
    def __init__(self, database_url: str) -> None:
        self.dsn = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        self.queues: dict[UUID, set[asyncio.Queue[None]]] = defaultdict(set)
        self.runner: asyncio.Task[None] | None = None
        self.connected = False

    def signal(self, user_id: UUID | None = None) -> None:
        groups = [self.queues.get(user_id, set())] if user_id else list(self.queues.values())
        for queues in groups:
            for queue in queues:
                if queue.empty():
                    queue.put_nowait(None)

    def subscribe(self, user_id: UUID) -> asyncio.Queue[None]:
        if len(self.queues[user_id]) >= 5:
            raise ValueError("Too many notification connections")
        queue: asyncio.Queue[None] = asyncio.Queue(maxsize=1)
        self.queues[user_id].add(queue)
        return queue

    def unsubscribe(self, user_id: UUID, queue: asyncio.Queue[None]) -> None:
        self.queues[user_id].discard(queue)
        if not self.queues[user_id]:
            self.queues.pop(user_id, None)

    async def listen(self) -> None:
        while True:
            try:
                async with await psycopg.AsyncConnection.connect(
                    self.dsn, autocommit=True, connect_timeout=5
                ) as connection:
                    await connection.execute("LISTEN insighthr_notifications")
                    self.connected = True
                    self.signal()  # Catch up after listener reconnect; rows are durable.
                    while True:
                        async for event in connection.notifies(timeout=10, stop_after=1):
                            try:
                                self.signal(UUID(event.payload))
                            except ValueError:
                                continue
            except (psycopg.Error, OSError):
                self.connected = False
                self.signal()
                await asyncio.sleep(2)
            finally:
                self.connected = False

    def start(self) -> None:
        self.runner = asyncio.create_task(self.listen())

    async def stop(self) -> None:
        if self.runner:
            self.runner.cancel()
            with suppress(asyncio.CancelledError):
                await self.runner


def authorized(
    factory: sessionmaker[Session],
    tokens: TokenService,
    token: str,
    user_id: UUID,
    family_id: UUID,
    role: UserRole,
) -> bool:
    try:
        tokens.decode_access_token(token)
    except InvalidAccessToken:
        return False
    with factory() as session:
        user = session.get(User, user_id)
        family = session.scalar(
            select(AuthSession.id).where(
                AuthSession.user_id == user_id,
                AuthSession.family_id == family_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.consumed_at.is_(None),
                AuthSession.expires_at > datetime.now(UTC),
            )
        )
        return bool(user and user.is_active and user.role == role and family)


async def stream(
    hub: NotificationHub,
    queue: asyncio.Queue[None],
    factory: sessionmaker[Session],
    tokens: TokenService,
    token: str,
    user_id: UUID,
    family_id: UUID,
    role: UserRole,
) -> AsyncIterator[str]:
    try:
        if not hub.connected:
            yield "event: reconnect\ndata: {}\n\n"
            return
        yield "retry: 2000\nevent: change\ndata: {}\n\n"
        while True:
            changed = True
            try:
                await asyncio.wait_for(queue.get(), timeout=10)
            except TimeoutError:
                changed = False
            if not hub.connected:
                yield "event: reconnect\ndata: {}\n\n"
                return
            try:
                valid = await asyncio.to_thread(
                    authorized, factory, tokens, token, user_id, family_id, role
                )
            except Exception:
                # No exception text or database credentials cross the SSE boundary.
                yield "event: reconnect\ndata: {}\n\n"
                return
            if not valid:
                yield "event: session\ndata: {}\n\n"
                return
            yield "event: change\ndata: {}\n\n" if changed else ": heartbeat\n\n"
    finally:
        hub.unsubscribe(user_id, queue)
