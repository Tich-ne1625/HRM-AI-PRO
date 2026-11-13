from uuid import UUID, uuid4

import psycopg
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Employee, Notification, User, UserRole
from app.modules.audit.service import AuditWriter

from .test_employee_kpis import replace_body
from .test_feedback_workflows import create_assignment, feedback_world, submit
from .test_performance import calculate, ready_world


def inbox(world, role="alice", **params):
    response = world.client(role).get("/api/v1/notifications", params=params)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def test_assignment_notice_is_durable_owned_and_read_is_idempotent(world):
    _, participant = feedback_world(world)
    created = create_assignment(world, participant).json()
    data = inbox(world)
    notice = next(row for row in data["items"] if row["href"] == f"/feedback/{created['id']}")
    assert notice["read_at"] is None
    assert "comment" not in str(data) and "reviewer_id" not in str(data)
    assert world.client("bob").post(f"/api/v1/notifications/{notice['id']}/read").status_code == 404
    before = data["unread_count"]
    path = f"/api/v1/notifications/{notice['id']}/read"
    assert world.client("alice").post(path).status_code == 204
    assert inbox(world)["unread_count"] == before - 1
    first_read = next(row["read_at"] for row in inbox(world)["items"] if row["id"] == notice["id"])
    assert world.client("alice").post(path).status_code == 204
    assert (
        next(row["read_at"] for row in inbox(world)["items"] if row["id"] == notice["id"])
        == first_read
    )
    assert world.client("alice").post("/api/v1/notifications/read-all").status_code == 204
    assert inbox(world, unread=True)["items"] == []
    assert inbox(world, "manager")["unread_count"] > 0


def test_submission_notifies_hr_and_manager_without_leaking_comment_or_reviewer(world):
    _, participant = feedback_world(world)
    row = create_assignment(world, participant).json()
    before_hr = inbox(world, "hr")["unread_count"]
    before_manager = inbox(world, "manager")["unread_count"]
    assert submit(world, row, comment="PRIVATE RAW SENTINEL").status_code == 201
    hr = inbox(world, "hr")
    assert hr["unread_count"] == before_hr + 1
    assert inbox(world, "manager")["unread_count"] == before_manager + 1
    assert "PRIVATE RAW SENTINEL" not in str(hr)
    with Session(world.engine) as session:
        count = session.scalar(select(func.count()).select_from(Notification))
    assert submit(world, row).status_code == 409
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(Notification)) == count


def test_rollback_has_no_durable_notice_and_no_postgresql_signal(world, monkeypatch):
    from app.modules.notifications import delivery

    _, participant = feedback_world(world)
    with Session(world.engine) as session:
        before = session.scalar(select(func.count()).select_from(Notification))
    original = delivery.deliver

    def fail(session, event):
        original(session, event)
        raise RuntimeError("Rollback fixture")

    monkeypatch.setattr(delivery, "deliver", fail)
    dsn = world.engine.url.render_as_string(hide_password=False).replace(
        "postgresql+psycopg://", "postgresql://"
    )
    with psycopg.connect(dsn, autocommit=True) as listener:
        listener.execute("LISTEN insighthr_notifications")
        assert create_assignment(world, participant).status_code == 500
        assert list(listener.notifies(timeout=0.2, stop_after=1)) == []
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(Notification)) == before


def test_committed_read_state_signals_other_tabs_with_only_recipient_id(world):
    feedback_world(world)
    notice = inbox(world)["items"][0]
    dsn = world.engine.url.render_as_string(hide_password=False).replace(
        "postgresql+psycopg://", "postgresql://"
    )
    with psycopg.connect(dsn, autocommit=True) as listener:
        listener.execute("LISTEN insighthr_notifications")
        assert (
            world.client("alice").post(f"/api/v1/notifications/{notice['id']}/read").status_code
            == 204
        )
        events = list(listener.notifies(timeout=1, stop_after=1))
        assert len(events) == 1 and events[0].payload == world.users["alice"]


@pytest.mark.parametrize("change", ["role", "manager"])
def test_scope_change_hides_old_notices_counts_and_read_access(world, change):
    feedback_world(world)
    data = inbox(world, "manager")
    assert data["total"] > 0
    with Session(world.engine) as session, session.begin():
        if change == "role":
            session.get(User, UUID(world.users["manager"])).role = UserRole.EMPLOYEE
        else:
            session.get(Employee, UUID(world.employees["alice"])).manager_id = UUID(
                world.employees["other"]
            )
    assert inbox(world, "manager")["total"] == 0
    assert inbox(world, "manager")["unread_count"] == 0
    assert (
        world.client("manager")
        .post(f"/api/v1/notifications/{data['items'][0]['id']}/read")
        .status_code
        == 404
    )


@pytest.mark.parametrize("protection", ["csrf", "origin"])
def test_read_state_requires_origin_and_csrf(world, protection):
    feedback_world(world)
    notice = inbox(world)["items"][0]
    client = world.client("alice")
    client.headers["X-CSRF-Token" if protection == "csrf" else "Origin"] = "invalid"
    assert client.post(f"/api/v1/notifications/{notice['id']}/read").status_code == 403
    assert inbox(world)["items"][0]["read_at"] is None


def test_hr_coordinates_while_manager_calculates_and_receives_handoff(world):
    cycle, participant, item, base = ready_world(world)
    kpis = f"/api/v1/employees/{world.employees['alice']}/kpis?cycle_id={cycle['id']}"
    assert world.client("hr").get(kpis).json()["participant"]["can_manage_kpis"] is False
    assert (
        world.client("hr")
        .put(
            kpis,
            json=replace_body(
                {"id": item["definition_id"]}, version=participant["evidence_version"]
            ),
        )
        .status_code
        == 403
    )
    assert (
        world.client("hr")
        .patch(
            f"/api/v1/employee-kpis/{item['id']}",
            json={"expected_evidence_version": participant["evidence_version"], "actual": "1"},
        )
        .status_code
        == 403
    )
    assert calculate(world, cycle, participant, base, "hr").status_code == 403
    hr_tasks = world.client("hr").get("/api/v1/notifications/tasks").json()
    assert any("Chờ quản lý tính" in row["title"] for row in hr_tasks["items"])
    result = calculate(world, cycle, participant, base)
    assert result.status_code == 201, result.text
    assert result.json()["can_finalize"] is False
    report = world.client("hr").get(base, params={"cycle_id": cycle["id"]}).json()
    assert report["can_calculate"] is False and report["can_finalize"] is True
    assert any(
        "Kiểm tra và chốt" in row["title"]
        for row in world.client("hr").get("/api/v1/notifications/tasks").json()["items"]
    )
    notices = inbox(world, "hr")
    assert any("Quản lý đã tính" in row["message"] for row in notices["items"])
    count = notices["total"]
    assert calculate(world, cycle, participant, base).status_code == 200
    assert inbox(world, "hr")["total"] == count


def test_private_advice_events_never_reach_manager_or_employee(world):
    cycle, participant, _, base = ready_world(world)
    review_id = calculate(world, cycle, participant, base).json()["review_id"]
    before_manager = inbox(world, "manager")["total"]
    before_employee = inbox(world)["total"]
    with Session(world.engine) as session, session.begin():
        session.get(User, UUID(world.users["spare"])).role = UserRole.HR
        AuditWriter().record(
            session,
            UUID(world.users["hr"]),
            "ai_analysis.succeeded",
            "ai_analysis",
            str(uuid4()),
            "private-event-test",
            {"review_id": review_id, "audience": "HR_PRIVATE"},
        )
    assert inbox(world, "manager")["total"] == before_manager
    assert inbox(world)["total"] == before_employee
    assert inbox(world, "spare")["total"] == 1


def test_tasks_are_owned_and_reading_notice_does_not_complete_task(world):
    _, participant = feedback_world(world)
    row = create_assignment(world, participant).json()
    client = world.client("alice")
    before = client.get("/api/v1/notifications/tasks").json()
    assert any(item["href"] == f"/feedback/{row['id']}" for item in before["items"])
    assert client.post("/api/v1/notifications/read-all").status_code == 204
    assert client.get("/api/v1/notifications/tasks").json() == before
    assert world.client("bob").get("/api/v1/notifications/tasks").json()["items"] == []
    assert submit(world, row).status_code == 201
    assert client.get("/api/v1/notifications/tasks").json()["items"] == []


def test_event_stream_rejects_cross_site_and_unauthenticated_requests(world):
    from fastapi.testclient import TestClient

    assert TestClient(world.app).get("/api/v1/notifications/events").status_code == 401
    assert (
        world.client("alice")
        .get("/api/v1/notifications/events", headers={"Origin": "https://outside.example"})
        .status_code
        == 403
    )
    assert (
        world.client("alice")
        .get("/api/v1/notifications/events", headers={"Sec-Fetch-Site": "cross-site"})
        .status_code
        == 403
    )
