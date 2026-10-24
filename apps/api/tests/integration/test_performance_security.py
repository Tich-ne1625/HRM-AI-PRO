from uuid import UUID

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AuditLog, CycleParticipant, EmployeeKPI, ReviewCycle
from app.modules.performance.models import PerformanceReview, PerformanceReviewRevision

from .test_feedback_workflows import submit
from .test_performance import calculate, finalize_body, ready_world


@pytest.mark.parametrize("operation", ["calculate", "finalize", "close"])
@pytest.mark.parametrize("protection", ["origin", "csrf"])
def test_performance_mutations_require_origin_and_csrf(world, operation, protection):
    cycle, participant, _, base = ready_world(world)
    report = calculate(world, cycle, participant, base).json()
    if operation == "calculate":
        path, body = (
            base + "/calculate",
            {"cycle_id": cycle["id"], "expected_evidence_version": participant["evidence_version"]},
        )
    elif operation == "finalize":
        path, body = f"/api/v1/reviews/{report['review_id']}/finalize", finalize_body(report)
    else:
        path, body = (
            f"/api/v1/review-cycles/{cycle['id']}/close",
            {"expected_version": cycle["version"]},
        )
    client = world.client()
    if protection == "origin":
        client.headers["Origin"] = "https://untrusted.example"
    else:
        client.headers["X-CSRF-Token"] = "invalid"
    assert client.post(path, json=body).status_code == 403
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(PerformanceReviewRevision)) == 1
        assert session.get(CycleParticipant, UUID(participant["id"])).finalized_at is None


@pytest.mark.parametrize("operation", ["finalize", "close"])
@pytest.mark.parametrize("role", ["admin", "manager", "alice"])
def test_hr_only_lifecycle(world, operation, role):
    cycle, participant, _, base = ready_world(world)
    report = calculate(world, cycle, participant, base).json()
    path = (
        f"/api/v1/reviews/{report['review_id']}/finalize"
        if operation == "finalize"
        else f"/api/v1/review-cycles/{cycle['id']}/close"
    )
    body = (
        finalize_body(report) if operation == "finalize" else {"expected_version": cycle["version"]}
    )
    assert world.client(role).post(path, json=body).status_code == 403


def test_new_feedback_stales_report_and_revision_never_includes_later_own_comment(world):
    cycle, participant, _, base = ready_world(world, optional=True)
    report = calculate(world, cycle, participant, base).json()
    assignment = world.client("bob").get("/api/v1/feedback-assignments").json()["items"][0]
    assert submit(world, assignment, "bob", rating=1, comment="Later feedback").status_code == 201
    stale = world.client().get(base + f"?cycle_id={cycle['id']}").json()
    assert stale["state"] == "STALE"
    body = finalize_body(report)
    body["expected_evidence_version"] += 1
    assert (
        world.client()
        .post(f"/api/v1/reviews/{report['review_id']}/finalize", json=body)
        .json()["error"]["code"]
        == "review_stale"
    )
    participant["evidence_version"] += 1
    report = calculate(world, cycle, participant, base).json()
    assert report["current_result"]["feedback_score"] == "60.00"
    assert all(
        g["count"] is None
        for g in report["current_result"]["feedback"]["groups"]
        if g["relationship"] == "PEER"
    )


def test_finalization_blocks_optional_submission_without_cancelling_history(world):
    from app.modules.feedback.models import AssignmentStatus, FeedbackAssignment

    cycle, participant, _, base = ready_world(world, optional=True)
    report = calculate(world, cycle, participant, base).json()
    assignment = world.client("bob").get("/api/v1/feedback-assignments").json()["items"][0]
    assert (
        world.client()
        .post(f"/api/v1/reviews/{report['review_id']}/finalize", json=finalize_body(report, 1))
        .status_code
        == 200
    )
    assert submit(world, assignment, "bob").json()["error"]["code"] == "participant_finalized"
    with Session(world.engine) as session:
        assert (
            session.get(FeedbackAssignment, UUID(assignment["id"])).status == AssignmentStatus.OPEN
        )
        review = session.get(PerformanceReview, UUID(report["review_id"]))
        assert (
            review.finalized_at
            == session.get(CycleParticipant, UUID(participant["id"])).finalized_at
        )
        assert review.evidence_version == participant["evidence_version"]
        assert session.scalar(select(func.count()).select_from(PerformanceReviewRevision)) == 1


@pytest.mark.parametrize(
    "corruption",
    ["missing_feedback", "bad_policy", "bad_snapshot", "missing_actual", "wrong_weight"],
)
def test_corrupt_or_incomplete_inputs_never_create_scores(world, corruption):
    cycle, participant, item, base = ready_world(world)
    with Session(world.engine) as session, session.begin():
        if corruption == "missing_feedback":
            session.execute(
                text(
                    "DELETE FROM feedback WHERE assignment_id IN "
                    "(SELECT id FROM feedback_assignments WHERE participant_id=:id)"
                ),
                {"id": participant["id"]},
            )
        elif corruption == "bad_policy":
            session.get(ReviewCycle, UUID(cycle["id"])).scoring_policy_snapshot = {
                "schema_version": 99
            }
        elif corruption == "bad_snapshot":
            session.get(EmployeeKPI, UUID(item["id"])).definition_snapshot = {"schema_version": 99}
        elif corruption == "missing_actual":
            session.get(EmployeeKPI, UUID(item["id"])).actual = None
        else:
            session.get(EmployeeKPI, UUID(item["id"])).weight = 99
    assert calculate(world, cycle, participant, base).status_code == 409
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(PerformanceReview)) == 0
        assert session.scalar(select(func.count()).select_from(PerformanceReviewRevision)) == 0


def test_scores_and_evidence_never_enter_audit_metadata(world):
    cycle, participant, _, base = ready_world(world)
    report = calculate(world, cycle, participant, base).json()
    assert calculate(world, cycle, participant, base).json()["reused"]
    world.client().post(
        f"/api/v1/reviews/{report['review_id']}/finalize", json=finalize_body(report)
    )
    with Session(world.engine) as session:
        rows = list(session.scalars(select(AuditLog).where(AuditLog.action.like("performance.%"))))
        assert sorted(r.action for r in rows) == ["performance.calculated", "performance.finalized"]
        assert all(
            set(r.metadata_)
            == {
                "participant_id",
                "cycle_id",
                "calculation_version",
                "evidence_version",
                "engine_version",
                "evidence_hash",
            }
            for r in rows
        )
        snapshot = session.get(PerformanceReview, UUID(report["review_id"])).evidence_snapshot
        for field in ("comment", "email", "manager_id", "direct_reports"):
            assert field not in str(snapshot)


@pytest.mark.parametrize(
    "clause",
    [
        "calculation_version=0",
        "evidence_version=0",
        "kpi_score=-1",
        "feedback_score='NaN'::numeric",
        "evidence_hash='x'",
        "evidence_snapshot='[]'::jsonb",
        "engine_version='x'",
    ],
)
def test_score_constraints_on_both_tables(world, clause):
    cycle, participant, _, base = ready_world(world)
    calculate(world, cycle, participant, base)
    for table in ("performance_reviews", "performance_review_revisions"):
        with pytest.raises(IntegrityError), world.engine.begin() as connection:
            connection.execute(text(f"UPDATE {table} SET {clause}"))


def test_revision_uniqueness_foreign_keys_and_migration_roundtrip(world):
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    from alembic import command

    from .conftest import ALEMBIC_INI

    cycle, participant, _, base = ready_world(world)
    report = calculate(world, cycle, participant, base).json()
    with pytest.raises(IntegrityError), world.engine.begin() as connection:
        connection.execute(
            text("DELETE FROM cycle_participants WHERE id=:id"), {"id": participant["id"]}
        )
    with Session(world.engine) as session:
        row = session.scalar(select(PerformanceReviewRevision))
        values = {
            column.name: getattr(row, column.name)
            for column in row.__table__.columns
            if column.name != "id"
        }
    with pytest.raises(IntegrityError), Session(world.engine) as session, session.begin():
        session.add(PerformanceReviewRevision(**values))
    config = Config(str(ALEMBIC_INI))
    assert ScriptDirectory.from_config(config).get_heads() == ["20261024_0008"]
    command.check(config)
    command.downgrade(config, "20261020_0005")
    command.upgrade(config, "head")
    with Session(world.engine) as session:
        assert session.get(CycleParticipant, UUID(participant["id"])) is not None
        assert session.scalar(select(func.count()).select_from(PerformanceReview)) == 0
    assert report["review_id"]


def test_manager_can_read_but_cannot_calculate_own_review(world):
    from app.models import User

    cycle, participant, _, base = ready_world(world)
    with Session(world.engine) as session, session.begin():
        session.get(User, UUID(world.users["alice"])).role = "MANAGER"
    assert world.client("alice").get(base + f"?cycle_id={cycle['id']}").status_code == 200
    assert calculate(world, cycle, participant, base, "alice").status_code == 403


@pytest.mark.parametrize("recalculate", [False, True])
def test_revision_database_error_rolls_back_header_and_audit(world, monkeypatch, recalculate):
    cycle, participant, item, base = ready_world(world)
    if recalculate:
        calculate(world, cycle, participant, base)
        world.client().patch(
            f"/api/v1/employee-kpis/{item['id']}",
            json={
                "expected_evidence_version": participant["evidence_version"],
                "actual": "12.0000",
            },
        )
        participant["evidence_version"] += 1
    original = Session.add

    def corrupt_revision(self, instance, *args, **kwargs):
        if isinstance(instance, PerformanceReviewRevision):
            instance.evidence_version = 0
        return original(self, instance, *args, **kwargs)

    monkeypatch.setattr(Session, "add", corrupt_revision)
    assert calculate(world, cycle, participant, base).status_code == 500
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(PerformanceReviewRevision)) == int(
            recalculate
        )
        assert session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action == "performance.calculated")
        ) == int(recalculate)
        row = session.scalar(select(PerformanceReview))
        if recalculate:
            assert row.calculation_version == 1 and str(row.final_score) == "87.00"
        else:
            assert row is None


def test_calculation_uses_frozen_policy_and_definition_after_live_edits(world):
    cycle, participant, item, base = ready_world(world)
    assert (
        world.client("admin")
        .patch(
            "/api/v1/settings/scoring",
            json={"expected_version": 1, "policy": {"kpi_cap": "150.00"}},
        )
        .status_code
        == 200
    )
    assert (
        world.client()
        .patch(
            f"/api/v1/kpis/{item['definition_id']}",
            json={"expected_version": 1, "name": "New catalog label"},
        )
        .status_code
        == 200
    )
    assert (
        world.client()
        .patch(
            f"/api/v1/employee-kpis/{item['id']}",
            json={
                "expected_evidence_version": participant["evidence_version"],
                "actual": "130.0000",
            },
        )
        .status_code
        == 200
    )
    participant["evidence_version"] += 1
    response = calculate(world, cycle, participant, base)
    assert response.status_code == 201, response.text
    result = response.json()["current_result"]
    assert result["kpi_score"] == "100.00" and result["final_score"] == "94.00"
    assert result["policy"]["kpi_cap"] == "100.00"
    assert result["items"][0]["name"] == "Sales"
