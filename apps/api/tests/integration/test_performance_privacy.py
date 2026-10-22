from uuid import UUID

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models import Employee, User

from .test_feedback_workflows import create_assignment, submit
from .test_performance import calculate, ready_world


@pytest.mark.parametrize("relationship", ["PEER", "SUBORDINATE"])
@pytest.mark.parametrize("count", [0, 1, 2, 3])
def test_report_and_revision_suppress_each_small_group(world, relationship, count):
    names = ["admin", "spare", "unlinked"]
    for index, name in enumerate(names):
        response = world.client().post(
            "/api/v1/employees",
            json=world.employee_payload(
                employee_code=f"EXTRA-{index}",
                display_name=f"Reviewer {index}",
                user_id=world.users[name],
                manager_id=world.employees["alice"] if relationship == "SUBORDINATE" else None,
            ),
        )
        assert response.status_code == 201
    cycle, participant, _, base = ready_world(world)
    for name in names[:count]:
        assignment = create_assignment(world, participant, name, relationship, required=False)
        assert assignment.status_code == 201, assignment.text
        sent = submit(world, assignment.json(), name, comment="PRIVATE-REVIEW-SENTINEL")
        assert sent.status_code == 201
        participant["evidence_version"] = sent.json()["evidence_version"]
    report = calculate(world, cycle, participant, base).json()
    for viewer in ("alice", "manager", "hr"):
        for path in (
            base + f"?cycle_id={cycle['id']}",
            f"/api/v1/reviews/{report['review_id']}/revisions/1",
        ):
            response = world.client(viewer).get(path)
            assert response.status_code == 200, response.text
            result = response.json().get("current_result", response.json())
            group = next(
                g for g in result["feedback"]["groups"] if g["relationship"] == relationship
            )
            assert group["suppressed"] == (count < 3)
            assert group["count"] == (None if count < 3 else count)
            assert group["mean"] == (None if count < 3 else "4.00")
            assert "PRIVATE-REVIEW-SENTINEL" not in response.text
            assert "reviewer_id" not in response.text


def test_own_submission_is_selected_from_revision_membership(world):
    cycle, participant, _, base = ready_world(world, optional=True)
    report = calculate(world, cycle, participant, base).json()
    assignment = world.client("bob").get("/api/v1/feedback-assignments").json()["items"][0]
    assert submit(world, assignment, "bob", comment="Later own comment").status_code == 201
    participant["evidence_version"] += 1
    calculate(world, cycle, participant, base)
    # Bob gains live report access after the calculations; own feedback remains historical.
    with Session(world.engine) as session, session.begin():
        session.get(User, UUID(world.users["bob"])).role = "MANAGER"
        session.get(Employee, UUID(world.employees["alice"])).manager_id = UUID(
            world.employees["bob"]
        )
    revisions = f"/api/v1/reviews/{report['review_id']}/revisions"
    assert world.client("bob").get(revisions + "/1").json()["feedback"]["own_submission"] is None
    assert (
        world.client("bob").get(revisions + "/2").json()["feedback"]["own_submission"]["comment"]
        == "Later own comment"
    )


def test_report_and_history_queries_are_bounded(world):
    cycle, participant, item, base = ready_world(world)
    report = calculate(world, cycle, participant, base).json()
    for value in ("50.0000", "60.0000", "70.0000"):
        assert (
            world.client()
            .patch(
                f"/api/v1/employee-kpis/{item['id']}",
                json={
                    "expected_evidence_version": participant["evidence_version"],
                    "actual": value,
                },
            )
            .status_code
            == 200
        )
        participant["evidence_version"] += 1
        calculate(world, cycle, participant, base)
    statements = []

    def record(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(world.engine, "before_cursor_execute", record)
    try:
        response = world.client("alice").get(base + f"?cycle_id={cycle['id']}")
        assert response.status_code == 200
        assert len(statements) <= 12, f"Report query regression: {len(statements)}"
        statements.clear()
        history = world.client("alice").get(
            f"/api/v1/reviews/{report['review_id']}/revisions?page_size=2"
        )
        assert history.status_code == 200 and history.json()["total"] == 4
        assert [r["calculation_version"] for r in history.json()["items"]] == [4, 3]
        assert len(statements) <= 6, f"History N+1 regression: {len(statements)}"
    finally:
        event.remove(world.engine, "before_cursor_execute", record)
