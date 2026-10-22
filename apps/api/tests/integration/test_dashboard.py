from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.cli.seed_demo import email, seed_demo
from app.models import (
    AuditLog,
    CycleParticipant,
    CycleStatus,
    Employee,
    PerformanceReview,
    ReviewCycle,
    User,
)

PASSWORD = "fictional-dashboard-test-password"


def test_dashboard_demo_metrics_scope_and_no_side_effects(world, monkeypatch):
    monkeypatch.setattr(
        "app.modules.ai.provider.GeminiProvider.generate",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("No provider calls")),
    )
    seed_demo(world.engine, PASSWORD)
    with Session(world.engine) as session:
        cycle = session.scalar(select(ReviewCycle).where(ReviewCycle.status == CycleStatus.ACTIVE))
        cycle_id = str(cycle.id)
        draft_id = str(
            session.scalar(select(ReviewCycle.id).where(ReviewCycle.status == CycleStatus.DRAFT))
        )
        audits_before = session.scalar(select(func.count()).select_from(AuditLog))
    clients = {}
    for name in ("hr", "manager", "sales.manager", "an", "binh", "admin"):
        client = TestClient(world.app, headers={"Origin": "http://testserver"})
        response = client.post(
            "/api/v1/auth/login", json={"email": email(name), "password": PASSWORD}
        )
        assert response.status_code == 200, response.text
        clients[name] = client
    with Session(world.engine) as session:
        audits_after_login = session.scalar(select(func.count()).select_from(AuditLog))
    assert audits_after_login >= audits_before
    statements = []

    def track(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(world.engine, "before_cursor_execute", track)
    try:
        response = clients["hr"].get("/api/v1/dashboard")
    finally:
        event.remove(world.engine, "before_cursor_execute", track)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    hr = response.json()
    assert hr["selected_cycle"]["id"] == cycle_id
    assert (
        hr["participants"],
        hr["current"],
        hr["stale"],
        hr["not_calculated"],
        hr["finalized"],
    ) == (5, 1, 1, 2, 1)
    assert (hr["sample_size"], hr["average"], hr["awaiting_completion"]) == (2, "84.90", 4)
    assert (hr["kpis_entered"], hr["kpis_assigned"], hr["kpi_entry_percent"]) == (9, 10, "90.00")
    assert sum(hr["score_bands"].values()) == 2
    assert len(hr["departments"]) == 2
    assert len(statements) <= 12  # authentication + fixed aggregates, independent of employee count
    manager = clients["manager"].get("/api/v1/dashboard").json()
    assert (manager["participants"], manager["sample_size"], manager["average"]) == (3, 1, "82.80")
    sales = clients["sales.manager"].get("/api/v1/dashboard").json()
    assert (sales["participants"], sales["stale"], sales["average"]) == (2, 1, "87.00")
    employee = clients["binh"].get("/api/v1/dashboard").json()
    assert (employee["participants"], employee["average"], employee["sample_size"]) == (1, None, 0)
    assert employee["pending_feedback"] >= 1
    admin = clients["admin"].get("/api/v1/dashboard").json()
    assert admin["active_accounts"] >= 10
    assert "participants" not in admin and "active_employees" not in admin
    for name in ("manager", "an", "admin"):
        assert clients[name].get(f"/api/v1/dashboard?cycle_id={draft_id}").status_code == 404
        assert clients[name].get(f"/api/v1/dashboard?cycle_id={uuid4()}").status_code == 404
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(AuditLog)) == audits_after_login


def test_dashboard_empty_unlinked_and_anonymous(world):
    assert TestClient(world.app).get("/api/v1/dashboard").status_code == 401
    for name in ("unlinked", "alice"):
        response = world.client(name).get("/api/v1/dashboard")
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["selected_cycle"] is None and result["cycles"] == []
        assert result["average"] is None and result["kpi_entry_percent"] is None
        assert result["participants"] == 0
    assert world.client("alice").get("/api/v1/dashboard?cycle_id=invalid").status_code == 422


def test_dashboard_uses_department_snapshot_but_live_manager_scope(world):
    seed_demo(world.engine, PASSWORD)
    with Session(world.engine) as session:
        hr_id = session.scalar(select(User.id).where(User.email == email("hr")))
        cycle_id = session.scalar(
            select(ReviewCycle.id).where(ReviewCycle.status == CycleStatus.ACTIVE)
        )
        an_id = session.scalar(select(Employee.id).where(Employee.employee_code == "DEMO-AN"))
    from app.modules.dashboard.service import DashboardService

    def read(user_id):
        with Session(world.engine) as session:
            user = session.get(User, user_id)
            session.expunge(user)
        with Session(world.engine) as session:
            return DashboardService(session).read(user, cycle_id)

    before = read(hr_id)
    with Session(world.engine) as session, session.begin():
        an = session.get(Employee, an_id)
        sales = session.scalar(
            select(Employee).where(Employee.employee_code == "DEMO-SALES-MANAGER")
        )
        an.department_id, an.manager_id = sales.department_id, sales.id
        manager_id = session.scalar(select(User.id).where(User.email == email("manager")))
    after = read(hr_id)
    assert after.departments == before.departments
    manager = read(manager_id)
    assert manager.participants == 2 and manager.average is None
    # An obsolete engine must be excluded even when its evidence version still matches.
    with Session(world.engine) as session, session.begin():
        participant = session.scalar(
            select(PerformanceReview)
            .join(CycleParticipant)
            .where(CycleParticipant.employee_id == an_id, CycleParticipant.cycle_id == cycle_id)
        )
        participant.engine_version = "999"
    stale = read(hr_id)
    assert stale.sample_size == 1 and stale.average == Decimal("87.00")
