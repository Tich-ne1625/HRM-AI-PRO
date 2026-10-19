from datetime import UTC, datetime

from fastapi import Response

from app.core.config import Settings
from app.core.security import ACCESS_COOKIE_NAME, CSRF_COOKIE_NAME, REFRESH_COOKIE_NAME
from app.modules.auth.service import AuthResult

REFRESH_COOKIE_PATH = "/api/v1/auth/refresh"


def set_auth_cookies(
    response: Response, result: AuthResult, settings: Settings, *, now: datetime | None = None
) -> None:
    remaining = max(0, int((result.expires_at - (now or datetime.now(UTC))).total_seconds()))
    response.set_cookie(
        ACCESS_COOKIE_NAME,
        result.access_token.get_secret_value(),
        max_age=settings.access_token_minutes * 60,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    for name, token, path, http_only in (
        (REFRESH_COOKIE_NAME, result.refresh_token, REFRESH_COOKIE_PATH, True),
        (CSRF_COOKIE_NAME, result.csrf_token, "/", False),
    ):
        response.set_cookie(
            name,
            token.get_secret_value(),
            max_age=remaining,
            expires=result.expires_at,
            path=path,
            secure=settings.cookie_secure,
            httponly=http_only,
            samesite="lax",
        )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    for name, path, http_only in (
        (ACCESS_COOKIE_NAME, "/", True),
        (REFRESH_COOKIE_NAME, REFRESH_COOKIE_PATH, True),
        (CSRF_COOKIE_NAME, "/", False),
    ):
        response.delete_cookie(
            name, path=path, secure=settings.cookie_secure, httponly=http_only, samesite="lax"
        )
