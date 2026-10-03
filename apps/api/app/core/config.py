from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    """Environment-backed application settings with secret-safe representation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_name: str = "InsightHR API"
    app_env: Literal["development", "test", "production"] = "development"
    database_url: SecretStr
    cors_allowed_origins: list[str] = []
    alembic_config_path: Path = Path("alembic.ini")

    @model_validator(mode="after")
    def validate_security_constraints(self) -> Self:
        database_url = self.database_url.get_secret_value()
        if not database_url.startswith("postgresql+psycopg://"):
            raise ValueError("PostgreSQL with the psycopg driver is required")

        try:
            parsed_database_url = make_url(database_url)
            _ = parsed_database_url.port
        except (ArgumentError, ValueError) as error:
            raise ValueError("database_url must be a valid PostgreSQL connection URL") from error
        if not parsed_database_url.host or not parsed_database_url.database:
            raise ValueError("database_url must be a valid PostgreSQL connection URL")

        for origin in self.cors_allowed_origins:
            if origin == "*":
                if self.app_env == "production":
                    raise ValueError("Production CORS origins must use HTTPS")
                continue
            try:
                parsed = urlsplit(origin)
                _ = parsed.port
            except ValueError as error:
                raise ValueError("CORS entries must be valid HTTP(S) origins") from error
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.hostname == "*"
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("CORS entries must be valid HTTP(S) origins")
            if self.app_env == "production" and (
                parsed.scheme != "https"
                or parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            ):
                raise ValueError("Production CORS origins must use HTTPS")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

