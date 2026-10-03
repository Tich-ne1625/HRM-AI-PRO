from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_accepts_psycopg_url_without_revealing_password() -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://user:super-secret@db/test",
    )

    assert settings.database_url.get_secret_value().startswith("postgresql+psycopg://")
    assert "super-secret" not in repr(settings)


def test_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)

    assert "database_url" in str(error.value)


def test_rejects_non_postgresql_database_url() -> None:
    with pytest.raises(ValidationError, match="PostgreSQL with the psycopg driver is required"):
        Settings(app_env="test", database_url="sqlite:///local.db")


@pytest.mark.parametrize(
    "origin",
    ["*", "http://localhost:3000", "http://127.0.0.1:3000"],
)
def test_production_rejects_unsafe_cors_origins(origin: str) -> None:
    with pytest.raises(ValidationError, match="Production CORS origins must use HTTPS"):
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://user:password@db/production",
            cors_allowed_origins=[origin],
        )

