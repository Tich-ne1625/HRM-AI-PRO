from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApiError
from app.models import AuditLog, AuthSession
from app.modules.auth.limiter import LoginLimit, reserve_login


def test_cleanup_is_bounded_and_preserves_active_buckets(auth_engine, monkeypatch):
    from app.cli import cleanup_login_limits

    now = datetime.now(UTC)
    with Session(auth_engine) as session, session.begin():
        session.add_all(
            [
                LoginLimit(
                    bucket_key=f"{i:064x}",
                    attempts=1,
                    expires_at=now + timedelta(days=1) if i == 0 else now - timedelta(days=1),
                )
                for i in range(4)
            ]
        )
    monkeypatch.setattr(cleanup_login_limits, "get_engine", lambda _: auth_engine)
    monkeypatch.setattr("sys.argv", ["cleanup", "--limit", "2"])
    assert cleanup_login_limits.main() == 0
    with Session(auth_engine) as session:
        assert session.scalar(select(func.count()).select_from(LoginLimit)) == 2
        assert session.get(LoginLimit, "0" * 64).attempts == 1


def test_limits_are_shared_and_atomic_across_sessions_and_expire(auth_engine):
    settings = Settings(_env_file=None, auth_login_max_attempts=3)
    barrier = Barrier(8)

    def attempt(_):
        barrier.wait(timeout=10)
        with Session(auth_engine) as session:
            try:
                reserve_login(session, settings, "fictional@example.com")
                return 200
            except ApiError as error:
                assert error.headers["Retry-After"]
                return error.status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        result = list(pool.map(attempt, range(8)))
    assert sorted(result) == [200] * 3 + [429] * 5
    with Session(auth_engine) as session, session.begin():
        row = session.scalars(select(LoginLimit)).one()
        assert row.attempts == 4 and len(row.bucket_key) == 64
        assert "fictional" not in row.bucket_key
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    with Session(auth_engine) as session:
        reserve_login(session, settings, "fictional@example.com")
    with Session(auth_engine) as session:
        assert session.scalars(select(LoginLimit)).one().attempts == 1


def test_throttle_precedes_password_work_and_does_not_write_audit_on_429(world, monkeypatch):
    world.app.state.settings.auth_login_max_attempts = 1
    client = TestClient(world.app, headers={"Origin": "http://testserver"})
    for email in ("missing@example.com", "hr@example.com"):
        first = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
        assert first.status_code == 401
    with Session(world.engine) as session:
        logs = session.scalar(select(func.count()).select_from(AuditLog))

    def forbidden(*a, **k):
        pytest.fail("Argon2 must not run after the limit")

    monkeypatch.setattr("app.core.security.PasswordService.verify", forbidden)
    for email in ("MISSING@EXAMPLE.COM", "HR@EXAMPLE.COM"):
        response = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
        assert response.status_code == 429 and int(response.headers["retry-after"]) >= 1
        assert response.headers["cache-control"] == "no-store"
        assert email not in response.text
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(AuditLog)) == logs
        assert session.scalar(select(func.count()).select_from(LoginLimit)) == 2


def test_limiter_database_failure_fails_closed_and_rolls_back(world, monkeypatch):
    original = Session.execute

    def fail(self, statement, *args, **kwargs):
        if "INSERT INTO auth_login_limits" in str(statement):
            raise SQLAlchemyError("SECRET_DB_ERROR")
        return original(self, statement, *args, **kwargs)

    monkeypatch.setattr(Session, "execute", fail)
    response = TestClient(
        world.app, headers={"Origin": "http://testserver"}, raise_server_exceptions=False
    ).post("/api/v1/auth/login", json={"email": "missing@example.com", "password": "wrong"})
    assert response.status_code == 503 and "SECRET" not in response.text
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(LoginLimit)) == 0
        # Fixture families stay untouched.
        assert session.scalar(select(func.count()).select_from(AuthSession)) == len(world.users)
        assert session.scalar(text("SELECT 1")) == 1
