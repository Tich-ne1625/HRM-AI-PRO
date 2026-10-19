from __future__ import annotations

from collections.abc import Iterator
from typing import cast

from fastapi import Request
from psycopg import Connection
from sqlalchemy import Engine, MetaData, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry

from app.core.config import Settings

metadata = MetaData()


class Base(DeclarativeBase):
    metadata = metadata


def get_engine(settings: Settings) -> Engine:
    engine = create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
    )
    event.listen(engine, "connect", _set_utc_timezone)
    return engine


def _set_utc_timezone(
    connection: Connection[tuple[object, ...]], connection_record: ConnectionPoolEntry
) -> None:
    # Persist the session setting outside transactions, including pool rollbacks.
    autocommit = connection.autocommit
    try:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute("SET TIME ZONE 'UTC'")
    finally:
        connection.autocommit = autocommit


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db_session(request: Request) -> Iterator[Session]:
    factory = cast(sessionmaker[Session], request.app.state.session_factory)
    session = factory()
    try:
        yield session
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()
