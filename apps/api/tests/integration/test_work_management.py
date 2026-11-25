from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import Base
from app.modules.audit.service import AuditWriter
from app.modules.notifications.models import Notification
from app.modules.work_management.models import EvidenceSubmission, WorkEvent, WorkGoal, WorkPlan

BASE = "/api/v1/work-management"


def ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def command(**values):
    return {"client_request_id": str(uuid4()), "expected_version": 1, **values}


@pytest.fixture
def flow(world):
    hr, manager, owner = world.client(), world.client("manager"), world.client("alice")
    today = datetime.now(UTC).date()
    start, end = today - timedelta(days=1), today + timedelta(days=30)
    schedule = {
        "timezone": "Asia/Ho_Chi_Minh",
        "acknowledgement_due_at": f"{start - timedelta(days=1)}T00:00:00Z",
        "input_cutoff_at": f"{end + timedelta(days=1)}T00:00:00Z",
        "verification_due_at": f"{end + timedelta(days=2)}T00:00:00Z",
        "response_due_at": f"{end + timedelta(days=3)}T00:00:00Z",
    }
    cycle = ok(
        hr.post(
            "/api/v1/review-cycles",
            json={
                "name": "Continuous test",
                "start_date": str(start),
                "end_date": str(end),
                "workflow_mode": "CONTINUOUS",
                "workflow_schedule": schedule,
            },
        ),
        201,
    )
    ok(
        hr.post(
            f"/api/v1/review-cycles/{cycle['id']}/participants",
            json={
                "expected_version": 1,
                "employee_ids": [world.employees["alice"]],
            },
        )
    )
    participant = ok(manager.get(f"{BASE}/participants"))["items"][0]["participant_id"]
    definition = ok(
        hr.post(
            "/api/v1/kpis",
            json={
                "code": "CASE",
                "name": "Verified cases",
                "description": "Verified support cases",
                "unit": "cases",
                "direction": "HIGHER_IS_BETTER",
            },
        ),
        201,
    )
    draft = command(
        objective="Reliable support",
        goals=[
            {
                "definition_id": definition["id"],
                "baseline": "0",
                "target": "100",
                "weight": "100",
                "method": "SUM",
                "source": "Distinct verified case IDs",
                "acceptance": "QA accepted",
            }
        ],
    )
    plan = ok(manager.post(f"{BASE}/participants/{participant}/plan", json=draft))
    return {
        "world": world,
        "hr": hr,
        "manager": manager,
        "owner": owner,
        "cycle": cycle,
        "participant": participant,
        "plan": plan,
        "draft": draft,
    }


def plan_action(flow, action, actor="manager", **extras):
    plan = flow["plan"]
    response = flow[actor].post(
        f"{BASE}/plans/{plan['id']}/actions",
        json=command(
            expected_version=plan["version"], revision=plan["revision"], action=action, **extras
        ),
    )
    flow["plan"] = ok(response)
    return flow["plan"]


def activate(flow):
    plan_action(flow, "submit")
    plan_action(flow, "approve")
    plan_action(flow, "acknowledge", "owner")
    return ok(
        flow["hr"].post(
            f"/api/v1/review-cycles/{flow['cycle']['id']}/activate", json={"expected_version": 2}
        )
    )


def create_work(flow, actor="manager", **extras):
    return ok(
        flow[actor].post(
            f"{BASE}/plans/{flow['plan']['id']}/items",
            json=command(
                expected_version=flow["plan"]["version"],
                title="Resolve support case",
                acceptance="Customer confirms resolution",
                source_key=str(uuid4()),
                goal_id=flow["plan"]["goals"][0]["id"],
                due_at=(datetime.now(UTC) + timedelta(days=2)).isoformat(),
                **extras,
            ),
        )
    )


def act(flow, item, action, actor="owner", **extras):
    return ok(
        flow[actor].post(
            f"{BASE}/items/{item['id']}/actions",
            json=command(expected_version=item["version"], action=action, **extras),
        )
    )


def test_plan_revision_acknowledgement_and_activation(flow):
    plan_action(flow, "submit")
    plan_action(flow, "approve")
    old = plan_action(flow, "acknowledge", "owner")
    plan_action(flow, "clarify", "owner", body="Explain the acceptance rule")
    flow["draft"]["client_request_id"] = str(uuid4())
    flow["draft"]["expected_version"] = flow["plan"]["version"]
    plan = ok(
        flow["manager"].post(f"{BASE}/participants/{flow['participant']}/plan", json=flow["draft"])
    )
    assert plan["revision"] == 2 and plan["acknowledged_revision"] is None
    flow["plan"] = plan
    plan_action(flow, "submit")
    plan_action(flow, "approve")
    response = flow["owner"].post(
        f"{BASE}/plans/{plan['id']}/actions",
        json=command(
            expected_version=flow["plan"]["version"], revision=old["revision"], action="acknowledge"
        ),
    )
    assert response.status_code == 409
    assert (
        flow["hr"]
        .post(f"/api/v1/review-cycles/{flow['cycle']['id']}/activate", json={"expected_version": 2})
        .status_code
        == 409
    )
    plan_action(flow, "acknowledge", "owner")
    ok(
        flow["hr"].post(
            f"/api/v1/review-cycles/{flow['cycle']['id']}/activate", json={"expected_version": 2}
        )
    )


def test_end_to_end_resubmissions_and_notifications(flow):
    activate(flow)
    item = create_work(flow)
    item = act(flow, item, "start")
    item = act(flow, item, "block", body="Need customer data")
    assert item["status"] == "IN_PROGRESS" and "submit" not in item["actions"]
    item = act(flow, item, "unblock")
    item = act(flow, item, "submit", body="First result", url="https://example.com/case/1")
    item = act(flow, item, "return", "manager", body="Add QA confirmation")
    item = act(flow, item, "start")
    item = act(flow, item, "submit", body="QA confirms completion")
    item = act(flow, item, "accept", "manager", body="Meets agreed criteria")
    assert item["status"] == "ACCEPTED"
    detail = ok(flow["owner"].get(f"{BASE}/items/{item['id']}"))
    assert [s["body"] for s in detail["submissions"]] == ["QA confirms completion", "First result"]
    assert detail["submission_total"] == 2
    notices = ok(flow["owner"].get("/api/v1/notifications"))
    assert any(n["href"] == f"/work-management?item={item['id']}" for n in notices["items"])
    assert ok(flow["owner"].get(f"{BASE}/items"))["total"] == 1
    assert ok(flow["manager"].get("/api/v1/notifications/tasks"))["items"] == []


@pytest.mark.parametrize("actor", ["admin", "other", "bob"])
def test_scope_and_no_information_leak(flow, actor):
    client = flow["world"].client(actor)
    assert ok(client.get(f"{BASE}/participants"))["total"] == 0
    assert client.get(f"{BASE}/plans/{flow['plan']['id']}").status_code == 404
    activate(flow)
    item = create_work(flow)
    assert client.get(f"{BASE}/items/{item['id']}").status_code == 404
    assert ok(client.get(f"{BASE}/items"))["total"] == 0


def test_hr_reads_plans_but_not_work_and_employee_cannot_approve(flow):
    assert (
        flow["owner"]
        .post(
            f"{BASE}/plans/{flow['plan']['id']}/actions", json=command(action="approve", revision=1)
        )
        .status_code
        == 409
    )
    assert ok(flow["hr"].get(f"{BASE}/plans/{flow['plan']['id']}"))["actions"] == []
    activate(flow)
    item = create_work(flow, "owner")
    assert item["status"] == "PROPOSED"
    assert flow["hr"].get(f"{BASE}/items/{item['id']}").status_code == 404
    item = act(flow, item, "publish", "manager")
    assert item["status"] == "TODO"


def test_replay_conflict_and_concurrent_decision(flow):
    activate(flow)
    item = act(flow, create_work(flow), "start")
    data = command(expected_version=item["version"], action="submit", body="Verified output")
    path = f"{BASE}/items/{item['id']}/actions"
    submitted = ok(flow["owner"].post(path, json=data))
    assert ok(flow["owner"].post(path, json=data))["version"] == submitted["version"]
    assert flow["owner"].post(path, json={**data, "body": "Different"}).status_code == 409

    def decide(action):
        return (
            flow["world"]
            .client("manager")
            .post(
                path,
                json=command(expected_version=submitted["version"], action=action, body="Decision"),
            )
            .status_code
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(decide, ["accept", "return"])) == [200, 409]
    with Session(flow["world"].engine) as session:
        assert session.scalar(select(func.count()).select_from(EvidenceSubmission)) == 1


def test_audit_failure_rolls_back_state_events_and_notifications(flow, monkeypatch):
    activate(flow)
    item = create_work(flow)
    with Session(flow["world"].engine) as session:
        counts = [
            session.scalar(select(func.count()).select_from(t)) for t in (WorkEvent, Notification)
        ]

    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(AuditWriter, "record", fail)
    assert (
        flow["owner"]
        .post(f"{BASE}/items/{item['id']}/actions", json=command(action="block", body="Need help"))
        .status_code
        == 500
    )
    assert not ok(flow["owner"].get(f"{BASE}/items/{item['id']}"))["blocked"]
    with Session(flow["world"].engine) as session:
        assert [
            session.scalar(select(func.count()).select_from(t)) for t in (WorkEvent, Notification)
        ] == counts


def test_legacy_bypasses_and_active_organization_changes_blocked(flow):
    activate(flow)
    world, cycle = flow["world"], flow["cycle"]["id"]
    employee = world.employees["alice"]
    response = flow["manager"].put(
        f"/api/v1/employees/{employee}/kpis?cycle_id={cycle}",
        json={"expected_evidence_version": 2, "items": []},
    )
    assert response.status_code in {409, 422}
    # Direct service guards are also tested by calculate/close API calls.
    response = flow["manager"].post(
        f"/api/v1/performance/{employee}/calculate",
        json={"cycle_id": cycle, "expected_evidence_version": 2},
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "managed_by_workflow"
    response = flow["hr"].post(f"/api/v1/review-cycles/{cycle}/close", json={"expected_version": 3})
    assert response.status_code == 409
    response = flow["hr"].patch(
        f"/api/v1/employees/{employee}", json={"manager_id": world.employees["other"]}
    )
    assert response.status_code == 409


@pytest.mark.parametrize(
    "header,value", [("Origin", "https://evil.example"), ("X-CSRF-Token", "invalid")]
)
def test_csrf(flow, header, value):
    client = flow["world"].client("manager")
    client.headers[header] = value
    assert (
        client.post(
            f"{BASE}/participants/{flow['participant']}/plan", json=flow["draft"]
        ).status_code
        == 403
    )


def test_schema_parity_constraints_and_immutable_revision(flow):
    with flow["world"].engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    with Session(flow["world"].engine) as session:
        plan = session.scalar(select(WorkPlan))
        assert plan is not None
        goal = session.scalar(select(WorkGoal))
        assert goal is not None
        goal.specification = {"tampered": True}
        with pytest.raises(IntegrityError):
            session.commit()
    with flow["world"].engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(text("UPDATE work_plans SET version = 0"))


def test_disabled_owner_stops_work_but_account_security_remains_available(flow):
    activate(flow)
    work = create_work(flow)
    ok(
        flow["world"]
        .client("admin")
        .patch(f"/api/v1/users/{flow['world'].users['alice']}", json={"is_active": False})
    )
    view = ok(flow["manager"].get(f"{BASE}/items/{work['id']}"))
    assert view["needs_hr"] and not view["actions"]
    assert (
        flow["manager"]
        .post(
            f"{BASE}/plans/{flow['plan']['id']}/items",
            json=command(
                expected_version=flow["plan"]["version"],
                title="Should not be assigned",
                acceptance="QA",
                source_key="disabled",
                due_at=(datetime.now(UTC) + timedelta(days=2)).isoformat(),
            ),
        )
        .status_code
        == 409
    )


def test_mode_is_fixed_and_schedule_is_validated(flow):
    hr, cycle = flow["hr"], flow["cycle"]["id"]
    from datetime import date

    shifted = date.fromisoformat(flow["cycle"]["start_date"]) + timedelta(days=1)
    response = hr.patch(
        f"/api/v1/review-cycles/{cycle}", json={"expected_version": 2, "start_date": str(shifted)}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "plan_schedule_frozen"
    assert (
        hr.patch(
            f"/api/v1/review-cycles/{cycle}",
            json={"expected_version": 2, "workflow_mode": "LEGACY"},
        ).status_code
        == 422
    )
    assert (
        hr.patch(
            f"/api/v1/review-cycles/{cycle}",
            json={"expected_version": 2, "start_date": "2000-01-01"},
        ).status_code
        == 422
    )
    assert (
        hr.request(
            "DELETE",
            f"/api/v1/review-cycles/{cycle}/participants/{flow['participant']}",
            json={"expected_version": 2},
        ).status_code
        == 409
    )


def test_create_replay_goal_validation_and_dashboard_no_fake_scores(flow):
    activate(flow)
    replay = ok(
        flow["manager"].post(f"{BASE}/participants/{flow['participant']}/plan", json=flow["draft"])
    )
    assert replay["id"] == flow["plan"]["id"]
    plan = flow["plan"]
    data = command(
        expected_version=plan["version"],
        title="Test task",
        acceptance="QA",
        source_key="case-1",
        due_at=(datetime.now(UTC) + timedelta(days=1)).isoformat(),
    )
    path = f"{BASE}/plans/{plan['id']}/items"
    one = ok(flow["manager"].post(path, json=data))
    assert ok(flow["manager"].post(path, json=data))["id"] == one["id"]
    assert (
        flow["manager"]
        .post(
            path,
            json={
                **data,
                "client_request_id": str(uuid4()),
                "goal_id": str(uuid4()),
                "source_key": "other",
            },
        )
        .status_code
        == 422
    )
    dashboard = ok(flow["owner"].get("/api/v1/dashboard"))
    assert dashboard["continuous"]["open_work"] == 1
    assert dashboard["average"] is None and not dashboard["score_bands"]
    allocation = ok(
        flow["manager"].get(
            f"/api/v1/employees/{flow['world'].employees['alice']}/kpis?cycle_id={flow['cycle']['id']}"
        )
    )
    assert len(allocation["items"]) == 1 and allocation["items"][0]["actual"] is None
    assert not allocation["participant"]["can_manage_kpis"]


def test_employee_can_edit_only_unpublished_own_proposal(flow):
    activate(flow)
    work = create_work(flow, "owner")
    data = command(
        title="Revised proposal",
        acceptance="QA and customer confirm",
        source_key="own-proposal",
        priority="HIGH",
        due_at=(datetime.now(UTC) + timedelta(days=2)).isoformat(),
    )
    path = f"{BASE}/items/{work['id']}/draft"
    revised = ok(flow["owner"].post(path, json=data))
    assert revised["title"] == "Revised proposal" and revised["status"] == "PROPOSED"
    assert ok(flow["owner"].post(path, json=data))["version"] == revised["version"]
    published = act(flow, revised, "publish", "manager")
    assert (
        flow["owner"]
        .post(
            path,
            json={
                **data,
                "client_request_id": str(uuid4()),
                "expected_version": published["version"],
                "title": "Silent changed promise",
            },
        )
        .status_code
        == 409
    )
