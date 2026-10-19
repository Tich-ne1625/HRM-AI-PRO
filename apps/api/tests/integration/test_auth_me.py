from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import TokenService
from app.models import AuthSession, User, UserRole


def test_me_returns_only_current_identity_without_requiring_origin(mutation_app, login_cookies):
    cookies = login_cookies()
    response = TestClient(mutation_app, cookies=cookies).get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json() == {
        "id": response.json()["id"],
        "email": "mutations@example.com",
        "role": "HR",
        "is_active": True,
        "employee_id": None,
    }
    assert response.headers["cache-control"] == "no-store"
    assert not response.headers.get_list("set-cookie")
    assert all(value not in response.text for value in cookies.values())


@pytest.mark.parametrize("state", [
    "missing", "malformed", "expired", "wrong_signature", "missing_user", "inactive",
    "missing_family", "expired_family", "revoked_family", "consumed_family", "foreign_family",
])
def test_me_rejects_invalid_identity_with_one_sanitized_error(
    mutation_app, login_cookies, auth_engine, state, caplog,
):
    cookies = login_cookies()
    issuer = TokenService(mutation_app.state.settings.access_signing_key)
    claims = issuer.decode_access_token(cookies["insighthr_access"])
    if state == "missing":
        cookies.pop("insighthr_access")
    elif state == "malformed":
        cookies["insighthr_access"] = "malformed-sensitive-token"
    elif state in {"expired", "wrong_signature", "missing_user", "missing_family"}:
        token_service = TokenService(
            "wrong-key-for-signature-check-at-least-32-characters"
            if state == "wrong_signature" else mutation_app.state.settings.access_signing_key,
            clock=lambda: datetime.now(UTC) - timedelta(hours=1)
            if state == "expired" else datetime.now(UTC),
        )
        cookies["insighthr_access"] = token_service.create_access_token(
            uuid4() if state == "missing_user" else claims.user_id,
            uuid4() if state == "missing_family" else claims.family_id,
        )
    else:
        with Session(auth_engine) as session, session.begin():
            row = session.scalars(select(AuthSession)).one()
            user = session.scalars(select(User)).one()
            if state == "inactive":
                user.is_active = False
            elif state == "expired_family":
                row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            elif state == "revoked_family":
                row.revoked_at = datetime.now(UTC)
            elif state == "consumed_family":
                row.consumed_at = datetime.now(UTC)
            else:
                other = User(email="other@example.com", password_hash="unused", role=UserRole.HR)
                session.add(other)
                session.flush()
                row.user_id = other.id
    response = TestClient(mutation_app, cookies=cookies).get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"] == {
        "code": "authentication_required", "message": "Authentication required", "details": [],
    }
    assert all(value not in response.text + caplog.text for value in cookies.values())


def test_current_database_role_governs_identity_and_policy(
    mutation_app, login_cookies, auth_engine,
):
    from app.core.policies import AuthContext, require_roles

    @mutation_app.get("/test-admin")
    def admin(context: Annotated[AuthContext, Depends(require_roles(UserRole.ADMIN))]):
        return {"role": context.user.role}

    cookies = login_cookies()
    client = TestClient(mutation_app, cookies=cookies)
    assert client.get("/test-admin").status_code == 403
    with Session(auth_engine) as session, session.begin():
        session.scalars(select(User)).one().role = UserRole.ADMIN
    assert client.get("/test-admin").json() == {"role": "ADMIN"}
    assert client.get("/api/v1/auth/me").json()["role"] == "ADMIN"
    with Session(auth_engine) as session, session.begin():
        session.scalars(select(User)).one().role = UserRole.EMPLOYEE
    assert client.get("/test-admin").json()["error"]["code"] == "forbidden"


def test_replay_revokes_original_and_rotated_access_over_http(mutation_app, login_cookies):
    cookies = login_cookies()
    client = TestClient(mutation_app, cookies=cookies)
    headers = {"Origin": "http://testserver", "X-CSRF-Token": cookies["insighthr_csrf"]}
    rotated = client.post("/api/v1/auth/refresh", headers=headers)
    assert rotated.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 200
    replay = TestClient(mutation_app, cookies=cookies)
    assert replay.post("/api/v1/auth/refresh", headers=headers).status_code == 401
    for credentials in (cookies, dict(rotated.cookies)):
        response = TestClient(mutation_app, cookies=credentials).get("/api/v1/auth/me")
        assert response.status_code == 401
