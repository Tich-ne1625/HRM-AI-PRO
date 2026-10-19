from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import UUID

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event, func, select
from sqlalchemy.exc import InvalidRequestError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_session_factory
from app.core.security import PasswordService, TokenService, hash_opaque_token
from app.main import create_app
from app.models import AuditLog, AuthSession, User, UserRole
from app.modules.audit.service import AuditWriter
from app.modules.auth.service import AuthService

pytestmark = pytest.mark.integration
PASSWORD = "login-test-password"
ORIGIN = "http://testserver"


@pytest.fixture
def login_app(auth_engine: Engine) -> Iterator[FastAPI]:
    settings = Settings(database_url=auth_engine.url.render_as_string(hide_password=False))
    app = create_app(settings)
    # Reuse the migrated disposable database while preserving request-owned sessions.
    app.state.engine.dispose()
    app.state.engine = auth_engine
    app.state.session_factory = get_session_factory(auth_engine)
    with Session(auth_engine) as session, session.begin():
        session.add(
            User(
                email="strasse@example.com",
                password_hash=PasswordService().hash(PASSWORD),
                role=UserRole.HR,
                is_active=True,
            )
        )
    yield app


def test_login_normalizes_email_and_persists_only_hashes_with_atomic_audit(
    login_app: FastAPI, auth_engine: Engine
) -> None:
    before = datetime.now(UTC)
    response = TestClient(login_app).post(
        "/api/v1/auth/login",
        json={"email": "Straße@EXAMPLE.com", "password": PASSWORD},
        headers={"Origin": ORIGIN, "X-Request-ID": "login-request-123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"id", "email", "role", "is_active", "employee_id"}
    assert body == {
        "id": str(UUID(body["id"])),
        "email": "strasse@example.com",
        "role": "HR",
        "is_active": True,
        "employee_id": None,
    }
    assert PASSWORD not in response.text
    assert response.headers["cache-control"] == "no-store"
    claims = TokenService(login_app.state.settings.access_signing_key).decode_access_token(
        response.cookies["insighthr_access"]
    )
    assert claims.user_id == UUID(body["id"])
    assert claims.expires_at - claims.issued_at == timedelta(minutes=15)
    with Session(auth_engine) as session:
        row = session.scalars(select(AuthSession)).one()
        assert row.family_id == claims.family_id and row.user_id == claims.user_id
        assert before + timedelta(days=7) <= row.expires_at <= datetime.now(UTC) + timedelta(days=7)
        assert row.token_hash == hash_opaque_token(response.cookies["insighthr_refresh"])
        assert row.csrf_hash == hash_opaque_token(response.cookies["insighthr_csrf"])
        assert row.token_hash != response.cookies["insighthr_refresh"]
        assert row.consumed_at is row.revoked_at is row.replacement_id is None
        audit = session.scalars(select(AuditLog)).one()
        assert audit.action == "auth.login_succeeded"
        assert audit.actor_id == claims.user_id
        assert audit.entity_type == "auth_session" and audit.entity_id == str(row.family_id)
        assert audit.request_id == "login-request-123"
        assert audit.metadata_ == {}


def test_invalid_and_inactive_logins_are_equivalent_and_always_verify_argon2(
    login_app: FastAPI, auth_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_verify = PasswordService.verify
    verified_hashes: list[str] = []

    def verify(self: PasswordService, password: str, encoded_hash: str) -> bool:
        verified_hashes.append(encoded_hash)
        return original_verify(self, password, encoded_hash)

    monkeypatch.setattr(PasswordService, "verify", verify)
    client = TestClient(login_app)
    responses = []
    for email, password in [
        ("strasse@example.com", "wrong-password"),
        ("missing@example.com", "wrong-password"),
        ("other-missing@example.com", "wrong-password"),
    ]:
        responses.append(
            client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": password},
                headers={"Origin": ORIGIN},
            )
        )
    with Session(auth_engine) as session, session.begin():
        account = session.scalars(select(User)).one()
        account.is_active = False
        known_hash = account.password_hash
    responses.append(
        client.post(
            "/api/v1/auth/login",
            json={"email": "strasse@example.com", "password": PASSWORD},
            headers={"Origin": ORIGIN},
        )
    )
    assert len(verified_hashes) == 4
    assert verified_hashes[0] == verified_hashes[3] == known_hash
    assert verified_hashes[1] == verified_hashes[2] != known_hash
    assert verified_hashes[1].startswith("$argon2id$v=19$m=65536,t=3,p=4$")
    for response in responses:
        assert response.status_code == 401
        assert response.json()["error"] == {
            "code": "invalid_credentials", "message": "Invalid email or password", "details": []
        }
        assert not response.headers.get_list("set-cookie")
        assert PASSWORD not in response.text and "strasse" not in response.text
    with Session(auth_engine) as session:
        assert session.scalar(select(func.count()).select_from(AuthSession)) == 0
        audits = session.scalars(select(AuditLog)).all()
        assert len(audits) == 4
        assert all(
            audit.action == "auth.login_failed" and audit.metadata_ == {} for audit in audits
        )
        assert all("@" not in audit.entity_id for audit in audits)


@pytest.mark.parametrize(
    "origin",
    [
        None, "", "null", "http://testserver:80", "https://testserver", "http://sub.testserver",
        "http://user@testserver", "http://testserver/", "http://testserver/path",
        "http://testserver,http://evil.test", "http://testserver, http://evil.test",
        " http://testserver", "http://testserver ", "http://TESTSERVER",
    ],
)
def test_origin_rejected_before_login_service(
    login_app: FastAPI, auth_engine: Engine, monkeypatch: pytest.MonkeyPatch, origin: str | None
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("The login service must not execute for an unapproved Origin")

    monkeypatch.setattr(AuthService, "login", forbidden)
    response = TestClient(login_app).post(
        "/api/v1/auth/login",
        json={"email": "strasse@example.com", "password": PASSWORD},
        headers={} if origin is None else {"Origin": origin},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "origin_not_allowed"
    assert not response.headers.get_list("set-cookie")
    with Session(auth_engine) as session:
        assert session.scalar(select(func.count()).select_from(AuthSession)) == 0
        assert session.scalar(select(func.count()).select_from(AuditLog)) == 0


def test_duplicate_origin_headers_are_rejected(login_app: FastAPI) -> None:
    response = TestClient(login_app).post(
        "/api/v1/auth/login",
        json={"email": "strasse@example.com", "password": PASSWORD},
        headers=[("Origin", ORIGIN), ("Origin", ORIGIN)],
    )
    assert response.status_code == 403


def test_concurrent_logins_create_independent_families(
    login_app: FastAPI, auth_engine: Engine
) -> None:
    barrier = Barrier(2)

    def login() -> str:
        with TestClient(login_app) as client:
            barrier.wait(timeout=10)
            response = client.post(
                "/api/v1/auth/login",
                json={"email": "strasse@example.com", "password": PASSWORD},
                headers={"Origin": ORIGIN},
            )
            assert response.status_code == 200
            return response.cookies["insighthr_refresh"]

    with ThreadPoolExecutor(max_workers=2) as executor:
        tokens = list(executor.map(lambda _: login(), range(2)))
    assert tokens[0] != tokens[1]
    with Session(auth_engine) as session:
        rows = session.scalars(select(AuthSession)).all()
        assert len(rows) == 2 and len({row.family_id for row in rows}) == 2
        assert {row.token_hash for row in rows} == {hash_opaque_token(token) for token in tokens}
        assert session.scalar(select(func.count()).select_from(AuditLog)) == 2


def test_audit_failure_rolls_back_session_and_returns_sanitized_error(
    login_app: FastAPI, auth_engine: Engine, monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise SQLAlchemyError("secret-database-password")

    monkeypatch.setattr(AuditWriter, "record", fail)
    response = TestClient(login_app, raise_server_exceptions=False).post(
        "/api/v1/auth/login",
        json={"email": "strasse@example.com", "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 500
    assert "secret-database-password" not in response.text + caplog.text
    assert PASSWORD not in response.text + caplog.text
    assert not response.headers.get_list("set-cookie")
    with Session(auth_engine) as session:
        assert session.scalar(select(func.count()).select_from(AuthSession)) == 0
        assert session.scalar(select(func.count()).select_from(AuditLog)) == 0


@pytest.mark.parametrize("failure", [False, True])
def test_request_session_always_closes_and_rolls_back_errors(
    login_app: FastAPI, auth_engine: Engine, failure: bool
) -> None:
    from app.core.database import get_db_session

    login_app.state.session_factory.configure(close_resets_only=False)
    request = Request({"type": "http", "app": login_app})
    dependency = get_db_session(request)
    session = next(dependency)
    rollbacks = []
    event.listen(session, "after_rollback", lambda _: rollbacks.append(True))
    account = session.scalars(select(User)).one()
    account.is_active = False
    session.flush()
    if failure:
        with pytest.raises(RuntimeError, match="request failed"):
            dependency.throw(RuntimeError("request failed"))
        assert rollbacks == [True]
    else:
        with pytest.raises(StopIteration):
            next(dependency)
    with pytest.raises(InvalidRequestError):
        session.scalars(select(User)).all()
    with Session(auth_engine) as observer:
        assert observer.scalars(select(User)).one().is_active is True
