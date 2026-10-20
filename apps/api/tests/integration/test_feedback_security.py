from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditLog, CycleParticipant, Employee, ReviewCycle, User
from app.modules.feedback.models import FeedbackAssignment

from .test_feedback_workflows import create_assignment, feedback_world, submit, versions


@pytest.mark.parametrize("change", ["unlink", "role_admin", "role_hr", "inactive_employment"])
def test_assigned_principal_survives_profile_or_role_changes(world, change):
    _, participant = feedback_world(world)
    row = create_assignment(world, participant).json()
    with Session(world.engine) as session, session.begin():
        employee = session.get(Employee, UUID(world.employees["alice"]))
        if change == "unlink":
            employee.user_id = None
        elif change == "inactive_employment":
            employee.employment_status = "INACTIVE"
        else:
            session.get(User, UUID(world.users["alice"])).role = (
                "ADMIN" if change == "role_admin" else "HR"
            )
    result = submit(world, row)
    assert result.status_code == 201, result.text
    assert "reviewer_id" not in result.json()


@pytest.mark.parametrize("state", ["DRAFT", "CLOSED", "FINALIZED"])
def test_lifecycle_blocks_submission_and_assignment_mutations(world, state):
    _, participant = feedback_world(world)
    row = create_assignment(world, participant).json()
    with Session(world.engine) as session, session.begin():
        participant_model = session.get(CycleParticipant, UUID(participant["id"]))
        if state == "FINALIZED":
            participant_model.finalized_at = datetime.now(UTC)
        else:
            cycle = session.get(ReviewCycle, participant_model.cycle_id)
            cycle.status = state
            if state == "DRAFT":
                cycle.scoring_policy_snapshot = None
                cycle.policy_source_version = None
                cycle.activated_at = None
    assert submit(world, row).status_code == 409
    response = world.client().patch(
        f"/api/v1/feedback-assignments/{row['id']}", json={**versions(row), "due_at": None}
    )
    assert response.status_code == 409


def test_noop_preserves_versions_and_audit_but_rejects_stale(world):
    _, participant = feedback_world(world)
    row = create_assignment(world, participant).json()
    path = f"/api/v1/feedback-assignments/{row['id']}"
    with Session(world.engine) as session:
        before = session.scalar(select(func.count()).select_from(AuditLog))
    saved = world.client().patch(path, json={**versions(row), "due_at": None, "required": True})
    assert saved.status_code == 200 and saved.json()["version"] == row["version"]
    assert saved.json()["evidence_version"] == row["evidence_version"]
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(AuditLog)) == before
    assert (
        world.client()
        .patch(path, json={**versions(row), "expected_evidence_version": 1, "due_at": None})
        .status_code
        == 409
    )


def test_replacement_can_reopen_cancelled_candidate_preserving_required_and_snapshot(world):
    _, participant = feedback_world(world)
    old = create_assignment(world, participant, "bob", "PEER").json()
    candidate = create_assignment(
        world,
        {**participant, "evidence_version": old["evidence_version"]},
        "other",
        "PEER",
        required=False,
    ).json()
    cancelled = (
        world.client()
        .request(
            "DELETE",
            f"/api/v1/feedback-assignments/{candidate['id']}",
            json={**versions(candidate), "reason_code": "WRONG_SELECTION"},
        )
        .json()
    )
    old = world.client().get(f"/api/v1/feedback-assignments/{old['id']}").json()
    with Session(world.engine) as session:
        original = dict(session.get(FeedbackAssignment, UUID(candidate["id"])).eligibility_snapshot)
    replaced = world.client().post(
        f"/api/v1/feedback-assignments/{old['id']}/replace",
        json={
            **versions(old),
            "reviewer_id": world.users["other"],
            "reason_code": "REVIEWER_UNAVAILABLE",
        },
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["id"] == candidate["id"] and replaced.json()["required"]
    assert replaced.json()["version"] == cancelled["version"] + 1
    assert replaced.json()["evidence_version"] == old["evidence_version"] + 1
    with Session(world.engine) as session:
        assert (
            session.get(FeedbackAssignment, UUID(candidate["id"])).eligibility_snapshot == original
        )
        assert session.get(FeedbackAssignment, UUID(old["id"])).status == "CANCELLED"


def test_reopen_rejects_peer_relinked_to_different_employee(world):
    _, participant = feedback_world(world)
    row = create_assignment(world, participant, "bob", "PEER", required=False).json()
    path = f"/api/v1/feedback-assignments/{row['id']}"
    row = (
        world.client()
        .request("DELETE", path, json={**versions(row), "reason_code": "WRONG_SELECTION"})
        .json()
    )
    with Session(world.engine) as session, session.begin():
        session.get(Employee, UUID(world.employees["bob"])).user_id = None
        session.get(Employee, UUID(world.employees["other"])).user_id = UUID(world.users["bob"])
    assert (
        world.client().patch(path, json={**versions(row), "status": "OPEN"}).json()["error"]["code"]
        == "reviewer_ineligible"
    )


def test_list_count_filters_do_not_bypass_owner_scope(world):
    cycle, participant = feedback_world(world)
    row = create_assignment(world, participant).json()
    assert (
        world.client("bob")
        .get(
            f"/api/v1/feedback-assignments?participant_id={participant['id']}&cycle_id={cycle['id']}"
        )
        .json()["total"]
        == 0
    )
    assert (
        world.client("alice").get("/api/v1/feedback-assignments?status=CANCELLED").json()["total"]
        == 0
    )
    assert (
        world.client("alice").get("/api/v1/feedback-assignments?sort=created_at").json()["total"]
        == 1
    )
    assert world.client("alice").get("/api/v1/feedback-assignments?sort=rating").status_code == 422
    assert (
        world.client("alice").get("/api/v1/feedback-assignments?page_size=101").status_code == 422
    )
    assert (
        world.client("alice").get("/api/v1/feedback-assignments?view=administration").status_code
        == 403
    )
    assert world.client("bob").get(f"/api/v1/feedback-assignments/{row['id']}").status_code == 404


def test_creation_rejects_past_deadline_without_increment(world):
    _, participant = feedback_world(world)
    response = create_assignment(
        world, participant, due_at=(datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    )
    assert response.json()["error"]["code"] == "deadline_passed"
    with Session(world.engine) as session:
        assert session.get(CycleParticipant, UUID(participant["id"])).evidence_version == 2


def test_assignment_capacity_enforced_before_new_or_reopened_assignment(world):
    from uuid import uuid4

    _, participant = feedback_world(world)
    cancelled = create_assignment(world, participant, "bob", "PEER", required=False).json()
    cancelled = (
        world.client()
        .request(
            "DELETE",
            f"/api/v1/feedback-assignments/{cancelled['id']}",
            json={**versions(cancelled), "reason_code": "WRONG_SELECTION"},
        )
        .json()
    )
    # Seed the upper boundary directly; the HTTP paths must not bypass it.
    with Session(world.engine) as session, session.begin():
        template = session.get(User, UUID(world.users["bob"]))
        for index in range(100):
            reviewer = User(
                id=uuid4(),
                email=f"capacity-{index}@example.com",
                password_hash=template.password_hash,
                role="EMPLOYEE",
            )
            session.add(reviewer)
            session.flush()
            session.add(
                FeedbackAssignment(
                    participant_id=UUID(participant["id"]),
                    reviewer_id=reviewer.id,
                    reviewer_employee_id=UUID(world.employees["bob"]),
                    relationship="PEER",
                    required=False,
                    eligibility_snapshot={"schema_version": 1},
                )
            )
    result = create_assignment(
        world, {**participant, "evidence_version": cancelled["evidence_version"]}
    )
    assert result.json()["error"]["code"] == "assignment_limit_reached"
    reopened = world.client().patch(
        f"/api/v1/feedback-assignments/{cancelled['id']}",
        json={**versions(cancelled), "status": "OPEN"},
    )
    assert reopened.json()["error"]["code"] == "assignment_limit_reached"
