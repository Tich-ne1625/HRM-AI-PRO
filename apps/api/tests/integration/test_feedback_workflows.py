from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit.service import AuditWriter

from .test_review_cycles import activate, draft, enroll


def feedback_world(world):
    cycle = activate(world, enroll(world, draft(world), "alice"))
    participant = (
        world.client().get(f"/api/v1/review-cycles/{cycle['id']}/participants").json()["items"][0]
    )
    return cycle, participant


def create_assignment(world, participant, reviewer="alice", relationship="SELF", **changes):
    return world.client().post(
        "/api/v1/feedback-assignments",
        json={
            "participant_id": participant["id"],
            "reviewer_id": world.users[reviewer],
            "relationship": relationship,
            "required": True,
            "expected_evidence_version": participant["evidence_version"],
            **changes,
        },
    )


def versions(row):
    return {
        "expected_assignment_version": row["version"],
        "expected_evidence_version": row["evidence_version"],
    }


def submit(world, row, reviewer="alice", **changes):
    return world.client(reviewer).post(
        "/api/v1/feedback",
        json={
            "assignment_id": row["id"],
            **versions(row),
            "rating": 4,
            "comment": "Helpful <script>plain text</script>",
            **changes,
        },
    )


def test_assignment_submission_replay_and_filtered_summary(world):
    cycle, participant = feedback_world(world)
    created = create_assignment(world, participant)
    assert created.status_code == 201, created.text
    row = created.json()
    assert row["evidence_version"] == 3 and row["version"] == 1
    mine = world.client("alice").get("/api/v1/feedback-assignments").json()
    assert mine["total"] == 1
    assert "reviewer_id" not in mine["items"][0]
    assert world.client("other").get("/api/v1/feedback-assignments").json()["total"] == 0
    assert world.client("other").get(f"/api/v1/feedback-assignments/{row['id']}").status_code == 404
    assert (
        world.client("admin").get("/api/v1/feedback-assignments?view=administration").status_code
        == 403
    )
    assert submit(world, row, "hr").status_code == 404
    result = submit(world, row)
    assert result.status_code == 201, result.text
    assert result.json()["status"] == "SUBMITTED"
    assert result.json()["evidence_version"] == 4
    assert submit(world, row).json()["error"]["code"] == "feedback_already_submitted"
    path = f"/api/v1/employees/{world.employees['alice']}/feedback?cycle_id={cycle['id']}"
    summary = world.client("manager").get(path)
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["count"] == 1 and body["mean"] == "4.00" and not body["ready"]
    assert body["own_submission"] is None
    assert "comment" not in str(body) and "reviewer_id" not in str(body)
    hidden = [g for g in body["groups"] if g["relationship"] in ("PEER", "SUBORDINATE")]
    assert all(
        g == {"relationship": g["relationship"], "suppressed": True, "count": None, "mean": None}
        for g in hidden
    )
    assert world.client("alice").get(path).json()["own_submission"]["rating"] == 4
    assert world.client("other").get(path).status_code == 404
    assert world.client("admin").get(path).status_code == 403


def test_historical_manager_keeps_inbox_after_transfer_and_unlink(world):
    from app.models import Employee

    cycle, participant = feedback_world(world)
    row = create_assignment(world, participant, "manager", "MANAGER").json()
    with Session(world.engine) as session, session.begin():
        session.get(Employee, UUID(world.employees["alice"])).manager_id = UUID(
            world.employees["other"]
        )
        session.get(Employee, UUID(world.employees["manager"])).user_id = None
    path = f"/api/v1/employees/{world.employees['alice']}/feedback?cycle_id={cycle['id']}"
    assert world.client("manager").get(path).status_code == 404
    assert world.client("other").get(path).status_code == 200
    assert world.client("other").get(f"/api/v1/feedback-assignments/{row['id']}").status_code == 404
    assert submit(world, row, "manager").status_code == 201


def test_optional_cancel_reopen_retains_identity_and_stale_form_is_rejected(world):
    _, participant = feedback_world(world)
    row = create_assignment(world, participant, "bob", "PEER", required=False).json()
    path = f"/api/v1/feedback-assignments/{row['id']}"
    cancelled = world.client().request(
        "DELETE", path, json={**versions(row), "reason_code": "WRONG_SELECTION"}
    )
    assert cancelled.status_code == 200, cancelled.text
    old = cancelled.json()
    duplicate = create_assignment(
        world,
        {**participant, "evidence_version": old["evidence_version"]},
        "bob",
        "PEER",
        required=False,
    )
    assert duplicate.json()["error"]["code"] == "assignment_already_exists"
    assert (
        world.client().patch(path, json={**versions(old), "due_at": None}).json()["error"]["code"]
        == "assignment_not_open"
    )
    reopened = world.client().patch(path, json={**versions(old), "status": "OPEN"})
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["id"] == row["id"] and reopened.json()["version"] == 3
    assert submit(world, row, "bob").json()["error"]["code"] == "stale_assignment_version"
    assert submit(world, reopened.json(), "bob").status_code == 201


def test_required_cancellation_and_mandatory_downgrade_are_blocked(world):
    _, participant = feedback_world(world)
    row = create_assignment(world, participant).json()
    path = f"/api/v1/feedback-assignments/{row['id']}"
    assert (
        world.client()
        .request("DELETE", path, json={**versions(row), "reason_code": "NO_LONGER_REQUIRED"})
        .json()["error"]["code"]
        == "required_coverage_conflict"
    )
    assert (
        world.client()
        .patch(path, json={**versions(row), "required": False})
        .json()["error"]["code"]
        == "required_coverage_conflict"
    )


@pytest.mark.parametrize("operation", ["submit", "cancel", "reopen", "replace", "update"])
def test_audit_failure_rolls_back_all_rows_and_versions(world, monkeypatch, operation):
    from app.models import CycleParticipant
    from app.modules.feedback.models import Feedback, FeedbackAssignment

    _, participant = feedback_world(world)
    row = create_assignment(world, participant, "bob", "PEER", required=False).json()
    path = f"/api/v1/feedback-assignments/{row['id']}"
    if operation == "reopen":
        row = (
            world.client()
            .request("DELETE", path, json={**versions(row), "reason_code": "WRONG_SELECTION"})
            .json()
        )

    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(AuditWriter, "record", fail)
    if operation == "submit":
        response = submit(world, row, "bob")
    elif operation == "cancel":
        response = world.client().request(
            "DELETE", path, json={**versions(row), "reason_code": "WRONG_SELECTION"}
        )
    elif operation == "reopen":
        response = world.client().patch(path, json={**versions(row), "status": "OPEN"})
    elif operation == "update":
        response = world.client().patch(path, json={**versions(row), "required": True})
    else:
        response = world.client().post(
            path + "/replace",
            json={
                **versions(row),
                "reviewer_id": world.users["other"],
                "reason_code": "REVIEWER_UNAVAILABLE",
            },
        )
    assert response.status_code == 500, response.text
    with Session(world.engine) as session:
        assert (
            session.get(CycleParticipant, UUID(participant["id"])).evidence_version
            == row["evidence_version"]
        )
        saved = session.get(FeedbackAssignment, UUID(row["id"]))
        assert saved.status == row["status"] and saved.version == row["version"]
        assert session.scalar(select(func.count()).select_from(Feedback)) == 0
        assert session.scalar(select(func.count()).select_from(FeedbackAssignment)) == 1


def test_expired_deadline_can_be_extended_but_not_submitted(world):
    from app.modules.feedback.models import FeedbackAssignment

    _, participant = feedback_world(world)
    row = create_assignment(world, participant).json()
    with Session(world.engine) as session, session.begin():
        session.get(FeedbackAssignment, UUID(row["id"])).due_at = datetime.now(UTC) - timedelta(
            seconds=1
        )
    assert submit(world, row).json()["error"]["code"] == "deadline_passed"
    extended = world.client().patch(
        f"/api/v1/feedback-assignments/{row['id']}",
        json={**versions(row), "due_at": (datetime.now(UTC) + timedelta(days=1)).isoformat()},
    )
    assert extended.status_code == 200, extended.text
    assert submit(world, extended.json()).status_code == 201


def test_ineligible_and_disabled_historical_reviewer_no_implicit_delegation(world):
    from app.models import User

    _, participant = feedback_world(world)
    with Session(world.engine) as session, session.begin():
        session.get(User, UUID(world.users["manager"])).is_active = False
    assert (
        create_assignment(world, participant, "manager", "MANAGER").json()["error"]["code"]
        == "reviewer_inactive"
    )
    assert (
        create_assignment(world, participant, "other", "MANAGER").json()["error"]["code"]
        == "reviewer_ineligible"
    )
    assert create_assignment(world, participant, "manager", "PEER").status_code == 409
    assert create_assignment(world, participant, "indirect", "SUBORDINATE").status_code == 201


def test_mutations_require_origin_csrf_and_unknown_uuid_hides_existence(world):
    _, participant = feedback_world(world)
    row = create_assignment(world, participant).json()
    client = world.client("alice")
    assert (
        client.post(
            "/api/v1/feedback",
            headers={"Origin": "http://evil.test"},
            json={"assignment_id": row["id"], **versions(row), "rating": 4},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/feedback",
            headers={"X-CSRF-Token": "wrong"},
            json={"assignment_id": row["id"], **versions(row), "rating": 4},
        ).status_code
        == 403
    )
    assert client.get(f"/api/v1/feedback-assignments/{uuid4()}").status_code == 404


def test_assignment_creation_audit_failure_leaves_no_row_or_version_change(world, monkeypatch):
    from app.models import CycleParticipant
    from app.modules.feedback.models import FeedbackAssignment

    _, participant = feedback_world(world)

    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(AuditWriter, "record", fail)
    assert create_assignment(world, participant).status_code == 500
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(FeedbackAssignment)) == 0
        assert session.get(CycleParticipant, UUID(participant["id"])).evidence_version == 2
