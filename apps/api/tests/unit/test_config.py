from __future__ import annotations

from pathlib import Path

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


def test_validation_errors_do_not_reveal_database_credentials() -> None:
    secret = "validation-secret"

    with pytest.raises(ValidationError) as error:
        Settings(
            app_env="production",
            database_url=f"postgresql+psycopg://user:{secret}@db/production",
            cors_allowed_origins=["*"],
        )

    assert secret not in str(error.value)


def test_accepts_explicit_alembic_config_path() -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://user:password@db/test",
        alembic_config_path="/app/alembic.ini",
    )

    assert settings.alembic_config_path == Path("/app/alembic.ini")


def test_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)

    assert "database_url" in str(error.value)


def test_rejects_non_postgresql_database_url_without_revealing_password() -> None:
    secret = "invalid-scheme-secret"

    with pytest.raises(
        ValidationError,
        match="PostgreSQL with the psycopg driver is required",
    ) as error:
        Settings(
            app_env="test",
            database_url=f"mysql://user:{secret}@db/test",
        )

    assert secret not in str(error.value)


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+psycopg:///missing-host",
        "postgresql+psycopg://user:password@db:not-a-port/test",
    ],
)
def test_rejects_malformed_postgresql_url(database_url: str) -> None:
    with pytest.raises(ValidationError, match="valid PostgreSQL connection URL"):
        Settings(app_env="test", database_url=database_url)


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


@pytest.mark.parametrize(
    "origin",
    ["https://", "https://*", "https://example.com/path", "https://user@example.com"],
)
def test_rejects_malformed_cors_origins(origin: str) -> None:
    with pytest.raises(ValidationError, match=r"valid HTTP\(S\) origins"):
        Settings(
            app_env="test",
            database_url="postgresql+psycopg://user:password@db/test",
            cors_allowed_origins=[origin],
        )

