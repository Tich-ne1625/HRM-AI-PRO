from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text
from sqlalchemy.engine import make_url

from alembic import command
from app.core.config import Settings, get_settings
from app.core.database import get_engine

from .organization_fixtures import world as world

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def drop_test_tables(engine: Engine) -> None:
    if not (engine.url.database or "").endswith("_test"):
        raise ValueError("Cleanup requires an explicitly disposable _test database")
    with engine.begin() as connection:
        for table in (
            "employees",
            "positions",
            "departments",
            "audit_logs",
            "auth_sessions",
            "users",
            "alembic_version",
        ):
            connection.execute(text(f"DROP TABLE IF EXISTS {table}"))


@pytest.fixture
def empty_test_engine(monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    if not (make_url(database_url).database or "").endswith("_test"):
        pytest.fail("Integration tests require an explicitly disposable _test database")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("APP_ENV", "test")
    get_settings.cache_clear()
    engine = get_engine(Settings(_env_file=None))
    drop_test_tables(engine)
    try:
        yield engine
    finally:
        drop_test_tables(engine)
        engine.dispose()
        get_settings.cache_clear()


@pytest.fixture
def auth_engine(empty_test_engine: Engine) -> Engine:
    config = Config(str(ALEMBIC_INI))
    heads = ScriptDirectory.from_config(config).get_heads()
    assert len(heads) == 1, "Integration tests require exactly one Alembic head"
    command.upgrade(config, heads[0])
    return empty_test_engine


@pytest.fixture
def mutation_app(auth_engine: Engine):
    from app.core.database import get_session_factory
    from app.core.security import PasswordService
    from app.main import create_app
    from app.models import User, UserRole

    app = create_app(Settings(database_url=auth_engine.url.render_as_string(hide_password=False)))
    app.state.engine.dispose()
    app.state.engine = auth_engine
    app.state.session_factory = get_session_factory(auth_engine)
    with app.state.session_factory.begin() as session:
        session.add(
            User(
                email="mutations@example.com",
                role=UserRole.HR,
                is_active=True,
                password_hash=PasswordService().hash("original-password"),
            )
        )
    return app


@pytest.fixture
def login_cookies(mutation_app):
    from fastapi.testclient import TestClient

    def login():
        response = TestClient(mutation_app).post(
            "/api/v1/auth/login",
            headers={"Origin": "http://testserver"},
            json={"email": "mutations@example.com", "password": "original-password"},
        )
        assert response.status_code == 200
        return dict(response.cookies)

    return login
