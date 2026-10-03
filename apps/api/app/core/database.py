from __future__ import annotations

from sqlalchemy import Engine, MetaData, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings

metadata = MetaData()


def get_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
    )


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

