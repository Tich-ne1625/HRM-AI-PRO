from uuid import UUID

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.models import AuditLog

from .test_feedback_workflows import create_assignment, feedback_world, submit


@pytest.mark.parametrize("relationship", ["PEER", "SUBORDINATE"])
@pytest.mark.parametrize("count", [0, 1, 2, 3])
def test_group_threshold_raw_hr_and_own_authored_boundaries(world, relationship, count):
    # Existing real users have persisted sessions; include ADMIN and a manager
    # without any report access to prove reviewer eligibility is role independent.
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
    cycle, participant = feedback_world(world)
    for name in names[:count]:
        assignment = create_assignment(world, participant, name, relationship, required=False)
        assert assignment.status_code == 201, assignment.text
        response = submit(world, assignment.json(), name, comment="PRIVATE-COMMENT-SENTINEL")
        assert response.status_code == 201, response.text
        participant["evidence_version"] = response.json()["evidence_version"]
    path = f"/api/v1/employees/{world.employees['alice']}/feedback?cycle_id={cycle['id']}"
    for viewer in ("alice", "manager", "hr"):
        response = world.client(viewer).get(path)
        assert response.status_code == 200, response.text
        summary = response.json()
        group = next(g for g in summary["groups"] if g["relationship"] == relationship)
        assert group["suppressed"] == (count < 3)
        assert group["count"] == (None if count < 3 else count)
        assert group["mean"] == (None if count < 3 else "4.00")
        assert summary["count"] == count
        assert "PRIVATE-COMMENT-SENTINEL" not in response.text
        assert "reviewer_id" not in response.text
    raw = world.client().get("/api/v1/feedback-assignments?view=administration").json()
    assert raw["total"] == count
    assert all(r["submission"]["comment"] == "PRIVATE-COMMENT-SENTINEL" for r in raw["items"])
    for name in names[:count]:
        own = world.client(name).get("/api/v1/feedback-assignments").json()
        assert own["total"] == 1 and "reviewer_id" not in own["items"][0]
        assert world.client(name).get(path).status_code in (403, 404)
    with Session(world.engine) as session:
        audits = session.scalars(
            select(AuditLog).where(AuditLog.action == "feedback.submitted")
        ).all()
        assert len(audits) == count
        assert all(
            not {"comment", "rating", "eligibility_snapshot", "email"} & a.metadata_.keys()
            for a in audits
        )


def test_required_coverage_only_ready_after_self_manager_and_other_required(world):
    _cycle, participant = feedback_world(world)
    rows = []
    for name, relationship in (("alice", "SELF"), ("manager", "MANAGER"), ("bob", "PEER")):
        response = create_assignment(world, participant, name, relationship)
        assert response.status_code == 201
        rows.append((name, response.json()["id"]))
        participant["evidence_version"] = response.json()["evidence_version"]
    path = f"/api/v1/feedback-context?participant_id={participant['id']}"
    assert not world.client().get(path).json()["coverage"]["ready"]
    for index, (name, identifier) in enumerate(rows):
        row = world.client(name).get(f"/api/v1/feedback-assignments/{identifier}").json()
        assert submit(world, row, name).status_code == 201
        coverage = world.client().get(path).json()["coverage"]
        assert coverage["ready"] == (index == 2)
        assert coverage["pending_required"] == 2 - index
    assert world.client("alice").get(path).status_code == 403


def test_options_use_snapshot_identity_pagination_and_literal_search(world):
    from app.models import Employee, User

    _, participant = feedback_world(world)
    base = f"/api/v1/feedback-reviewer-options?participant_id={participant['id']}"
    self_options = world.client().get(base + "&relationship=SELF").json()
    assert self_options["total"] == 1
    assert self_options["items"][0]["reviewer_id"] == world.users["alice"]
    assert "email" not in str(self_options)
    peers = world.client().get(base + "&relationship=PEER&page_size=1").json()
    assert peers["total"] == 2 and len(peers["items"]) == 1
    assert world.client().get(base + "&relationship=PEER&q=%25").json()["total"] == 0
    assert world.client("manager").get(base + "&relationship=SELF").status_code == 403
    with Session(world.engine) as session, session.begin():
        session.get(Employee, UUID(world.employees["manager"])).user_id = None
        session.get(User, UUID(world.users["manager"])).is_active = False
    manager_options = world.client().get(base + "&relationship=MANAGER").json()
    assert manager_options["total"] == 1
    assert manager_options["items"][0]["reviewer_id"] == world.users["manager"]
    assert not manager_options["items"][0]["is_active"]


def test_administration_list_query_count_is_bounded(world):
    _, participant = feedback_world(world)
    for name, relation in (
        ("alice", "SELF"),
        ("manager", "MANAGER"),
        ("bob", "PEER"),
        ("other", "PEER"),
        ("indirect", "SUBORDINATE"),
    ):
        response = create_assignment(world, participant, name, relation)
        assert response.status_code == 201
        participant["evidence_version"] = response.json()["evidence_version"]
    queries = []

    def record(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            queries.append(statement)

    event.listen(world.engine, "before_cursor_execute", record)
    try:
        response = world.client().get("/api/v1/feedback-assignments?view=administration")
        assert response.status_code == 200 and response.json()["total"] == 5
        assert len(queries) <= 7, f"N+1 query regression: {len(queries)} SELECTs"
    finally:
        event.remove(world.engine, "before_cursor_execute", record)
