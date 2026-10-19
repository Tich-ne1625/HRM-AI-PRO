from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import PasswordService, TokenService, hash_opaque_token
from app.models import AuditLog, AuthSession, User
from app.modules.audit.service import AuditWriter

pytestmark = pytest.mark.integration
PATHS = ["refresh", "logout", "change-password"]


def test_old_password_login_cannot_commit_a_surviving_family_after_password_change(
    mutation_app,
    login_cookies,
    auth_engine,
    monkeypatch,
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, Lock
    from time import monotonic, sleep

    from sqlalchemy import func

    from app.modules.users.repository import UserRepository

    cookies = login_cookies()
    claims = TokenService(mutation_app.state.settings.access_signing_key).decode_access_token(
        cookies["insighthr_access"]
    )
    login_verified, release_login, change_started = Event(), Event(), Event()
    guard = Lock()
    first_verification = True
    change_pid = []
    original_verify = PasswordService.verify
    original_lock = UserRepository.get_by_id_for_update

    def pause_login(self, password, encoded_hash):
        nonlocal first_verification
        valid = original_verify(self, password, encoded_hash)
        with guard:
            pause = first_verification
            first_verification = False
        if pause:
            login_verified.set()
            assert release_login.wait(timeout=15)
        return valid

    def observe_change_lock(self, user_id):
        change_pid.append(self.session.scalar(select(func.pg_backend_pid())))
        change_started.set()
        return original_lock(self, user_id)

    monkeypatch.setattr(PasswordService, "verify", pause_login)
    monkeypatch.setattr(UserRepository, "get_by_id_for_update", observe_change_lock)

    def concurrent_login():
        return TestClient(mutation_app).post(
            "/api/v1/auth/login",
            headers={"Origin": "http://testserver"},
            json={"email": "mutations@example.com", "password": "original-password"},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        login_future = executor.submit(concurrent_login)
        try:
            assert login_verified.wait(timeout=10)
            change_future = executor.submit(mutate, mutation_app, "change-password", cookies)
            assert change_started.wait(timeout=10)
            # Allow the password change to commit if login does not hold the
            # owner lock. With the fix it instead waits on that PostgreSQL lock.
            deadline = monotonic() + 10
            with Session(auth_engine) as observer:
                while not change_future.done():
                    blockers = observer.scalar(select(func.pg_blocking_pids(change_pid[0])))
                    if blockers:
                        break
                    assert monotonic() < deadline, "Password change neither committed nor blocked"
                    sleep(0.01)
        finally:
            release_login.set()
        login_response = login_future.result(timeout=15)
        change_response = change_future.result(timeout=15)
    assert login_response.status_code == 200
    assert change_response.status_code == 204
    with Session(auth_engine) as session:
        rows = session.scalars(select(AuthSession)).all()
        assert len(rows) == 2
        assert all((row.revoked_at is None) == (row.family_id == claims.family_id) for row in rows)
        assert PasswordService().verify(
            "replacement-password", session.scalars(select(User)).one().password_hash
        )


def mutate(app, path, cookies, *, origin="http://testserver", csrf="default", body=None):
    headers = {
        "Cookie": "; ".join(f"{key}={value}" for key, value in cookies.items()),
        "X-Request-ID": "mutation-test-123",
    }
    if origin is not None:
        headers["Origin"] = origin
    if csrf == "default":
        csrf = cookies.get("insighthr_csrf")
    if csrf is not None:
        headers["X-CSRF-Token"] = csrf
    return TestClient(app, raise_server_exceptions=False).post(
        f"/api/v1/auth/{path}",
        headers=headers,
        json=body or {"old_password": "original-password", "new_password": "replacement-password"},
    )


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize(
    "origin",
    [None, "http://evil.test", "http://testserver/", "http://TESTSERVER", "http://testserver:80"],
)
def test_origin_rejection_precedes_csrf_and_preserves_state(
    mutation_app,
    login_cookies,
    auth_engine,
    path,
    origin,
):
    cookies = login_cookies()
    response = mutate(mutation_app, path, cookies, origin=origin, csrf="wrong-csrf")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "origin_not_allowed"
    assert_unchanged(auth_engine, 1)


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize(
    "case", ["cookie_missing", "header_missing", "different", "cross_family", "unicode"]
)
def test_csrf_is_required_constant_time_compatible_and_bound_to_current_family(
    mutation_app,
    login_cookies,
    auth_engine,
    path,
    case,
):
    cookies = login_cookies()
    csrf = cookies["insighthr_csrf"]
    count = 1
    if case == "cookie_missing":
        cookies.pop("insighthr_csrf")
    elif case == "header_missing":
        csrf = None
    elif case == "different":
        csrf = "mismatched-csrf"
    elif case == "cross_family":
        other = login_cookies()
        csrf = cookies["insighthr_csrf"] = other["insighthr_csrf"]
        count = 2
    elif case == "unicode":
        cookies["insighthr_csrf"] = csrf = "invalid-csrf-%C3%A9"
    response = mutate(mutation_app, path, cookies, csrf=csrf)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"
    assert_unchanged(auth_engine, count)


def assert_unchanged(engine, count):
    with Session(engine) as session:
        rows = session.scalars(select(AuthSession)).all()
        assert len(rows) == count
        assert all(row.consumed_at is row.revoked_at is row.replacement_id is None for row in rows)
        assert PasswordService().verify(
            "original-password", session.scalars(select(User)).one().password_hash
        )
        assert len(session.scalars(select(AuditLog)).all()) == count


def test_cross_family_csrf_cannot_trigger_consumed_refresh_replay_revocation(
    mutation_app,
    login_cookies,
    auth_engine,
):
    cookies = login_cookies()
    assert mutate(mutation_app, "refresh", cookies).status_code == 204
    other = login_cookies()
    cookies["insighthr_csrf"] = other["insighthr_csrf"]
    response = mutate(mutation_app, "refresh", cookies)
    assert response.status_code == 403 and response.json()["error"]["code"] == "csrf_failed"
    with Session(auth_engine) as session:
        rows = session.scalars(select(AuthSession)).all()
        assert len(rows) == 3 and all(row.revoked_at is None for row in rows)


def test_logout_revokes_only_current_family_audits_and_clears_exact_cookies(
    mutation_app,
    login_cookies,
    auth_engine,
):
    cookies = login_cookies()
    other = login_cookies()
    # Browser will not send the refresh-scoped cookie to logout.
    cookies.pop("insighthr_refresh")
    response = mutate(mutation_app, "logout", cookies)
    assert response.status_code == 204 and response.content == b""
    assert response.headers["cache-control"] == "no-store"
    deletions = SimpleCookie()
    for value in response.headers.get_list("set-cookie"):
        deletions.load(value)
    assert set(deletions) == {"insighthr_access", "insighthr_refresh", "insighthr_csrf"}
    for name, path, http_only in [
        ("insighthr_access", "/", True),
        ("insighthr_refresh", "/api/v1/auth/refresh", True),
        ("insighthr_csrf", "/", False),
    ]:
        cookie = deletions[name]
        assert cookie.value == "" and cookie["max-age"] == "0"
        assert cookie["path"] == path and cookie["samesite"] == "lax"
        assert bool(cookie["httponly"]) is http_only
        assert bool(cookie["secure"]) is mutation_app.state.settings.cookie_secure
    claims = TokenService(mutation_app.state.settings.access_signing_key).decode_access_token(
        cookies["insighthr_access"]
    )
    with Session(auth_engine) as session:
        rows = session.scalars(select(AuthSession)).all()
        assert all(
            (row.revoked_at is not None) == (row.family_id == claims.family_id) for row in rows
        )
        audit = session.scalars(select(AuditLog).where(AuditLog.action == "auth.logout")).one()
        assert audit.actor_id == claims.user_id and audit.entity_id == str(claims.family_id)
        assert audit.request_id == "mutation-test-123" and audit.metadata_ == {}
        assert (
            session.scalars(
                select(AuthSession).where(
                    AuthSession.token_hash == hash_opaque_token(other["insighthr_refresh"])
                )
            )
            .one()
            .revoked_at
            is None
        )
    assert mutate(mutation_app, "logout", cookies).status_code == 401


@pytest.mark.parametrize("password", ["123456789012", "p" * 128, " mật khẩu mới "])
def test_password_change_preserves_current_family_revokes_all_other_families_and_audits(
    mutation_app,
    login_cookies,
    auth_engine,
    password,
):
    cookies = login_cookies()
    other = login_cookies()
    assert mutate(mutation_app, "refresh", other).status_code == 204
    cookies.pop("insighthr_refresh")
    with Session(auth_engine) as session:
        old_hash = session.scalars(select(User)).one().password_hash
    response = mutate(
        mutation_app,
        "change-password",
        cookies,
        body={
            "old_password": "original-password",
            "new_password": password,
        },
    )
    assert response.status_code == 204 and response.content == b""
    assert not response.headers.get_list("set-cookie")
    claims = TokenService(mutation_app.state.settings.access_signing_key).decode_access_token(
        cookies["insighthr_access"]
    )
    with Session(auth_engine) as session:
        user = session.scalars(select(User)).one()
        assert user.password_hash != old_hash and user.password_hash.startswith("$argon2id$")
        assert PasswordService().verify(password, user.password_hash)
        assert not PasswordService().verify("original-password", user.password_hash)
        rows = session.scalars(select(AuthSession)).all()
        assert len(rows) == 3
        assert all((row.revoked_at is None) == (row.family_id == claims.family_id) for row in rows)
        audit = session.scalars(
            select(AuditLog).where(AuditLog.action == "user.password_changed")
        ).one()
        assert audit.actor_id == user.id and audit.entity_id == str(user.id)
        assert audit.request_id == "mutation-test-123" and audit.metadata_ == {}
    assert mutate(mutation_app, "logout", cookies).status_code == 204


@pytest.mark.parametrize(
    "old,new,status",
    [
        ("wrong-old-password", "replacement-password", 401),
        ("original-password", "original-password", 422),
        ("original-password", "s" * 11, 422),
        ("original-password", "s" * 129, 422),
    ],
)
def test_password_rejection_does_not_change_hash_sessions_or_audits(
    mutation_app,
    login_cookies,
    auth_engine,
    old,
    new,
    status,
    caplog,
):
    cookies = login_cookies()
    response = mutate(
        mutation_app, "change-password", cookies, body={"old_password": old, "new_password": new}
    )
    assert response.status_code == status
    for secret in [old, new, *cookies.values()]:
        assert secret not in response.text + caplog.text
    assert_unchanged(auth_engine, 1)


@pytest.mark.parametrize("path", ["logout", "change-password"])
@pytest.mark.parametrize(
    "state",
    [
        "missing",
        "malformed",
        "expired",
        "wrong_signature",
        "wrong_user",
        "revoked",
        "family_expired",
        "inactive",
    ],
)
def test_mutation_requires_valid_access_and_active_owned_family(
    mutation_app,
    login_cookies,
    auth_engine,
    path,
    state,
):
    cookies = login_cookies()
    tokens = TokenService(mutation_app.state.settings.access_signing_key)
    claims = tokens.decode_access_token(cookies["insighthr_access"])
    if state == "missing":
        cookies.pop("insighthr_access")
    elif state == "malformed":
        cookies["insighthr_access"] = "malformed-access-secret"
    elif state in {"expired", "wrong_signature", "wrong_user"}:
        from uuid import uuid4

        issuer = TokenService(
            "wrong-signing-key-longer-than-32-characters"
            if state == "wrong_signature"
            else mutation_app.state.settings.access_signing_key,
            clock=lambda: (
                datetime.now(UTC) - timedelta(hours=1) if state == "expired" else datetime.now(UTC)
            ),
        )
        cookies["insighthr_access"] = issuer.create_access_token(
            uuid4() if state == "wrong_user" else claims.user_id,
            claims.family_id,
        )
    else:
        with Session(auth_engine) as session, session.begin():
            row = session.scalars(select(AuthSession)).one()
            if state == "revoked":
                row.revoked_at = datetime.now(UTC)
            elif state == "family_expired":
                row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            else:
                session.scalars(select(User)).one().is_active = False
    response = mutate(mutation_app, path, cookies)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_session"


@pytest.mark.parametrize("path", ["logout", "change-password"])
def test_mutation_audit_failure_rolls_back_every_change_and_leaks_no_secrets(
    mutation_app,
    login_cookies,
    auth_engine,
    monkeypatch,
    caplog,
    path,
):
    cookies = login_cookies()
    login_cookies()

    def fail(*args, **kwargs):
        raise SQLAlchemyError("secret-database-password")

    monkeypatch.setattr(AuditWriter, "record", fail)
    response = mutate(mutation_app, path, cookies)
    assert response.status_code == 500
    assert not response.headers.get_list("set-cookie")
    for secret in [*cookies.values(), "secret-database-password", "replacement-password"]:
        assert secret not in response.text + caplog.text
    assert_unchanged(auth_engine, 2)
