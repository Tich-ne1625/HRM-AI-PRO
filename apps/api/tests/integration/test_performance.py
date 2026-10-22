from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit.service import AuditWriter
from app.modules.performance.models import PerformanceReview, PerformanceReviewRevision

from .test_employee_kpis import replace_body
from .test_feedback_workflows import create_assignment, feedback_world, submit
from .test_kpi_definitions import definition


def ready_world(world, *, optional=False):
    cycle, participant = feedback_world(world)
    first = world.client().post("/api/v1/kpis", json=definition()).json()
    kpis = f"/api/v1/employees/{world.employees['alice']}/kpis?cycle_id={cycle['id']}"
    allocation = world.client().put(kpis, json=replace_body(first)).json()
    item = allocation["items"][0]
    actual = world.client().patch(
        f"/api/v1/employee-kpis/{item['id']}",
        json={"expected_evidence_version": 3, "actual": "90.0000"},
    )
    assert actual.status_code == 200, actual.text
    participant["evidence_version"] = 4
    for reviewer, relationship in (("alice", "SELF"), ("manager", "MANAGER")):
        created = create_assignment(world, participant, reviewer, relationship)
        assert created.status_code == 201, created.text
        result = submit(world, created.json(), reviewer)
        assert result.status_code == 201, result.text
        participant["evidence_version"] = result.json()["evidence_version"]
    if optional:
        result = create_assignment(world, participant, "bob", "PEER", required=False)
        assert result.status_code == 201, result.text
        participant["evidence_version"] = result.json()["evidence_version"]
    base = f"/api/v1/performance/{world.employees['alice']}"
    return cycle, participant, item, base


def calculate(world, cycle, participant, base, role="hr"):
    return world.client(role).post(
        base + "/calculate",
        json={
            "cycle_id": cycle["id"],
            "expected_evidence_version": participant["evidence_version"],
        },
    )


def finalize_body(report, count=0):
    return {
        "expected_evidence_version": report["evidence_version"],
        "expected_calculation_version": report["current_result"]["calculation_version"],
        "acknowledge_open_optional_count": count,
    }


def test_calculation_reuse_stale_revision_and_safe_projection(world):
    cycle, participant, item, base = ready_world(world)
    path = base + f"?cycle_id={cycle['id']}"
    assert world.client().get(path).json()["state"] == "NOT_CALCULATED"
    response = calculate(world, cycle, participant, base, "manager")
    assert response.status_code == 201, response.text
    report = response.json()
    assert (
        report["state"] == "CURRENT"
        and report["evidence_version"] == participant["evidence_version"]
    )
    assert report["current_result"]["final_score"] == "87.00"
    assert report["current_result"]["feedback"]["own_submission"]["rating"] == 4
    assert response.headers["cache-control"] == "no-store"
    assert calculate(world, cycle, participant, base).json()["reused"]
    public = world.client().get(path).json()
    assert public["current_result"]["feedback"]["own_submission"] is None
    for forbidden in (
        "reviewer_id",
        "evidence_snapshot",
        "evidence_hash",
        "pending_assignment_ids",
        "Helpful",
    ):
        assert forbidden not in str(public)
    changed = world.client().patch(
        f"/api/v1/employee-kpis/{item['id']}",
        json={"expected_evidence_version": participant["evidence_version"], "actual": "50.0000"},
    )
    assert changed.status_code == 200, changed.text
    stale = world.client().get(path).json()
    assert stale["state"] == "STALE" and stale["current_result"] is None
    assert stale["last_calculation"]["final_score"] == "87.00"
    assert (
        calculate(world, cycle, participant, base).json()["error"]["code"]
        == "stale_evidence_version"
    )
    participant["evidence_version"] += 1
    recalculated = calculate(world, cycle, participant, base)
    assert recalculated.status_code == 200, recalculated.text
    assert recalculated.json()["current_result"]["final_score"] == "59.00"
    revisions = f"/api/v1/reviews/{report['review_id']}/revisions"
    history = world.client("alice").get(revisions).json()
    assert history["total"] == 2 and [r["calculation_version"] for r in history["items"]] == [2, 1]
    assert world.client("alice").get(revisions + "/1").json()["final_score"] == "87.00"
    assert world.client().get(revisions + "/99").status_code == 404
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(PerformanceReview)) == 1
        assert session.scalar(select(func.count()).select_from(PerformanceReviewRevision)) == 2


def test_finalize_optional_ack_close_and_new_cycle(world):
    from .test_review_cycles import activate, draft, enroll

    cycle, participant, item, base = ready_world(world, optional=True)
    calculated = calculate(world, cycle, participant, base).json()
    review = f"/api/v1/reviews/{calculated['review_id']}"
    context = world.client().get(review + "/finalization-context").json()
    assert context["open_optional_count"] == 1 and context["readiness"]["ready"]
    assert world.client("manager").get(review + "/finalization-context").status_code == 403
    assert (
        world.client()
        .post(review + "/finalize", json=finalize_body(calculated))
        .json()["error"]["code"]
        == "optional_feedback_acknowledgement_required"
    )
    close_path = f"/api/v1/review-cycles/{cycle['id']}/close"
    assert (
        world.client()
        .post(close_path, json={"expected_version": cycle["version"]})
        .json()["error"]["code"]
        == "cycle_reviews_incomplete"
    )
    finalized = world.client().post(review + "/finalize", json=finalize_body(calculated, 1))
    assert finalized.status_code == 200, finalized.text
    report = finalized.json()
    assert report["state"] == "FINALIZED" and report["cycle_version"] == cycle["version"] + 1
    assert (
        world.client()
        .post(review + "/finalize", json=finalize_body(calculated, 1))
        .json()["error"]["code"]
        == "review_already_finalized"
    )
    assert (
        world.client()
        .patch(
            f"/api/v1/employee-kpis/{item['id']}",
            json={
                "expected_evidence_version": participant["evidence_version"],
                "actual": "99.0000",
            },
        )
        .json()["error"]["code"]
        == "participant_finalized"
    )
    assert (
        calculate(world, cycle, participant, base).json()["error"]["code"]
        == "participant_finalized"
    )
    assert (
        world.client()
        .post(close_path, json={"expected_version": cycle["version"]})
        .json()["error"]["code"]
        == "stale_version"
    )
    closed = world.client().post(close_path, json={"expected_version": report["cycle_version"]})
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "CLOSED"
    assert (
        world.client()
        .post(close_path, json={"expected_version": report["cycle_version"]})
        .json()["error"]["code"]
        == "cycle_already_closed"
    )
    assert (
        world.client("alice").get(base + f"?cycle_id={cycle['id']}").json()["state"] == "FINALIZED"
    )
    assert (
        activate(world, enroll(world, draft(world, name="Next cycle"), "alice"))["status"]
        == "ACTIVE"
    )


@pytest.mark.parametrize(
    "role,status",
    [
        ("admin", 403),
        ("other", 404),
        ("bob", 404),
        ("unlinked", 404),
        ("alice", 200),
        ("manager", 200),
        ("hr", 200),
    ],
)
def test_live_report_scope_and_revision_scope(world, role, status):
    cycle, participant, _, base = ready_world(world)
    report = calculate(world, cycle, participant, base).json()
    client = world.client(role)
    for path in (
        base + f"?cycle_id={cycle['id']}",
        base + f"/readiness?cycle_id={cycle['id']}",
        f"/api/v1/reviews/{report['review_id']}/revisions",
        f"/api/v1/reviews/{report['review_id']}/revisions/1",
    ):
        response = client.get(path)
        assert response.status_code == status, response.text
        if status == 200 and role != "hr":
            assert "pending_assignment_ids" not in response.text


def test_transfer_revokes_history_and_grants_current_manager(world):
    from app.models import Employee

    cycle, participant, _, base = ready_world(world)
    report = calculate(world, cycle, participant, base).json()
    with Session(world.engine) as session, session.begin():
        session.get(Employee, UUID(world.employees["alice"])).manager_id = UUID(
            world.employees["other"]
        )
    for suffix in ("", "/1"):
        path = f"/api/v1/reviews/{report['review_id']}/revisions" + suffix
        assert world.client("manager").get(path).status_code == 404
        assert world.client("other").get(path).status_code == 200
    assert calculate(world, cycle, participant, base, "manager").status_code == 404
    assert calculate(world, cycle, participant, base, "other").json()["reused"]


@pytest.mark.parametrize("operation", ["calculate", "recalculate", "finalize", "close"])
def test_performance_audit_failure_rolls_back_atomically(world, monkeypatch, operation):
    from app.models import CycleParticipant, ReviewCycle

    cycle, participant, item, base = ready_world(world)
    report = None
    if operation != "calculate":
        report = calculate(world, cycle, participant, base).json()
    if operation == "recalculate":
        world.client().patch(
            f"/api/v1/employee-kpis/{item['id']}",
            json={
                "expected_evidence_version": participant["evidence_version"],
                "actual": "12.0000",
            },
        )
        participant["evidence_version"] += 1
    if operation == "close":
        report = (
            world.client()
            .post(f"/api/v1/reviews/{report['review_id']}/finalize", json=finalize_body(report))
            .json()
        )

    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(AuditWriter, "record", fail)
    if operation in ("calculate", "recalculate"):
        response = calculate(world, cycle, participant, base)
    elif operation == "finalize":
        response = world.client().post(
            f"/api/v1/reviews/{report['review_id']}/finalize", json=finalize_body(report)
        )
    else:
        response = world.client().post(
            f"/api/v1/review-cycles/{cycle['id']}/close",
            json={"expected_version": report["cycle_version"]},
        )
    assert response.status_code == 500, response.text
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(PerformanceReviewRevision)) == (
            0 if operation == "calculate" else 1
        )
        stored = session.get(CycleParticipant, UUID(participant["id"]))
        assert (stored.finalized_at is not None) == (operation == "close")
        review = session.scalar(select(PerformanceReview))
        if review:
            assert review.calculation_version == 1 and str(review.final_score) == "87.00"
        assert session.get(ReviewCycle, UUID(cycle["id"])).status.value == "ACTIVE"


def test_incomplete_evidence_read_only_and_calculation_forbidden(world):
    cycle, participant = feedback_world(world)
    base = f"/api/v1/performance/{world.employees['alice']}"
    result = world.client().get(base + f"?cycle_id={cycle['id']}")
    assert result.status_code == 200, result.text
    assert not result.json()["readiness"]["ready"] and not result.json()["can_calculate"]
    assert (
        calculate(world, cycle, participant, base).json()["error"]["code"] == "evidence_incomplete"
    )
    assert calculate(world, cycle, participant, base, "alice").status_code == 403
    assert world.client().get(f"/api/v1/reviews/{uuid4()}/revisions").status_code == 404
