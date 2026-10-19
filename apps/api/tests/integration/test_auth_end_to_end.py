from io import StringIO

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cli.create_admin import main
from app.core.config import Settings
from app.main import create_app
from app.models import AuditLog


def test_bootstrap_to_user_management_rotation_and_logout(auth_engine, monkeypatch):
    monkeypatch.setattr("sys.stdin", StringIO("bootstrap-password\nbootstrap-password\n"))
    assert main(["--email", "admin@example.com", "--password-stdin"]) == 0
    settings = Settings(database_url=auth_engine.url.render_as_string(hide_password=False))
    app = create_app(settings)
    try:
        with TestClient(app) as admin:
            assert (
                admin.post(
                    "/api/v1/auth/login",
                    headers={"Origin": settings.web_origin},
                    json={
                        "email": "admin@example.com",
                        "password": "bootstrap-password",
                    },
                ).status_code
                == 200
            )
            admin.headers.update(
                {"Origin": settings.web_origin, "X-CSRF-Token": admin.cookies["insighthr_csrf"]}
            )
            assert admin.get("/api/v1/auth/me").json()["role"] == "ADMIN"
            created = admin.post(
                "/api/v1/users",
                json={
                    "email": "hr@example.com",
                    "password": "initial-password",
                    "role": "HR",
                },
            )
            assert created.status_code == 201
            assert created.json()["employee_id"] is None
            current, other = TestClient(app), TestClient(app)
            for client in (current, other):
                assert (
                    client.post(
                        "/api/v1/auth/login",
                        headers={"Origin": settings.web_origin},
                        json={"email": "hr@example.com", "password": "initial-password"},
                    ).status_code
                    == 200
                )
                client.headers.update(
                    {
                        "Origin": settings.web_origin,
                        "X-CSRF-Token": client.cookies["insighthr_csrf"],
                    }
                )
            assert current.get("/api/v1/users").status_code == 403
            assert (
                current.post(
                    "/api/v1/auth/change-password",
                    json={
                        "old_password": "initial-password",
                        "new_password": "replacement-password",
                    },
                ).status_code
                == 204
            )
            assert other.get("/api/v1/auth/me").status_code == 401
            assert current.post("/api/v1/auth/refresh").status_code == 204
            stale = dict(current.cookies)
            assert current.post("/api/v1/auth/logout").status_code == 204
            assert current.get("/api/v1/auth/me").status_code == 401
            old_client = TestClient(app, cookies=stale, headers=current.headers)
            assert old_client.get("/api/v1/auth/me").status_code == 401
            assert old_client.post("/api/v1/auth/refresh").status_code == 401
        with Session(auth_engine) as session:
            audits = session.scalars(select(AuditLog)).all()
            assert {
                "user.bootstrap_created",
                "user.created",
                "auth.login_succeeded",
                "user.password_changed",
                "auth.refresh_succeeded",
                "auth.logout",
            } <= {audit.action for audit in audits}
            assert all("password" not in str(audit.metadata_) for audit in audits)
    finally:
        app.state.engine.dispose()
