from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, text

from alembic import command
from app.modules.health.service import ReadinessService

API_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = API_ROOT / "alembic.ini"


@pytest.mark.integration
def test_readiness_tracks_real_migration_state(empty_test_engine: Engine) -> None:
    service = ReadinessService(empty_test_engine, ALEMBIC_INI)

    before_upgrade = service.check()

    assert before_upgrade.is_ready is False
    assert before_upgrade.database == "ok"
    assert before_upgrade.migrations == "missing"

    config = Config(str(ALEMBIC_INI))
    heads = ScriptDirectory.from_config(config).get_heads()
    assert len(heads) == 1
    command.upgrade(config, heads[0])

    with empty_test_engine.connect() as connection:
        revisions = connection.execute(text("SELECT version_num FROM alembic_version")).scalars()
        assert list(revisions) == heads
    assert service.check().is_ready is True

    with empty_test_engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num = 'obsolete_revision'"))

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
