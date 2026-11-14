from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    CycleParticipant,
    Employee,
    FeedbackAssignment,
    Notification,
    ReviewCycle,
    User,
    UserRole,
)
from app.modules.feedback.service import FeedbackService

from .test_feedback_workflows import create_assignment, feedback_world


def extra_reviewer(world, *, subordinate=False):
    with Session(world.engine) as session, session.begin():
        template = session.get(User, UUID(world.users["alice"]))
        user = User(
            email="batch-peer@example.com",
            password_hash=template.password_hash,
            role=UserRole.EMPLOYEE,
        )
        session.add(user)
        session.flush()
        employee = Employee(
            employee_code="BATCH-02",
            display_name="Batch Reviewer",
            department_id=UUID(world.departments["ENG"]),
            position_id=UUID(world.positions["DEV"]),
            user_id=user.id,
            manager_id=UUID(world.employees["alice"]) if subordinate else None,
        )
        session.add(employee)
        session.flush()
        return str(user.id), str(employee.id)


def payload(world, participant, reviewers, **changes):
    return {
        "participant_id": participant["id"],
        "reviewer_ids": reviewers,
        "relationship": "PEER",
        "required": False,
        "due_at": None,
        "expected_evidence_version": participant["evidence_version"],
        **changes,
    }


def snapshot(world):
    with Session(world.engine) as session:
        return tuple(
            session.scalar(select(func.count()).select_from(model))
            for model in (FeedbackAssignment, Notification, AuditLog)
        )


@pytest.mark.parametrize("relation", ["PEER", "SUBORDINATE"])
def test_batch_assigns_each_reviewer_once_with_one_version_and_individual_notices(world, relation):
    extra, _ = extra_reviewer(world, subordinate=relation == "SUBORDINATE")
    _, participant = feedback_world(world)
    reviewer = world.users["bob" if relation == "PEER" else "indirect"]
    body = payload(world, participant, [reviewer, extra], relationship=relation)
    response = world.client().post("/api/v1/feedback-assignments/bulk", json=body)
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["created_count"] == 2 and len(set(result["assignment_ids"])) == 2
    assert result["evidence_version"] == participant["evidence_version"] + 1
    with Session(world.engine) as session:
        notices = list(
            session.scalars(select(Notification).where(Notification.kind == "assignment.created"))
        )
        assert {str(row.recipient_id) for row in notices} == {reviewer, extra}
        assert {str(row.assignment_id) for row in notices} == set(result["assignment_ids"])
    before = snapshot(world)
    assert world.client().post("/api/v1/feedback-assignments/bulk", json=body).status_code == 409
    assert snapshot(world) == before
    assert (
        world.client()
        .post(
            "/api/v1/feedback-assignments/bulk",
            json={**body, "expected_evidence_version": result["evidence_version"]},
        )
        .json()["error"]["code"]
        == "assignment_already_exists"
    )


def test_department_filter_applies_before_count_and_select_all_excludes_existing(world):
    extra, _ = extra_reviewer(world)
    _, participant = feedback_world(world)
    path = "/api/v1/feedback-reviewer-options"
    params = {
        "participant_id": participant["id"],
        "relationship": "PEER",
        "department_id": world.departments["ENG"],
        "available_only": True,
    }
    data = world.client().get(path, params=params).json()
    assert data["total"] == 1 and data["items"][0]["reviewer_id"] == extra
    assert (
        world.client()
        .get(path, params={**params, "department_id": world.departments["UNUSED"]})
        .json()["total"]
        == 0
    )
    assert (
        world.client()
        .post("/api/v1/feedback-assignments/bulk", json=payload(world, participant, [extra]))
        .status_code
        == 201
    )
    assert world.client().get(path, params=params).json()["total"] == 0
    # Default option mode retains historical assignment status for editors.
    data = world.client().get(path, params={**params, "available_only": False}).json()
    assert data["items"][0]["existing_status"] == "OPEN"


@pytest.mark.parametrize(
    "invalid", ["wrong_relationship", "inactive", "duplicate", "past_due", "stale"]
)
def test_batch_revalidates_every_recipient_and_rolls_back_all_on_conflict(world, invalid):
    extra, _ = extra_reviewer(world)
    _, participant = feedback_world(world)
    body = payload(world, participant, [world.users["bob"], extra])
    if invalid == "wrong_relationship":
        body["reviewer_ids"][-1] = world.users["manager"]
    elif invalid == "inactive":
        with Session(world.engine) as session, session.begin():
            session.get(User, UUID(extra)).is_active = False
    elif invalid == "duplicate":
        body["reviewer_ids"] = [extra, extra]
    elif invalid == "past_due":
        body["due_at"] = "2020-01-01T00:00:00Z"
    elif invalid == "stale":
        body["expected_evidence_version"] = 1
    before = snapshot(world)
    response = world.client().post("/api/v1/feedback-assignments/bulk", json=body)
    assert response.status_code == (422 if invalid == "duplicate" else 409), response.text
    assert snapshot(world) == before
    with Session(world.engine) as session:
        assert (
            session.get(CycleParticipant, UUID(participant["id"])).evidence_version
            == participant["evidence_version"]
        )


def test_batch_late_delivery_failure_rolls_back_assignments_audits_and_notices(world, monkeypatch):
    extra, _ = extra_reviewer(world)
    _, participant = feedback_world(world)
    before = snapshot(world)
    original = FeedbackService.audit
    calls = []

    def fail_late(self, *args, **kwargs):
        original(self, *args, **kwargs)
        calls.append(True)
        if len(calls) == 2:
            raise RuntimeError("Late batch failure")

    monkeypatch.setattr(FeedbackService, "audit", fail_late)
    result = world.client().post(
        "/api/v1/feedback-assignments/bulk",
        json=payload(world, participant, [world.users["bob"], extra]),
    )
    assert result.status_code == 500 and len(calls) == 2
    assert snapshot(world) == before


@pytest.mark.parametrize("role", ["admin", "manager", "alice"])
def test_only_hr_can_batch_assign(world, role):
    _, participant = feedback_world(world)
    assert (
        world.client(role)
        .post(
            "/api/v1/feedback-assignments/bulk",
            json=payload(world, participant, [world.users["bob"]]),
        )
        .status_code
        == 403
    )


@pytest.mark.parametrize("protection", ["csrf", "origin"])
def test_bulk_write_keeps_origin_and_csrf_checks(world, protection):
    _, participant = feedback_world(world)
    client = world.client()
    client.headers["X-CSRF-Token" if protection == "csrf" else "Origin"] = "invalid"
    assert (
        client.post(
            "/api/v1/feedback-assignments/bulk",
            json=payload(world, participant, [world.users["bob"]]),
        ).status_code
        == 403
    )


def test_concurrent_batches_do_not_duplicate_or_partially_assign(world):
    extra, _ = extra_reviewer(world)
    _, participant = feedback_world(world)
    body = payload(world, participant, [world.users["bob"], extra])

    def send(_):
        return world.client().post("/api/v1/feedback-assignments/bulk", json=body).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(send, range(2)))
    assert sorted(statuses) == [201, 409]
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(FeedbackAssignment)) == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"relationship": "SELF"},
        {"relationship": "MANAGER"},
        {"reviewer_ids": []},
        {"reviewer_ids": ["invalid"] * 101},
    ],
)
def test_batch_limits_and_relationships_are_explicit(world, changes):
    _, participant = feedback_world(world)
    assert (
        world.client()
        .post(
            "/api/v1/feedback-assignments/bulk",
            json=payload(world, participant, [world.users["bob"]], **changes),
        )
        .status_code
        == 422
    )


def test_existing_cancelled_assignment_is_not_silently_recreated_by_batch(world):
    _, participant = feedback_world(world)
    row = create_assignment(world, participant, "bob", "PEER", required=False).json()
    cancelled = world.client().request(
        "DELETE",
        f"/api/v1/feedback-assignments/{row['id']}",
        json={
            "expected_assignment_version": row["version"],
            "expected_evidence_version": row["evidence_version"],
            "reason_code": "WRONG_SELECTION",
        },
    )
    assert cancelled.status_code == 200
    body = payload(
        world,
        participant,
        [world.users["bob"]],
        expected_evidence_version=cancelled.json()["evidence_version"],
    )
    assert (
        world.client().post("/api/v1/feedback-assignments/bulk", json=body).json()["error"]["code"]
        == "assignment_already_exists"
    )


@pytest.mark.parametrize("state", ["CLOSED", "FINALIZED"])
def test_batch_cannot_write_closed_or_finalized_evidence(world, state):
    _, participant = feedback_world(world)
    with Session(world.engine) as session, session.begin():
        row = session.get(CycleParticipant, UUID(participant["id"]))
        if state == "FINALIZED":
            row.finalized_at = datetime.now(UTC)
        else:
            session.get(ReviewCycle, row.cycle_id).status = "CLOSED"
    before = snapshot(world)
    response = world.client().post(
        "/api/v1/feedback-assignments/bulk",
        json=payload(world, participant, [world.users["bob"]]),
    )
    assert response.status_code == 409
    assert snapshot(world) == before


def test_batch_capacity_counts_existing_assignments_and_preserves_all_on_overflow(world):
    extra, _ = extra_reviewer(world)
    _, participant = feedback_world(world)
    with Session(world.engine) as session, session.begin():
        template = session.get(User, UUID(world.users["bob"]))
        for index in range(99):
            user = User(
                email=f"batch-capacity-{index}@example.com",
                password_hash=template.password_hash,
                role=UserRole.EMPLOYEE,
            )
            session.add(user)
            session.flush()
            session.add(
                FeedbackAssignment(
                    participant_id=UUID(participant["id"]),
                    reviewer_id=user.id,
                    reviewer_employee_id=UUID(world.employees["bob"]),
                    relationship="PEER",
                    required=False,
                    eligibility_snapshot={"schema_version": 1},
                )
            )
    context = (
        world.client()
        .get("/api/v1/feedback-context", params={"participant_id": participant["id"]})
        .json()
    )
    assert context["active_assignment_count"] == 99
    before = snapshot(world)
    response = world.client().post(
        "/api/v1/feedback-assignments/bulk",
        json=payload(world, participant, [world.users["bob"], extra]),
    )
    assert (
        response.status_code == 409
        and response.json()["error"]["code"] == "assignment_limit_reached"
    )
    assert snapshot(world) == before
