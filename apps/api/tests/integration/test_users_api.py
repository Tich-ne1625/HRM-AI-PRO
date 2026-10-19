from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import AuditLog, AuthSession, User, UserRole
from app.modules.audit.service import AuditWriter


@pytest.fixture
def admin_client(mutation_app, login_cookies, auth_engine):
    cookies = login_cookies()
    with Session(auth_engine) as session, session.begin():
        session.scalars(select(User)).one().role = UserRole.ADMIN
    return TestClient(
        mutation_app,
        raise_server_exceptions=False,
        cookies=cookies,
        headers={
            "Origin": "http://testserver",
            "X-CSRF-Token": cookies["insighthr_csrf"],
        },
    )


def create_user(client, **overrides):
    return client.post(
        "/api/v1/users",
        json={
            "email": " New.User@EXAMPLE.com ",
            "password": "initial-password",
            "role": "HR",
            **overrides,
        },
    )


def test_admin_create_list_update_and_transactional_audits(admin_client, auth_engine):
    response = create_user(admin_client)
    assert response.status_code == 201
    user = response.json()
    assert set(user) == {"id", "email", "role", "is_active", "employee_id"}
    assert user["email"] == "new.user@example.com"
    assert user["employee_id"] is None
    listing = admin_client.get("/api/v1/users", params={"role": "HR", "page_size": 1})
    assert listing.json() == {"items": [user], "total": 1, "page": 1, "page_size": 1}
    updated = admin_client.patch(
        f"/api/v1/users/{user['id']}",
        json={
            "role": "MANAGER",
            "is_active": False,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "MANAGER" and not updated.json()["is_active"]
    with Session(auth_engine) as session:
        stored = session.get(User, user["id"])
        assert stored.password_hash.startswith("$argon2id$")
        assert "initial-password" not in stored.password_hash
        audits = session.scalars(select(AuditLog)).all()
        assert {"user.created", "user.role_changed", "user.status_changed"} <= {
            audit.action for audit in audits
        }
        assert all("password" not in str(audit.metadata_) for audit in audits)
    assert listing.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("role", ["HR", "MANAGER", "EMPLOYEE"])
def test_nonadmins_denied_all_user_routes(mutation_app, login_cookies, auth_engine, role):
    cookies = login_cookies()
    with Session(auth_engine) as session, session.begin():
        session.scalars(select(User)).one().role = UserRole(role)
    client = TestClient(mutation_app, cookies=cookies)
    for method, path in [
        ("GET", "/api/v1/users"),
        ("POST", "/api/v1/users"),
        ("PATCH", f"/api/v1/users/{uuid4()}"),
    ]:
        response = client.request(method, path, json={} if method != "GET" else None)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.parametrize(
    "changes",
    [
        {"email": "invalid"},
        {"password": "x" * 11},
        {"password": "x" * 129},
        {"role": "ROOT"},
    ],
)
def test_create_validation_is_sanitized(admin_client, changes):
    response = create_user(admin_client, **changes)
    assert response.status_code == 422
    assert "initial-password" not in response.text


def test_duplicate_email_and_unknown_user_have_stable_errors(admin_client):
    assert create_user(admin_client).status_code == 201
    duplicate = create_user(admin_client, email="NEW.USER@example.com")
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "email_already_exists"
    assert admin_client.patch(f"/api/v1/users/{uuid4()}", json={"role": "HR"}).status_code == 404


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page_size": 101},
        {"sort": "password_hash"},
        {"role": "ROOT"},
    ],
)
def test_list_validation(admin_client, params):
    assert admin_client.get("/api/v1/users", params=params).status_code == 422


@pytest.mark.parametrize("body", [{}, {"role": None}, {"is_active": None}, {"unknown": True}])
def test_update_requires_explicit_nonnull_supported_change(admin_client, body):
    assert admin_client.patch(f"/api/v1/users/{uuid4()}", json=body).status_code == 422


@pytest.mark.parametrize("body", [{"role": "HR"}, {"is_active": False}])
def test_last_admin_is_protected(admin_client, body):
    user_id = admin_client.get("/api/v1/auth/me").json()["id"]
    response = admin_client.patch(f"/api/v1/users/{user_id}", json=body)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "last_active_admin"


def test_deactivation_revokes_all_families_and_demotion_is_immediate(
    admin_client,
    mutation_app,
    auth_engine,
):
    target = create_user(admin_client, role="ADMIN").json()
    logins = [
        TestClient(mutation_app).post(
            "/api/v1/auth/login",
            headers={
                "Origin": "http://testserver",
            },
            json={"email": target["email"], "password": "initial-password"},
        )
        for _ in range(2)
    ]
    client = TestClient(mutation_app, cookies=dict(logins[0].cookies))
    assert client.get("/api/v1/users").status_code == 200
    assert (
        admin_client.patch(f"/api/v1/users/{target['id']}", json={"role": "HR"}).status_code == 200
    )
    assert client.get("/api/v1/users").status_code == 403
    assert (
        admin_client.patch(f"/api/v1/users/{target['id']}", json={"is_active": False}).status_code
        == 200
    )
    assert client.get("/api/v1/auth/me").status_code == 401
    with Session(auth_engine) as session:
        rows = session.scalars(select(AuthSession).where(AuthSession.user_id == target["id"])).all()
        assert len(rows) == 2 and all(row.revoked_at <= datetime.now(UTC) for row in rows)


@pytest.mark.parametrize("operation", ["create", "update"])
def test_user_audit_failure_rolls_back_every_change(
    admin_client, auth_engine, monkeypatch, operation
):
    target = create_user(admin_client).json()

    def fail(*args, **kwargs):
        raise SQLAlchemyError("private-db-detail")

    monkeypatch.setattr(AuditWriter, "record", fail)
    if operation == "create":
        response = create_user(admin_client, email="rollback@example.com")
    else:
        response = admin_client.patch(f"/api/v1/users/{target['id']}", json={"is_active": False})
    assert response.status_code == 500
    assert "private-db-detail" not in response.text
    with Session(auth_engine) as session:
        assert len(session.scalars(select(User)).all()) == 2
        assert session.get(User, target["id"]).is_active


@pytest.mark.parametrize("failure", ["origin", "csrf"])
def test_user_mutations_reject_missing_origin_or_csrf_without_changes(admin_client, failure):
    admin_client.headers.pop("Origin" if failure == "origin" else "X-CSRF-Token")
    assert create_user(admin_client).status_code == 403
    assert admin_client.get("/api/v1/users").json()["total"] == 1
