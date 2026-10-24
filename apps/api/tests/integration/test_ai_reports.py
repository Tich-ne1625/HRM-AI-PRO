from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.models import AuditLog, Employee
from app.modules.ai.models import AIAnalysis

from .test_ai_workflows import ai_world as ai_world


def generate(world, path, body, audience="PUBLIC"):
    response = world.client().post(
        path, json={**body, "audience": audience, "client_request_id": str(uuid4())}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_saved_reports_scope_pagination_and_no_private_projection(ai_world):
    world, provider, report, path, body, _ = ai_world
    public = generate(world, path, body)
    private = generate(world, path, body, "HR_PRIVATE")
    with Session(world.engine) as session, session.begin():
        original = session.get(AIAnalysis, UUID(public["id"]))
        values = {
            c.name: getattr(original, c.name)
            for c in AIAnalysis.__table__.columns
            if c.name != "id"
        }
        for version in range(2, 23):
            session.add(
                AIAnalysis(
                    **{**values, "generation_version": version, "client_request_id": uuid4()}
                )
            )
    with Session(world.engine) as session:
        before = session.scalar(select(func.count()).select_from(AuditLog))
    for role in ("hr", "manager", "alice"):
        response = world.client(role).get("/api/v1/ai-reports?page_size=20")
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        data = response.json()
        assert data["total"] == 22 and len(data["items"]) == 20
        second = world.client(role).get("/api/v1/ai-reports?page=2").json()
        assert len(second["items"]) == 2
        ids = [row["id"] for row in data["items"] + second["items"]]
        assert len(set(ids)) == 22 and ids == sorted(ids, reverse=True)
        assert private["id"] not in response.text
        for forbidden in (
            "Private sentinel",
            "Advice",
            "output",
            "input_hash",
            "requested_by",
            "client_request_id",
            "evidence_hash",
        ):
            assert forbidden not in response.text
        assert all(row["matches_current_calculation"] for row in data["items"])
    private_list = world.client().get("/api/v1/ai-reports?audience=HR_PRIVATE").json()
    assert private_list["total"] == 1 and private_list["items"][0]["id"] == private["id"]
    for role in ("other", "unlinked", "bob"):
        assert world.client(role).get("/api/v1/ai-reports").json()["total"] == 0
        assert (
            world.client(role).get(f"/api/v1/ai-reports?cycle_id={report['cycle_id']}").status_code
            == 404
        )
    for role in ("manager", "alice", "other", "unlinked"):
        assert world.client(role).get("/api/v1/ai-reports?audience=HR_PRIVATE").status_code == 403
    assert TestClient(world.app).get("/api/v1/ai-reports").status_code == 401
    assert world.client("admin").get("/api/v1/ai-reports").status_code == 403
    assert world.client().get(f"/api/v1/ai-reports?cycle_id={uuid4()}").status_code == 404
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(AuditLog)) == before
    assert len(provider.calls) == 2


@pytest.mark.parametrize(
    "query", ["page=0", "page=-1", "page_size=101", "page_size=0", "audience=OTHER"]
)
def test_saved_reports_reject_invalid_filters(world, query):
    assert world.client().get("/api/v1/ai-reports?" + query).status_code == 422


def test_saved_report_history_stale_engine_and_live_scope(ai_world):
    world, provider, report, path, body, item = ai_world
    generated = generate(world, path, body)
    changed = world.client().patch(
        f"/api/v1/employee-kpis/{item['id']}",
        json={"expected_evidence_version": report["evidence_version"], "actual": "50.0000"},
    )
    assert changed.status_code == 200, changed.text
    data = world.client("alice").get("/api/v1/ai-reports").json()
    assert data["total"] == 1 and not data["items"][0]["matches_current_calculation"]
    assert data["items"][0]["id"] == generated["id"]
    # A transfer changes current read scope without deleting the historical advice.
    with Session(world.engine) as session, session.begin():
        employee = session.get(Employee, UUID(world.employees["alice"]))
        employee.manager_id = UUID(world.employees["other"])
    assert world.client("manager").get("/api/v1/ai-reports").json()["total"] == 0
    assert world.client("other").get("/api/v1/ai-reports").json()["total"] == 1
    assert world.client("manager").get("/api/v1/dashboard").json()["recent_activities"] == []
    assert len(world.client("other").get("/api/v1/dashboard").json()["recent_activities"]) == 1
    assert len(provider.calls) == 1


def test_saved_report_count_and_rows_share_one_snapshot(ai_world):
    world, _, _, path, body, _ = ai_world
    generated = generate(world, path, body)
    inserted = False

    def concurrent_insert(conn, cursor, statement, parameters, context, executemany):
        nonlocal inserted
        if inserted or "count(" not in statement.lower() or "ai_analyses" not in statement:
            return
        inserted = True
        with Session(world.engine) as session, session.begin():
            original = session.get(AIAnalysis, UUID(generated["id"]))
            values = {
                c.name: getattr(original, c.name)
                for c in AIAnalysis.__table__.columns
                if c.name != "id"
            }
            session.add(
                AIAnalysis(**{**values, "generation_version": 2, "client_request_id": uuid4()})
            )

    event.listen(world.engine, "after_cursor_execute", concurrent_insert)
    try:
        first = world.client().get("/api/v1/ai-reports")
    finally:
        event.remove(world.engine, "after_cursor_execute", concurrent_insert)
    assert first.status_code == 200, first.text
    assert inserted and first.json()["total"] == len(first.json()["items"]) == 1
    second = world.client().get("/api/v1/ai-reports").json()
    assert second["total"] == len(second["items"]) == 2


def test_dashboard_activity_allowlist_scope_and_read_only(ai_world):
    world, provider, report, _, _, _ = ai_world
    with Session(world.engine) as session, session.begin():
        for action, entity_type, entity_id in (
            ("performance.calculated", "performance_review", report["review_id"]),
            ("performance.calculated", "performance_review", "invalid-uuid"),
            ("performance.calculated", "ai_analysis", report["review_id"]),
            ("ai_analysis.completed", "performance_review", report["review_id"]),
            ("auth.login_failed", "user", world.users["hr"]),
            ("user.created", "user", world.users["alice"]),
        ):
            session.add(
                AuditLog(
                    action=action,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    request_id="PRIVATE_REQUEST",
                    metadata_={"secret": "PRIVATE_METADATA"},
                )
            )
    with Session(world.engine) as session:
        before = session.scalar(select(func.count()).select_from(AuditLog))
    for role in ("hr", "manager", "alice"):
        response = world.client(role).get("/api/v1/dashboard")
        assert response.status_code == 200, response.text
        activities = response.json()["recent_activities"]
        assert len(activities) == 2
        assert all(a["employee_id"] == world.employees["alice"] for a in activities)
        assert all(a["cycle_id"] == report["cycle_id"] for a in activities)
        for forbidden in (
            "PRIVATE",
            "metadata",
            "actor_id",
            "request_id",
            "ai_analysis",
            "auth.login",
        ):
            assert forbidden not in response.text
    assert world.client("other").get("/api/v1/dashboard").json()["recent_activities"] == []
    admin = world.client("admin").get("/api/v1/dashboard").json()["recent_activities"]
    assert len(admin) == 1 and admin[0]["action"] == "user.created"
    assert admin[0]["employee_id"] is None and admin[0]["display_name"] is None
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(AuditLog)) == before
    assert not provider.calls
