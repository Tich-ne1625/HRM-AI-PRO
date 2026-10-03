from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

DEVELOPMENT_ACCESS_SECRET = "development-only-change-me-signing-key"


class Settings(BaseSettings):
    """Environment-backed application settings with secret-safe representation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
        populate_by_name=True,
    )

    app_name: str = "InsightHR API"
    app_env: Literal["development", "test", "production"] = "development"
    database_url: SecretStr
    cors_allowed_origins: list[str] = []
    alembic_config_path: Path = Path("alembic.ini")
    access_signing_key: SecretStr = Field(
        default=SecretStr(DEVELOPMENT_ACCESS_SECRET), validation_alias="AUTH_ACCESS_SECRET"
    )
    web_origin: str = "http://localhost:3000"
    cookie_secure: bool = False
    access_token_minutes: int = Field(default=15, gt=0)
    refresh_session_days: int = Field(default=7, gt=0)

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
                parsed.scheme != "https" or parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            ):
                raise ValueError("Production CORS origins must use HTTPS")

        key = self.access_signing_key.get_secret_value()
        if self.app_env != "development" and (key == DEVELOPMENT_ACCESS_SECRET or len(key) < 32):
            raise ValueError("A nondefault signing key of at least 32 characters is required")
        if self.app_env == "production" and not self.cookie_secure:
            raise ValueError("Production requires secure cookies")

        if any(ord(character) < 32 or ord(character) == 127 for character in self.web_origin):
            raise ValueError("WEB_ORIGIN must be one exact HTTP(S) origin")
        try:
            web_origin = urlsplit(self.web_origin)
            _ = web_origin.port
        except ValueError:
            raise ValueError("WEB_ORIGIN must be one exact HTTP(S) origin") from None
        if (
            web_origin.scheme not in {"http", "https"}
            or not web_origin.hostname
            or web_origin.hostname == "*"
            or web_origin.username is not None
            or web_origin.password is not None
            or web_origin.path
            or web_origin.query
            or web_origin.fragment
            or web_origin.netloc.endswith(":")
            or re.fullmatch(
                r"(?:\[[0-9a-fA-F:.]+\]|[\w.-]+)(?::[0-9]+)?", web_origin.netloc
            )
            is None
            or any(character.isspace() for character in self.web_origin)
            or any(character in self.web_origin for character in "?#\\,")
        ):
            raise ValueError("WEB_ORIGIN must be one exact HTTP(S) origin")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
