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
            cookie_secure=True,
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
            cookie_secure=True,
            database_url="postgresql+psycopg://user:password@db/production",
            cors_allowed_origins=[origin],
        )


@pytest.mark.parametrize("app_env", ["test", "production"])
@pytest.mark.parametrize("secret", [None, "development-only-change-me-signing-key", "too-short"])
def test_nondevelopment_requires_explicit_strong_signing_key(
    monkeypatch: pytest.MonkeyPatch, app_env: str, secret: str | None
) -> None:
    monkeypatch.delenv("AUTH_ACCESS_SECRET", raising=False)
    if secret is not None:
        monkeypatch.setenv("AUTH_ACCESS_SECRET", secret)

    with pytest.raises(ValidationError, match="signing key") as error:
        Settings(_env_file=None, app_env=app_env, cookie_secure=True)

    if secret is not None:
        assert secret not in str(error.value)


def test_production_requires_secure_cookies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COOKIE_SECURE", "false")

    with pytest.raises(ValidationError, match="secure cookies"):
        Settings(_env_file=None, app_env="production")


def test_auth_environment_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_ACCESS_SECRET", "a" * 32)
    monkeypatch.setenv("WEB_ORIGIN", "https://hr.example.com:8443")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("ACCESS_TOKEN_MINUTES", "20")
    monkeypatch.setenv("REFRESH_SESSION_DAYS", "10")

    settings = Settings(_env_file=None, app_env="production")

    assert settings.access_signing_key.get_secret_value() == "a" * 32
    assert "a" * 32 not in repr(settings)
    assert settings.web_origin == "https://hr.example.com:8443"
    assert settings.cookie_secure is True
    assert settings.access_token_minutes == 20
    assert settings.refresh_session_days == 10


def test_auth_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "AUTH_ACCESS_SECRET",
        "COOKIE_SECURE",
        "ACCESS_TOKEN_MINUTES",
        "REFRESH_SESSION_DAYS",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None, app_env="development")

    assert (
        settings.access_signing_key.get_secret_value() == "development-only-change-me-signing-key"
    )
    assert settings.cookie_secure is False
    assert settings.access_token_minutes == 15
    assert settings.refresh_session_days == 7


@pytest.mark.parametrize(
    "origin", ["http://localhost:3000", "https://hr.example.com", "http://[::1]:3000"]
)
def test_accepts_exact_web_origin(origin: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEB_ORIGIN", origin)

    assert Settings(_env_file=None).web_origin == origin


@pytest.mark.parametrize(
    "origin",
    [
        "",
        "*",
        "https://",
        "https://*",
        "ftp://hr.example.com",
        "https://user:password@hr.example.com",
        "https://hr.example.com/",
        "https://hr.example.com/path",
        "https://hr.example.com?query=yes",
        "https://hr.example.com#fragment",
        "https://hr.example.com?",
        "https://hr.example.com#",
        "https://hr.example.com:invalid",
        "https://hr.example.com:65536",
        "https://hr.example.com:",
        " https://hr.example.com",
        "https://hr.example.com\n",
        "https://hr.example.com,https://other.example.com",
        "https://hr.example.com\\evil",
        "https://hr*.example.com",
        "https://hr.example.com\x01",
        "https://[::1]suffix",
        "https://hr.example.com%2fpath",
    ],
)
def test_rejects_inexact_web_origin(origin: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEB_ORIGIN", origin)

    with pytest.raises(ValidationError, match="WEB_ORIGIN"):
        Settings(_env_file=None)


@pytest.mark.parametrize("control", [chr(value) for value in (*range(32), 127)])
@pytest.mark.parametrize("position", ["leading", "authority", "trailing"])
def test_rejects_raw_ascii_controls_in_web_origin(control: str, position: str) -> None:
    origins = {
        "leading": f"{control}https://hr.example.com",
        "authority": f"https://hr{control}.example.com",
        "trailing": f"https://hr.example.com{control}",
    }

    with pytest.raises(ValidationError, match="WEB_ORIGIN"):
        # Constructor input also covers NUL, which cannot be stored in the environment.
        Settings(_env_file=None, web_origin=origins[position])


@pytest.mark.parametrize("name", ["ACCESS_TOKEN_MINUTES", "REFRESH_SESSION_DAYS"])
@pytest.mark.parametrize("value", ["0", "-1"])
def test_rejects_nonpositive_auth_lifetimes(
    name: str, value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_auth_validation_error_hides_signing_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "sensitive-short-key"
    monkeypatch.setenv("AUTH_ACCESS_SECRET", secret)

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, app_env="production", cookie_secure=True)

    assert secret not in str(error.value)


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
