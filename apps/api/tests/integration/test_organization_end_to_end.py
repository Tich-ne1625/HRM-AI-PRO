from io import StringIO

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cli.create_admin import main
from app.core.config import Settings
from app.main import create_app
from app.models import AuditLog


def test_real_accounts_organization_linkage_scopes_and_transfer(auth_engine, monkeypatch):
    monkeypatch.setattr("sys.stdin", StringIO("bootstrap-password\nbootstrap-password\n"))
    assert main(["--email", "admin@example.com", "--password-stdin"]) == 0
    settings = Settings(database_url=auth_engine.url.render_as_string(hide_password=False))
    app = create_app(settings)

    def login(email, password="initial-password"):
        client = TestClient(app, headers={"Origin": settings.web_origin})
        result = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert result.status_code == 200
        client.headers["X-CSRF-Token"] = client.cookies["insighthr_csrf"]
        return client, result.json()

    try:
        admin, _ = login("admin@example.com", "bootstrap-password")
        accounts = {}
        for name, role in (("hr", "HR"), ("manager", "MANAGER"), ("employee", "EMPLOYEE")):
            created = admin.post(
                "/api/v1/users",
                json={
                    "email": f"{name}@example.com",
                    "password": "initial-password",
                    "role": role,
                },
            )
            assert created.status_code == 201
            accounts[name] = created.json()["id"]
        hr, _ = login("hr@example.com")
        manager, _ = login("manager@example.com")
        employee, initial_identity = login("employee@example.com")
        assert initial_identity["employee_id"] is None
        assert employee.get("/api/v1/employees").json()["items"] == []
        department = hr.post("/api/v1/departments", json={"code": "ENG", "name": "Engineering"})
        position = hr.post("/api/v1/positions", json={"code": "DEV", "title": "Developer"})
        assert department.status_code == position.status_code == 201
        base = {"department_id": department.json()["id"], "position_id": position.json()["id"]}
        leader = hr.post(
            "/api/v1/employees",
            json={
                **base,
                "employee_code": "MGR-01",
                "display_name": "Manager",
                "user_id": accounts["manager"],
            },
        )
        assert leader.status_code == 201
        report = hr.post(
            "/api/v1/employees",
            json={
                **base,
                "employee_code": "EMP-01",
                "display_name": "Employee",
                "user_id": accounts["employee"],
                "manager_id": leader.json()["id"],
            },
        )
        assert report.status_code == 201
        unrelated = hr.post(
            "/api/v1/employees",
            json={**base, "employee_code": "EMP-02", "display_name": "Unrelated"},
        )
        assert unrelated.status_code == 201
        report_id = report.json()["id"]
        assert employee.get("/api/v1/auth/me").json()["employee_id"] == report_id
        assert employee.get("/api/v1/employees").json()["total"] == 1
        assert manager.get("/api/v1/employees").json()["total"] == 2
        assert manager.get(f"/api/v1/employees/{unrelated.json()['id']}").status_code == 404
        assert admin.get("/api/v1/employees").status_code == 403
        assert hr.get("/api/v1/users").status_code == 403
        _, refreshed_identity = login("employee@example.com")
        assert refreshed_identity["employee_id"] == report_id
        assert manager.post("/api/v1/auth/refresh").status_code == 204
        assert manager.get("/api/v1/auth/me").json()["employee_id"] == leader.json()["id"]
        assert (
            hr.patch(f"/api/v1/employees/{report_id}", json={"manager_id": None}).status_code == 200
        )
        assert manager.get(f"/api/v1/employees/{report_id}").status_code == 404
        assert hr.patch(f"/api/v1/employees/{report_id}", json={"user_id": None}).status_code == 200
        assert employee.get("/api/v1/auth/me").json()["employee_id"] is None
        assert employee.get("/api/v1/employees").json()["total"] == 0
        with Session(auth_engine) as session:
            audits = session.scalars(select(AuditLog)).all()
            assert {
                "department.created",
                "position.created",
                "employee.created",
                "employee.updated",
            } <= {audit.action for audit in audits}
            assert all("password" not in str(audit.metadata_) for audit in audits)
    finally:
        app.state.engine.dispose()
