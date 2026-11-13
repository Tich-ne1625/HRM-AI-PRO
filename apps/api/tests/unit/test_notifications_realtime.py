import asyncio
from uuid import uuid4

import pytest

from app.modules.notifications.realtime import NotificationHub


def test_hub_coalesces_signals_without_leaking_between_recipients():
    hub = NotificationHub("postgresql+psycopg://unused/unused")
    first, other = uuid4(), uuid4()
    queue = hub.subscribe(first)
    second_tab = hub.subscribe(first)
    unrelated = hub.subscribe(other)
    for _ in range(100):
        hub.signal(first)
    assert queue.qsize() == second_tab.qsize() == 1
    assert unrelated.empty()
    hub.unsubscribe(first, queue)
    hub.unsubscribe(first, second_tab)
    assert first not in hub.queues


def test_hub_bounds_connections_and_cleans_subscriptions():
    hub = NotificationHub("postgresql://unused/unused")
    user = uuid4()
    queues = [hub.subscribe(user) for _ in range(5)]
    with pytest.raises(ValueError):
        hub.subscribe(user)
    for queue in queues:
        hub.unsubscribe(user, queue)
    assert not hub.queues


def test_stream_rechecks_authority_and_closes_subscription(monkeypatch):
    from app.modules.notifications import realtime
    from app.modules.users.models import UserRole

    monkeypatch.setattr(realtime, "authorized", lambda *args: False)

    async def check():
        hub = NotificationHub("postgresql://unused/unused")
        hub.connected = True
        user = uuid4()
        queue = hub.subscribe(user)
        output = realtime.stream(hub, queue, None, None, "", user, uuid4(), UserRole.MANAGER)
        assert "event: change" in await anext(output)
        hub.signal(user)
        assert "event: session" in await anext(output)
        with pytest.raises(StopAsyncIteration):
            await anext(output)
        assert not hub.queues

    asyncio.run(check())


def test_stream_requests_polling_reconnect_when_database_listener_is_unavailable():
    from app.modules.notifications import realtime
    from app.modules.users.models import UserRole

    async def check():
        hub = NotificationHub("postgresql://unused/unused")
        user = uuid4()
        output = realtime.stream(
            hub, hub.subscribe(user), None, None, "", user, uuid4(), UserRole.HR
        )
        assert "event: reconnect" in await anext(output)
        await output.aclose()
        assert not hub.queues

    asyncio.run(check())
