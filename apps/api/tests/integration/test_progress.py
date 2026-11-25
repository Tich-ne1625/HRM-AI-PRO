from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import Base
from app.modules.audit.service import AuditWriter
from app.modules.notifications.models import Notification
from app.modules.progress.models import Measurement, ProgressEvent, ProgressSnapshot

from .test_work_management import BASE, act, activate, command, create_work, ok
from .test_work_management import flow as flow

PROGRESS = "/api/v1/progress"


def draft(flow, **overrides):
    values = {
        "source_key": f"CASE-{uuid4()}",
        "occurred_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        "value": "10",
        "body": "Business event confirmed in the source register",
        **overrides,
    }
    return command(expected_version=flow["plan"]["version"], **values)


def create(flow, data=None):
    return ok(
        flow["owner"].post(
            f"{PROGRESS}/goals/{flow['plan']['goals'][0]['id']}/measurements",
            json=data or draft(flow),
        )
    )


def decide(flow, row, action, actor="owner", **overrides):
    return ok(
        flow[actor].post(
            f"{PROGRESS}/measurements/{row['id']}/actions",
            json=command(
                expected_version=row["version"],
                action=action,
                body="Verified source and business rule",
                **overrides,
            ),
        )
    )


def goals(flow):
    return ok(flow["owner"].get(f"{PROGRESS}/plans/{flow['plan']['id']}/goals"))


def edit(flow, row, **overrides):
    data = {
        "source_kind": row["source_kind"],
        "source_key": row["source_key"],
        "work_item_id": row["work_item_id"],
        "occurred_at": row["occurred_at"],
        "milestone": row["milestone"],
        "kind": "VALUE",
        "value": "8",
        "body": "Correction with supporting register",
        **overrides,
    }
    return ok(
        flow["owner"].post(
            f"{PROGRESS}/measurements/{row['id']}/draft",
            json=command(expected_version=row["version"], **data),
        )
    )


def test_measurement_correction_void_and_old_snapshots(flow):
    activate(flow)
    data = draft(flow)
    row = create(flow, data)
    assert create(flow, data)["id"] == row["id"]
    row = decide(flow, row, "submit")
    row = decide(flow, row, "return", "manager")
    row = edit(flow, row, value="10")
    row = decide(flow, row, "submit")
    row = decide(flow, row, "verify", "manager")
    assert goals(flow)["goals"][0]["actual"] == "10.0000"
    snapshots = ok(flow["owner"].get(f"{PROGRESS}/plans/{flow['plan']['id']}/snapshots"))["items"]
    original = ok(flow["owner"].get(f"{PROGRESS}/snapshots/{snapshots[0]['id']}"))
    row = edit(flow, row)
    row = decide(flow, row, "submit")
    assert goals(flow)["goals"][0]["actual"] == "10.0000"
    row = decide(flow, row, "verify", "manager")
    assert goals(flow)["goals"][0]["actual"] == "8.0000"
    row = edit(flow, row, kind="VOID", value=None)
    row = decide(flow, row, "submit")
    row = decide(flow, row, "verify", "manager")
    assert goals(flow)["goals"][0]["actual"] is None
    assert ok(flow["owner"].get(f"{PROGRESS}/snapshots/{original['id']}")) == original
    assert original["sources"]["items"][0]["payload"]["value"] == "10"


def test_work_reopen_suspends_source_without_rewriting_history(flow):
    activate(flow)
    work = create_work(flow)
    work = act(flow, work, "start")
    work = act(flow, work, "submit", body="Customer accepted and QA checked")
    work = act(flow, work, "accept", "manager", body="Output meets acceptance")
    flow["plan"] = ok(flow["manager"].get(f"{BASE}/plans/{flow['plan']['id']}"))
    data = draft(flow, source_kind="WORK", work_item_id=work["id"])
    data["source_key"] = work["source_key"]
    row = create(flow, data)
    row = decide(flow, row, "submit")
    row = decide(flow, row, "verify", "manager")
    assert goals(flow)["goals"][0]["actual"] == "10.0000"
    work = act(flow, work, "reopen", "manager", body="QA found missing documentation")
    assert goals(flow)["goals"][0]["actual"] is None
    suspended = ok(flow["owner"].get(f"{PROGRESS}/measurements/{row['id']}"))
    assert suspended["suspended"]
    work = act(flow, work, "start")
    work = act(flow, work, "submit", body="Added missing QA references")
    act(flow, work, "accept", "manager", body="New evidence meets criteria")
    assert goals(flow)["goals"][0]["actual"] is None
    row = edit(flow, suspended, value="9")
    row = decide(flow, row, "submit")
    decide(flow, row, "verify", "manager")
    assert goals(flow)["goals"][0]["actual"] == "9.0000"


@pytest.mark.parametrize("role", ["hr", "admin", "other", "bob"])
def test_measurements_and_checkins_are_private_to_pair(flow, role):
    activate(flow)
    row = create(flow)
    client = flow["world"].client(role)
    assert client.get(f"{PROGRESS}/measurements/{row['id']}").status_code == 404
    assert client.get(f"{PROGRESS}/plans/{flow['plan']['id']}/goals").status_code == 404
    assert client.get(f"/api/v1/checkins?plan_id={flow['plan']['id']}").status_code == 404
    if role == "hr":
        value = ok(client.get(f"{PROGRESS}/plans/{flow['plan']['id']}/coordination"))
        assert value["measurements"] == {"DRAFT": 1}
        assert "Business event" not in str(value) and "actual" not in str(value)


def test_source_collision_request_conflict_and_atomic_failure(flow, monkeypatch):
    activate(flow)
    data = draft(flow)
    row = create(flow, data)
    changed = dict(data, value="12")
    assert (
        flow["owner"]
        .post(f"{PROGRESS}/goals/{row['goal_id']}/measurements", json=changed)
        .status_code
        == 409
    )
    duplicate = dict(
        data, client_request_id=str(uuid4()), source_key=f"  {data['source_key'].lower()}  "
    )
    assert (
        flow["owner"]
        .post(f"{PROGRESS}/goals/{row['goal_id']}/measurements", json=duplicate)
        .status_code
        == 409
    )
    row = decide(flow, row, "submit")
    with Session(flow["world"].engine) as session:
        before = [
            session.scalar(select(func.count()).select_from(t))
            for t in (ProgressEvent, ProgressSnapshot, Notification)
        ]
    original = AuditWriter.record

    def fail(*args, **kwargs):
        if args[3].startswith("progress."):
            raise RuntimeError("audit unavailable")
        return original(*args, **kwargs)

    monkeypatch.setattr(AuditWriter, "record", fail)
    response = flow["manager"].post(
        f"{PROGRESS}/measurements/{row['id']}/actions",
        json=command(expected_version=row["version"], action="verify", body="Accept"),
    )
    assert response.status_code == 500
    with Session(flow["world"].engine) as session:
        assert before == [
            session.scalar(select(func.count()).select_from(t))
            for t in (ProgressEvent, ProgressSnapshot, Notification)
        ]
        assert session.get(Measurement, UUID(row["id"])).status == "SUBMITTED"


def test_concurrent_verify_return_and_csrf(flow):
    activate(flow)
    row = decide(flow, create(flow), "submit")
    path = f"{PROGRESS}/measurements/{row['id']}/actions"
    assert (
        flow["manager"]
        .post(
            path,
            json=command(expected_version=row["version"], action="verify", body="OK"),
            headers={"X-CSRF-Token": "wrong"},
        )
        .status_code
        == 403
    )

    def decision(action):
        return (
            flow["world"]
            .client("manager")
            .post(
                path, json=command(expected_version=row["version"], action=action, body="Reviewed")
            )
            .status_code
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(decision, ["verify", "return"])) == [200, 409]


def test_checkin_private_preparation_snapshot_clarification_and_support(flow):
    activate(flow)
    row = decide(flow, create(flow), "submit")
    decide(flow, row, "verify", "manager")
    checkin = ok(
        flow["manager"].post(
            f"{PROGRESS}/plans/{flow['plan']['id']}/checkins",
            json=command(
                expected_version=flow["plan"]["version"],
                title="Weekly support review",
                scheduled_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                period_start=flow["cycle"]["start_date"],
                period_end=datetime.now(UTC).date().isoformat(),
            ),
        )
    )
    path = f"/api/v1/checkins/{checkin['id']}"
    ok(
        flow["owner"].post(
            f"{path}/preparation", json=command(body="Private preparation", shared=False)
        )
    )
    assert ok(flow["manager"].get(path))["preparations"] == []

    def meeting(action, actor="manager", **extra):
        nonlocal checkin
        checkin = ok(
            flow[actor].post(
                f"{path}/actions",
                json=command(
                    expected_version=checkin["version"],
                    action=action,
                    publication=checkin["publication"],
                    **extra,
                ),
            )
        )
        return checkin

    meeting("open")
    meeting("publish", body="Need manager support from the partner team")
    assert checkin["snapshot"]["goals"][0]["actual"] == "10.0000"
    meeting("clarify", "owner", body="Please clarify the support deadline")
    assert checkin["clarification_pending"] and "acknowledge" not in checkin["actions"]
    meeting("addendum", body="Manager will obtain the partner data by tomorrow")
    meeting("acknowledge", "owner")
    assert checkin["acknowledged_publication"] == 2
    action = ok(
        flow["manager"].post(
            f"{path}/follow-ups",
            json=command(
                expected_version=checkin["version"],
                body="Manager obtains the missing partner data",
                owner_id=flow["world"].users["manager"],
                due_at=(datetime.now(UTC) + timedelta(days=1)).isoformat(),
            ),
        )
    )

    def support(step, actor):
        nonlocal action
        action = ok(
            flow[actor].post(
                f"/api/v1/checkin-actions/{action['id']}/actions",
                json=command(
                    expected_version=action["version"], action=step, body="Support step recorded"
                ),
            )
        )

    support("start", "manager")
    support("submit", "manager")
    assert "complete" not in action["actions"]
    support("complete", "owner")
    assert action["status"] == "DONE"
    assert "Private preparation" not in str(ok(flow["manager"].get(path))["publications"])


def test_schema_and_append_only_revision(flow):
    activate(flow)
    row = create(flow)
    with flow["world"].engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    with Session(flow["world"].engine) as session:
        with pytest.raises(IntegrityError):
            session.execute(
                text("UPDATE measurement_revisions SET payload = '{}' WHERE measurement_id = :id"),
                {"id": row["id"]},
            )
        session.rollback()


def measurement_method(flow, method):
    from app.modules.kpis.models import KPIDefinition

    data = flow["draft"]
    data["client_request_id"] = str(uuid4())
    data["expected_version"] = flow["plan"]["version"]
    specification = data["goals"][0]
    specification["method"] = method
    if method in {"RATIO", "MILESTONE"}:
        with Session(flow["world"].engine) as session, session.begin():
            session.get(KPIDefinition, UUID(specification["definition_id"])).unit = "%"
    if method == "RATIO":
        specification.update(numerator="Passed samples", denominator="All samples")
    if method == "MILESTONE":
        specification["milestones"] = [
            {"title": "First", "weight": "30"},
            {"title": "Second", "weight": "70"},
        ]
    flow["plan"] = ok(
        flow["manager"].post(f"{BASE}/participants/{flow['participant']}/plan", json=data)
    )
    activate(flow)


@pytest.mark.parametrize(
    "method,expected",
    [("SUM", "105.0000"), ("LAST", "50.0000"), ("RATIO", "83.33"), ("MILESTONE", "30.00")],
)
def test_real_ledger_aggregation_methods(flow, method, expected):
    measurement_method(flow, method)
    values = [{"value": "20"}, {"value": "35"}, {"value": "50"}]
    if method == "RATIO":
        values = [
            {"value": None, "numerator": "9", "denominator": "10"},
            {"value": None, "numerator": "1", "denominator": "2"},
        ]
    elif method == "MILESTONE":
        values = [{"value": None, "milestone": 0}]
    for index, value in enumerate(values):
        row = create(
            flow,
            draft(
                flow,
                occurred_at=(datetime.now(UTC) - timedelta(minutes=5 - index)).isoformat(),
                **value,
            ),
        )
        decide(flow, decide(flow, row, "submit"), "verify", "manager")
    assert goals(flow)["goals"][0]["actual"] == expected


@pytest.mark.parametrize("method", ["LAST", "MILESTONE"])
def test_void_allows_correct_source_replacement_but_not_double_reactivation(flow, method):
    measurement_method(flow, method)
    values = {"value": "10"} if method == "LAST" else {"value": None, "milestone": 0}
    original_data = draft(flow, **values)
    row = decide(flow, decide(flow, create(flow, original_data), "submit"), "verify", "manager")
    old_id = row["id"]
    row = edit(flow, row, kind="VOID", value=None)
    row = decide(flow, decide(flow, row, "submit"), "verify", "manager")
    replacement_data = dict(
        original_data, client_request_id=str(uuid4()), source_key="CORRECTED-SOURCE"
    )
    replacement = decide(
        flow, decide(flow, create(flow, replacement_data), "submit"), "verify", "manager"
    )
    assert replacement["id"] != old_id
    row = edit(flow, row, **values)
    row = decide(flow, row, "submit")
    response = flow["manager"].post(
        f"{PROGRESS}/measurements/{row['id']}/actions",
        json=command(
            expected_version=row["version"], action="verify", body="Try to reintroduce old source"
        ),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "duplicate_measurement_source"
    assert goals(flow)["goals"][0]["source_count"] == 1


def test_event_window_respects_cycle_timezone_and_exact_revision_is_readable(flow):
    from datetime import date, time

    activate(flow)
    first = date.fromisoformat(flow["cycle"]["start_date"])
    records = []
    for hour, minute, value in [(16, 59, "2"), (17, 1, "3")]:
        row = create(
            flow,
            draft(
                flow,
                occurred_at=datetime.combine(first, time(hour, minute), UTC).isoformat(),
                value=value,
            ),
        )
        records.append(decide(flow, decide(flow, row, "submit"), "verify", "manager"))
    response = ok(
        flow["owner"].get(
            f"{PROGRESS}/plans/{flow['plan']['id']}/goals?from_date={first}&to_date={first}"
        )
    )
    assert response["goals"][0]["actual"] == "2.0000"
    assert goals(flow)["goals"][0]["actual"] == "5.0000"
    row = edit(flow, records[0], value="1")
    decide(flow, decide(flow, row, "submit"), "verify", "manager")
    old = ok(flow["owner"].get(f"{PROGRESS}/measurements/{row['id']}?revision_number=1"))
    assert old["selected_revision"]["payload"]["value"] == "2"
    assert (
        flow["owner"].get(f"{PROGRESS}/measurements/{row['id']}?revision_number=999").status_code
        == 404
    )


def test_cutoff_blocks_new_input_but_keeps_verification_window(flow, monkeypatch):
    import app.modules.progress.service as service

    activate(flow)
    pending = decide(flow, create(flow), "submit")
    unsent = create(flow)
    cutoff = datetime.fromisoformat(flow["cycle"]["workflow_schedule"]["input_cutoff_at"])

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cutoff + timedelta(seconds=1)

    monkeypatch.setattr(service, "datetime", Clock)
    response = flow["owner"].post(
        f"{PROGRESS}/measurements/{unsent['id']}/actions",
        json=command(expected_version=unsent["version"], action="submit"),
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "workflow_cutoff"
    decide(flow, pending, "verify", "manager")


def test_paginated_measurement_reader_has_bounded_queries(flow):
    from sqlalchemy import event

    activate(flow)
    for _ in range(22):
        create(flow)
    queries = []

    def count(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(flow["world"].engine, "before_cursor_execute", count)
    try:
        result = ok(
            flow["owner"].get(f"{PROGRESS}/goals/{flow['plan']['goals'][0]['id']}/measurements")
        )
    finally:
        event.remove(flow["world"].engine, "before_cursor_execute", count)
    assert result["total"] == 22 and len(result["items"]) == 20
    assert len(queries) <= 18, len(queries)


@pytest.mark.parametrize("rollback", [False, True])
def test_verify_reopen_race_and_late_work_audit_failure(flow, monkeypatch, rollback):
    from app.modules.work_management.models import WorkItem

    activate(flow)
    work = create_work(flow)
    work = act(flow, work, "start")
    work = act(flow, work, "submit", body="Accepted QA evidence")
    work = act(flow, work, "accept", "manager", body="Meets the output criteria")
    flow["plan"] = ok(flow["manager"].get(f"{BASE}/plans/{flow['plan']['id']}"))
    row = create(
        flow,
        draft(flow, source_key=work["source_key"], source_kind="WORK", work_item_id=work["id"]),
    )
    row = decide(flow, row, "submit")
    if rollback:
        row = decide(flow, row, "verify", "manager")
        with Session(flow["world"].engine) as session:
            before = [
                session.scalar(select(func.count()).select_from(t))
                for t in (ProgressEvent, ProgressSnapshot, Notification)
            ]
        original = AuditWriter.record

        def fail_late(*args, **kwargs):
            if args[3] == "work.reopen":
                raise RuntimeError("late work audit failure")
            return original(*args, **kwargs)

        monkeypatch.setattr(AuditWriter, "record", fail_late)
        response = flow["manager"].post(
            f"{BASE}/items/{work['id']}/actions",
            json=command(
                expected_version=work["version"], action="reopen", body="Recheck QA evidence"
            ),
        )
        assert response.status_code == 500
        with Session(flow["world"].engine) as session:
            assert before == [
                session.scalar(select(func.count()).select_from(t))
                for t in (ProgressEvent, ProgressSnapshot, Notification)
            ]
            assert session.get(WorkItem, UUID(work["id"])).status == "ACCEPTED"
            assert not session.get(Measurement, UUID(row["id"])).suspended
        assert goals(flow)["goals"][0]["actual"] == "10.0000"
    else:

        def verify():
            return (
                flow["world"]
                .client("manager")
                .post(
                    f"{PROGRESS}/measurements/{row['id']}/actions",
                    json=command(
                        expected_version=row["version"], action="verify", body="Verify source"
                    ),
                )
                .status_code
            )

        def reopen():
            return (
                flow["world"]
                .client("manager")
                .post(
                    f"{BASE}/items/{work['id']}/actions",
                    json=command(
                        expected_version=work["version"],
                        action="reopen",
                        body="Recheck QA evidence",
                    ),
                )
                .status_code
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            verified, reopened = pool.submit(verify), pool.submit(reopen)
            assert verified.result(timeout=30) in {200, 409}
            assert reopened.result(timeout=30) == 200
        assert goals(flow)["goals"][0]["actual"] is None
        assert ok(flow["owner"].get(f"{BASE}/items/{work['id']}"))["status"] == "CHANGES_REQUESTED"


def test_read_load_sixty_participants_and_thousand_sources(flow):
    """Direct synthetic fixture for read cost, not an invented workflow history."""
    import json
    from pathlib import Path
    from time import perf_counter

    from sqlalchemy import event

    from app.models import CycleParticipant, Employee, User, WorkGoal, WorkPlan
    from app.modules.progress.models import MeasurementRevision, MetricRule
    from app.modules.progress.service import ProgressService
    from app.modules.work_management.models import PlanRevision

    activate(flow)
    with Session(flow["world"].engine) as session, session.begin():
        owner = session.get(User, UUID(flow["world"].users["alice"]))
        for index in range(59):
            account = User(
                email=f"p12-load-{index}@example.test",
                password_hash=owner.password_hash,
                role="EMPLOYEE",
                is_active=True,
            )
            session.add(account)
            session.flush()
            employee = Employee(
                employee_code=f"P12-LOAD-{index:03}",
                display_name=f"Load fixture {index}",
                user_id=account.id,
                manager_id=UUID(flow["world"].employees["manager"]),
                department_id=UUID(flow["world"].departments["ENG"]),
                position_id=UUID(flow["world"].positions["DEV"]),
            )
            session.add(employee)
            session.flush()
            participant = CycleParticipant(
                cycle_id=UUID(flow["cycle"]["id"]),
                employee_id=employee.id,
                snapshot={"fixture": "synthetic-read-load-only", "employee_id": str(employee.id)},
            )
            session.add(participant)
            session.flush()
            plan = WorkPlan(
                participant_id=participant.id,
                revision=1,
                status="APPROVED",
                acknowledged_revision=1,
                approved_by=UUID(flow["world"].users["manager"]),
            )
            session.add(plan)
            session.flush()
            session.add(
                PlanRevision(
                    plan_id=plan.id,
                    number=1,
                    author_id=UUID(flow["world"].users["manager"]),
                    objective="Synthetic read fixture",
                )
            )
            session.flush()
            original = session.get(WorkGoal, UUID(flow["plan"]["goals"][0]["id"]))
            session.add(
                WorkGoal(
                    plan_id=plan.id,
                    revision=1,
                    definition_id=original.definition_id,
                    specification=original.specification,
                )
            )
        plan = session.get(WorkPlan, UUID(flow["plan"]["id"]))
        goal = session.get(WorkGoal, UUID(flow["plan"]["goals"][0]["id"]))
        rule = MetricRule(
            plan_id=plan.id,
            plan_revision=plan.revision,
            goal_id=goal.id,
            specification=goal.specification,
        )
        session.add(rule)
        session.flush()
        rows = [
            Measurement(
                plan_id=plan.id,
                rule_id=rule.id,
                source_key=f"load-{i:04}",
                source_label=f"LOAD-{i:04}",
                source_kind="EXTERNAL_REFERENCE",
                occurred_at=datetime.now(UTC) - timedelta(minutes=1),
                number=1,
                status="VERIFIED",
                effective_number=1,
            )
            for i in range(1000)
        ]
        session.add_all(rows)
        session.flush()
        session.add_all(
            [
                MeasurementRevision(
                    measurement_id=row.id,
                    number=1,
                    kind="VALUE",
                    author_id=owner.id,
                    payload={
                        "value": "1",
                        "body": "Synthetic source for read-cost measurement",
                        "url": None,
                    },
                )
                for row in rows
            ]
        )
        ProgressService(session).snapshot(plan, changed=True)
    results = []
    queries = []

    def count(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(flow["world"].engine, "before_cursor_execute", count)
    try:
        paths = [
            f"{BASE}/participants",
            f"{PROGRESS}/plans/{flow['plan']['id']}/goals",
            f"{PROGRESS}/goals/{flow['plan']['goals'][0]['id']}/measurements",
        ]
        for path in paths:
            queries.clear()
            start = perf_counter()
            data = ok(flow["manager"].get(path))
            results.append(
                {
                    "path": path,
                    "queries": len(queries),
                    "duration_ms": round((perf_counter() - start) * 1000, 2),
                }
            )
            assert len(queries) <= 20, results[-1]
            if path.endswith("/participants"):
                assert data["total"] == 60 and len(data["items"]) == 20
            elif path.endswith("/goals"):
                assert data["goals"][0]["actual"] == "1000.0000"
                assert data["goals"][0]["source_count"] == 1000
            else:
                assert data["total"] == 1000 and len(data["items"]) == 20
    finally:
        event.remove(flow["world"].engine, "before_cursor_execute", count)
    folder = Path(__file__).resolve().parents[4] / ".superpowers/phase12"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "performance.json").write_text(
        json.dumps(
            {
                "participants": 60,
                "verified_sources": 1000,
                "fixture_only_not_workflow_history": True,
                "reads": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_work_request_uuid_is_independent_of_progress_command_namespace(flow):
    activate(flow)
    work = create_work(flow)
    work = act(flow, work, "start")
    work = act(flow, work, "submit", body="QA accepted")
    work = act(flow, work, "accept", "manager", body="Meets criteria")
    flow["plan"] = ok(flow["manager"].get(f"{BASE}/plans/{flow['plan']['id']}"))
    data = draft(flow, source_key=work["source_key"], source_kind="WORK", work_item_id=work["id"])
    row = decide(flow, create(flow, data), "submit")
    shared_id = str(uuid4())
    ok(
        flow["manager"].post(
            f"{PROGRESS}/measurements/{row['id']}/actions",
            json=command(
                client_request_id=shared_id,
                expected_version=row["version"],
                action="verify",
                body="Verified source",
            ),
        )
    )
    data = command(
        client_request_id=shared_id,
        expected_version=work["version"],
        action="reopen",
        body="Recheck output",
    )
    result = ok(flow["manager"].post(f"{BASE}/items/{work['id']}/actions", json=data))
    assert result["status"] == "CHANGES_REQUESTED"
    assert (
        ok(flow["manager"].post(f"{BASE}/items/{work['id']}/actions", json=data))["version"]
        == result["version"]
    )
    assert goals(flow)["goals"][0]["actual"] is None
    with Session(flow["world"].engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(ProgressEvent)
                .where(ProgressEvent.kind == "measurement.suspended")
            )
            == 1
        )


def test_writer_role_denial_precedes_resource_resolution(flow):
    activate(flow)
    row = create(flow)
    for role in ("hr", "admin"):
        client = flow["world"].client(role)
        for identifier in (row["id"], str(uuid4())):
            response = client.post(
                f"{PROGRESS}/measurements/{identifier}/actions", json=command(action="submit")
            )
            assert response.status_code == 403
            response = client.post(f"{PROGRESS}/measurements/{identifier}/draft", json=draft(flow))
            assert response.status_code == 403
        for identifier in (flow["plan"]["goals"][0]["id"], str(uuid4())):
            assert (
                client.post(
                    f"{PROGRESS}/goals/{identifier}/measurements", json=draft(flow)
                ).status_code
                == 403
            )
