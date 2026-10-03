from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text

from alembic import command
from app.core.config import Settings, get_settings
from app.core.database import get_engine
from app.modules.health.service import ReadinessService

API_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = API_ROOT / "alembic.ini"


@pytest.fixture
def migrated_test_engine(monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("APP_ENV", "test")
    get_settings.cache_clear()
    engine = get_engine(Settings(_env_file=None))
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))

    try:
        yield engine
    finally:
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        engine.dispose()
        get_settings.cache_clear()


@pytest.mark.integration
def test_readiness_tracks_real_migration_state(migrated_test_engine: Engine) -> None:
    service = ReadinessService(migrated_test_engine, ALEMBIC_INI)

    before_upgrade = service.check()

    assert before_upgrade.is_ready is False
    assert before_upgrade.database == "ok"
    assert before_upgrade.migrations == "missing"

    command.upgrade(Config(str(ALEMBIC_INI)), "head")

    with migrated_test_engine.connect() as connection:
        revisions = connection.execute(text("SELECT version_num FROM alembic_version")).scalars()
        assert list(revisions) == ["20261003_0001"]
    assert service.check().is_ready is True

    with migrated_test_engine.begin() as connection:
        connection.execute(
            text("UPDATE alembic_version SET version_num = 'obsolete_revision'")
        )

    after_revision_change = service.check()
    assert after_revision_change.is_ready is False
    assert after_revision_change.migrations == "pending"


@pytest.mark.integration
def test_readiness_sanitizes_database_outage() -> None:
    unavailable_engine = create_engine(
        "postgresql+psycopg://user:password@127.0.0.1:1/missing?connect_timeout=1"
    )
    service = ReadinessService(unavailable_engine, ALEMBIC_INI)

    result = service.check()

    assert result.is_ready is False
    assert result.database == "unavailable"
    assert result.migrations == "unavailable"
    unavailable_engine.dispose()

