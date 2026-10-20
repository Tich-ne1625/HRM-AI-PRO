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
        for name, role in (
            ("hr", "HR"),
            ("manager", "MANAGER"),
            ("employee", "EMPLOYEE"),
            ("peer", "EMPLOYEE"),
            ("subordinate", "EMPLOYEE"),
        ):
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
        for name in ("peer", "subordinate"):
            linked = hr.post(
                "/api/v1/employees",
                json={
                    **base,
                    "employee_code": "EMP-" + name.upper(),
                    "display_name": name.title(),
                    "user_id": accounts[name],
                    "manager_id": report_id if name == "subordinate" else None,
                },
            )
            assert linked.status_code == 201
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
        # Continue the same real-account workflow through Phase 4; no forged tokens.
        configured = admin.patch(
            "/api/v1/settings/scoring",
            json={
                "expected_version": 1,
                "policy": {"kpi_cap": "120.00"},
            },
        )
        assert configured.status_code == 200
        cycle = hr.post(
            "/api/v1/review-cycles",
            json={
                "name": "Q4",
                "start_date": "2026-10-01",
                "end_date": "2026-12-31",
            },
        )
        assert cycle.status_code == 201
        cycle_path = "/api/v1/review-cycles/" + cycle.json()["id"]
        assert (
            hr.post(
                cycle_path + "/participants",
                json={
                    "expected_version": 1,
                    "employee_ids": [report_id],
                },
            ).status_code
            == 200
        )
        activated = hr.post(cycle_path + "/activate", json={"expected_version": 2})
        assert activated.status_code == 200
        assert activated.json()["policy"]["kpi_cap"] == "120.00"
        definition = hr.post(
            "/api/v1/kpis",
            json={
                "code": "SALES",
                "name": "Sales",
                "unit": "VND",
                "direction": "HIGHER_IS_BETTER",
            },
        )
        assert definition.status_code == 201
        kpis_path = f"/api/v1/employees/{report_id}/kpis?cycle_id={cycle.json()['id']}"
        assigned = manager.put(
            kpis_path,
            json={
                "expected_evidence_version": 2,
                "items": [
                    {
                        "definition_id": definition.json()["id"],
                        "target": "100.0000",
                        "weight": "100.00",
                    },
                ],
            },
        )
        assert assigned.status_code == 200
        actual = manager.patch(
            "/api/v1/employee-kpis/" + assigned.json()["items"][0]["id"],
            json={
                "expected_evidence_version": 3,
                "actual": "75.0000",
            },
        )
        assert actual.status_code == 200
        assert employee.get(kpis_path).json()["items"][0]["actual"] == "75.0000"
        assert admin.get(kpis_path).status_code == 403
        # Phase 5 continues the same real authenticated accounts and ACTIVE cycle.
        peer, _ = login("peer@example.com")
        subordinate, _ = login("subordinate@example.com")
        participant = actual.json()["participant"]
        assignments = []
        for client, account_id, relationship in (
            (employee, accounts["employee"], "SELF"),
            (manager, accounts["manager"], "MANAGER"),
            (peer, accounts["peer"], "PEER"),
            (subordinate, accounts["subordinate"], "SUBORDINATE"),
        ):
            created = hr.post(
                "/api/v1/feedback-assignments",
                json={
                    "participant_id": participant["id"],
                    "reviewer_id": account_id,
                    "relationship": relationship,
                    "required": True,
                    "expected_evidence_version": participant["evidence_version"],
                },
            )
            assert created.status_code == 201, created.text
            row = created.json()
            payload = {
                "assignment_id": row["id"],
                "expected_assignment_version": row["version"],
                "expected_evidence_version": row["evidence_version"],
                "rating": 4,
                "comment": "Real account private comment",
            }
            assert hr.post("/api/v1/feedback", json=payload).status_code == 404
            sent = client.post("/api/v1/feedback", json=payload)
            assert sent.status_code == 201, sent.text
            assert client.post("/api/v1/feedback", json=payload).status_code == 409
            participant["evidence_version"] = sent.json()["evidence_version"]
            assignments.append((client, row["id"]))
        summary_path = f"/api/v1/employees/{report_id}/feedback?cycle_id={cycle.json()['id']}"
        summary = manager.get(summary_path).json()
        assert summary["ready"] and summary["count"] == 4 and summary["mean"] == "4.00"
        assert all(
            g["suppressed"]
            for g in summary["groups"]
            if g["relationship"] in ("PEER", "SUBORDINATE")
        )
        assert summary["own_submission"]["comment"] == "Real account private comment"
        assert "Real account private comment" not in str(
            {key: value for key, value in summary.items() if key != "own_submission"}
        )
        assert peer.get(summary_path).status_code == 404
        assert admin.get(summary_path).status_code == 403
        assert hr.get("/api/v1/feedback-assignments?view=administration").json()["total"] == 4
        assert (
            hr.patch(f"/api/v1/employees/{report_id}", json={"manager_id": None}).status_code == 200
        )
        assert manager.get(f"/api/v1/employees/{report_id}").status_code == 404
        assert manager.get(kpis_path).status_code == 404
        assert manager.get(summary_path).status_code == 404
        assert manager.get(f"/api/v1/feedback-assignments/{assignments[1][1]}").status_code == 200
        assert hr.patch(f"/api/v1/employees/{report_id}", json={"user_id": None}).status_code == 200
        assert employee.get("/api/v1/auth/me").json()["employee_id"] is None
        assert employee.get("/api/v1/employees").json()["total"] == 0
        assert employee.get(kpis_path).status_code == 404
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
