from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import TokenService, hash_opaque_token
from app.models import AuditLog, AuthSession, User
from app.modules.audit.service import AuditWriter
from app.modules.auth.repository import AuthSessionRepository

pytestmark = pytest.mark.integration


def refresh(app, cookies):
    return TestClient(app, raise_server_exceptions=False).post(
        "/api/v1/auth/refresh",
        headers={
            "Origin": "http://testserver",
            "X-CSRF-Token": cookies["insighthr_csrf"],
            "Cookie": "; ".join(f"{key}={value}" for key, value in cookies.items()),
        },
    )


def test_rotation_consumes_links_one_successor_without_sliding_expiry(
    mutation_app,
    login_cookies,
    auth_engine,
):
    cookies = login_cookies()
    response = refresh(mutation_app, cookies)
    assert response.status_code == 204
    assert response.content == b"" and response.headers["cache-control"] == "no-store"
    assert response.cookies["insighthr_refresh"] != cookies["insighthr_refresh"]
    assert response.cookies["insighthr_csrf"] == cookies["insighthr_csrf"]
    claims = TokenService(mutation_app.state.settings.access_signing_key).decode_access_token(
        response.cookies["insighthr_access"]
    )
    with Session(auth_engine) as session:
        rows = session.scalars(select(AuthSession)).all()
        assert len(rows) == 2
        old = next(row for row in rows if row.consumed_at is not None)
        new = next(row for row in rows if row.consumed_at is None)
        assert old.replacement_id == new.id
        assert old.revoked_at is new.revoked_at is new.replacement_id is None
        assert old.expires_at == new.expires_at
        assert old.family_id == new.family_id == claims.family_id
        assert old.user_id == new.user_id == claims.user_id
        assert old.csrf_hash == new.csrf_hash == hash_opaque_token(cookies["insighthr_csrf"])
        assert old.token_hash == hash_opaque_token(cookies["insighthr_refresh"])
        assert new.token_hash == hash_opaque_token(response.cookies["insighthr_refresh"])
        for row in rows:
            assert len(row.token_hash) == 64 and len(row.csrf_hash) == 64
            assert row.token_hash not in cookies.values()
        actions = [audit.action for audit in session.scalars(select(AuditLog))]
        assert actions == ["auth.login_succeeded", "auth.refresh_succeeded"]


@pytest.mark.parametrize("state", ["missing", "random", "expired", "revoked", "inactive"])
def test_invalid_refresh_is_sanitized_and_does_not_mutate(
    mutation_app,
    login_cookies,
    auth_engine,
    state,
    caplog,
):
    cookies = login_cookies()
    with Session(auth_engine) as session, session.begin():
        row = session.scalars(select(AuthSession)).one()
        if state == "expired":
            row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        elif state == "revoked":
            row.revoked_at = datetime.now(UTC)
        elif state == "inactive":
            session.scalars(select(User)).one().is_active = False
    if state == "missing":
        cookies.pop("insighthr_refresh")
    elif state == "random":
        cookies["insighthr_refresh"] = "opaque-unknown-refresh-secret"
    response = refresh(mutation_app, cookies)
    assert response.status_code == 401
    assert response.json()["error"] == {
        "code": "invalid_session",
        "message": "Invalid session",
        "details": [],
    }
    assert not response.headers.get_list("set-cookie")
    for secret in cookies.values():
        assert secret not in response.text + caplog.text
    with Session(auth_engine) as session:
        assert len(session.scalars(select(AuthSession)).all()) == 1
        assert session.scalars(select(AuthSession)).one().consumed_at is None


def test_replaying_any_consumed_ancestor_revokes_whole_family(
    mutation_app,
    login_cookies,
    auth_engine,
):
    original = login_cookies()
    first = refresh(mutation_app, original)
    assert first.status_code == 204
    second = refresh(mutation_app, dict(first.cookies))
    assert second.status_code == 204
    response = refresh(mutation_app, original)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "refresh_reuse_detected"
    with Session(auth_engine) as session:
        rows = session.scalars(select(AuthSession)).all()
        assert len(rows) == 3 and all(row.revoked_at is not None for row in rows)
        assert "auth.refresh_reuse_detected" in [
            audit.action for audit in session.scalars(select(AuditLog))
        ]
    assert refresh(mutation_app, dict(second.cookies)).json()["error"]["code"] == "invalid_session"


def test_same_refresh_concurrently_creates_one_successor_and_revokes_access_families(
    mutation_app,
    login_cookies,
    auth_engine,
    monkeypatch,
):
    cookies = login_cookies()
    barrier = Barrier(2)
    sessions = []
    original = AuthSessionRepository.get_by_token_hash_for_update

    def locked_read(self, token_hash):
        sessions.append(self.session)
        barrier.wait(timeout=10)
        return original(self, token_hash)

    monkeypatch.setattr(AuthSessionRepository, "get_by_token_hash_for_update", locked_read)
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: refresh(mutation_app, cookies), range(2)))
    assert len(sessions) == 2 and sessions[0] is not sessions[1]
    assert sorted(response.status_code for response in responses) == [204, 401]
    failure = next(response for response in responses if response.status_code == 401)
    assert failure.json()["error"]["code"] == "refresh_reuse_detected"
    success = next(response for response in responses if response.status_code == 204)
    tokens = [cookies["insighthr_access"], success.cookies["insighthr_access"]]
    with Session(auth_engine) as session:
        rows = session.scalars(select(AuthSession)).all()
        assert len(rows) == 2 and all(row.revoked_at is not None for row in rows)
        for token in tokens:
            claims = TokenService(
                mutation_app.state.settings.access_signing_key
            ).decode_access_token(token)
            assert (
                AuthSessionRepository(session).get_active_family(
                    claims.family_id, now=datetime.now(UTC)
                )
                == []
            )


@pytest.mark.parametrize("replay", [False, True])
def test_refresh_audit_failure_rolls_back_rotation_or_replay_revocation(
    mutation_app,
    login_cookies,
    auth_engine,
    monkeypatch,
    caplog,
    replay,
):
    cookies = login_cookies()
    if replay:
        assert refresh(mutation_app, cookies).status_code == 204

    def fail(*args, **kwargs):
        raise SQLAlchemyError("secret-database-password")

    monkeypatch.setattr(AuditWriter, "record", fail)
    response = refresh(mutation_app, cookies)
    assert response.status_code == 500
    assert not response.headers.get_list("set-cookie")
    for secret in [*cookies.values(), "secret-database-password"]:
        assert secret not in response.text + caplog.text
    with Session(auth_engine) as session:
        rows = session.scalars(select(AuthSession)).all()
        assert len(rows) == (2 if replay else 1)
        assert all(row.revoked_at is None for row in rows)
        assert sum(row.consumed_at is not None for row in rows) == int(replay)
