from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from uuid import uuid4

import pytest
from fastapi import Response
from pydantic import SecretStr

from app.core.config import Settings
from app.modules.auth.cookies import clear_auth_cookies, set_auth_cookies
from app.modules.auth.schemas import CurrentUser
from app.modules.auth.service import AuthResult


@pytest.mark.parametrize("secure", [False, True])
@pytest.mark.parametrize("remaining", [604800, 123, 0, -10])
def test_cookie_policy_respects_absolute_family_expiry(secure: bool, remaining: int) -> None:
    now = datetime(2026, 10, 3, tzinfo=UTC)
    settings = Settings(cookie_secure=secure)
    result = AuthResult(
        user=CurrentUser(
            id=uuid4(), email="user@example.com", role="HR", is_active=True, employee_id=None
        ),
        access_token=SecretStr("access-token"),
        refresh_token=SecretStr("refresh-token"),
        csrf_token=SecretStr("csrf-token"),
        expires_at=now + timedelta(seconds=remaining),
    )
    response = Response()
    set_auth_cookies(response, result, settings, now=now)
    cookies: SimpleCookie[str] = SimpleCookie()
    for header in response.headers.getlist("set-cookie"):
        cookies.load(header)
    assert set(cookies) == {"insighthr_access", "insighthr_refresh", "insighthr_csrf"}
    for name, path, http_only, age, value in [
        ("insighthr_access", "/", True, 900, "access-token"),
        ("insighthr_refresh", "/api/v1/auth/refresh", True, max(0, remaining), "refresh-token"),
        ("insighthr_csrf", "/", False, max(0, remaining), "csrf-token"),
    ]:
        cookie = cookies[name]
        assert cookie.value == value
        assert cookie["path"] == path
        assert bool(cookie["httponly"]) is http_only
        assert cookie["samesite"].lower() == "lax"
        assert bool(cookie["secure"]) is secure
        assert int(cookie["max-age"]) == age
        assert not cookie["domain"]


@pytest.mark.parametrize("secure", [False, True])
def test_clear_cookies_matches_paths_and_security_attributes(secure: bool) -> None:
    response = Response()
    clear_auth_cookies(response, Settings(cookie_secure=secure))
    cookies: SimpleCookie[str] = SimpleCookie()
    for header in response.headers.getlist("set-cookie"):
        cookies.load(header)
    assert set(cookies) == {"insighthr_access", "insighthr_refresh", "insighthr_csrf"}
    for name, path, http_only in [
        ("insighthr_access", "/", True),
        ("insighthr_refresh", "/api/v1/auth/refresh", True),
        ("insighthr_csrf", "/", False),
    ]:
        assert cookies[name].value == ""
        assert cookies[name]["max-age"] == "0"
        assert cookies[name]["expires"]
        assert cookies[name]["path"] == path
        assert bool(cookies[name]["httponly"]) is http_only
        assert bool(cookies[name]["secure"]) is secure
        assert cookies[name]["samesite"].lower() == "lax"
