from __future__ import annotations

from functools import lru_cache
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed application settings with secret-safe representation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "InsightHR API"
    app_env: Literal["development", "test", "production"] = "development"
    database_url: SecretStr
    cors_allowed_origins: list[str] = []

    @model_validator(mode="after")
    def validate_security_constraints(self) -> Self:
        database_url = self.database_url.get_secret_value()
        if not database_url.startswith("postgresql+psycopg://"):
            raise ValueError("PostgreSQL with the psycopg driver is required")

        if self.app_env == "production":
            for origin in self.cors_allowed_origins:
                parsed = urlsplit(origin)
                if (
                    origin == "*"
                    or parsed.scheme != "https"
                    or parsed.hostname in {"localhost", "127.0.0.1", "::1"}
                ):
                    raise ValueError("Production CORS origins must use HTTPS")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

