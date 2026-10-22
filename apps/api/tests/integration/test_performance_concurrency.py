from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.performance.models import PerformanceReviewRevision

from .test_feedback_workflows import submit
from .test_kpi_concurrency import race
from .test_performance import calculate, finalize_body, ready_world


def test_simultaneous_calculation_reuses_one_revision(world, monkeypatch):
    cycle, participant, _, base = ready_world(world)
    responses = race(
        monkeypatch,
        lambda: calculate(world, cycle, participant, base),
        lambda: calculate(world, cycle, participant, base, "manager"),
    )
    assert sorted(r.status_code for r in responses) == [200, 201]
    assert sum(r.json()["reused"] for r in responses) == 1
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(PerformanceReviewRevision)) == 1


def test_simultaneous_finalization_is_committed_once(world, monkeypatch):
    cycle, participant, _, base = ready_world(world)
    report = calculate(world, cycle, participant, base).json()
    path = f"/api/v1/reviews/{report['review_id']}/finalize"
    responses = race(
        monkeypatch,
        lambda: world.client().post(path, json=finalize_body(report)),
        lambda: world.client().post(path, json=finalize_body(report)),
    )
    assert sorted(r.status_code for r in responses) == [200, 409]
    assert (
        next(r for r in responses if r.status_code == 409).json()["error"]["code"]
        == "review_already_finalized"
    )


@pytest.mark.parametrize("mutation", ["actual", "submit", "allocation", "replacement"])
def test_finalize_competes_with_evidence_writer(world, monkeypatch, mutation):
    cycle, participant, item, base = ready_world(world, optional=True)
    report = calculate(world, cycle, participant, base).json()
    assignment = world.client("bob").get("/api/v1/feedback-assignments").json()["items"][0]

    def write():
        if mutation == "submit":
            return submit(world, assignment, "bob")
        if mutation == "allocation":
            return world.client().put(
                f"/api/v1/employees/{world.employees['alice']}/kpis?cycle_id={cycle['id']}",
                json={
                    "expected_evidence_version": participant["evidence_version"],
                    "items": [
                        {
                            "definition_id": item["definition_id"],
                            "target": "200.0000",
                            "weight": "100.00",
                        }
                    ],
                },
            )
        if mutation == "replacement":
            return world.client().post(
                f"/api/v1/feedback-assignments/{assignment['id']}/replace",
                json={
                    "expected_assignment_version": assignment["version"],
                    "expected_evidence_version": participant["evidence_version"],
                    "reviewer_id": world.users["other"],
                    "reason_code": "REVIEWER_UNAVAILABLE",
                    "due_at": None,
                },
            )
        return world.client().patch(
            f"/api/v1/employee-kpis/{item['id']}",
            json={
                "expected_evidence_version": participant["evidence_version"],
                "actual": "99.0000",
            },
        )

    responses = race(
        monkeypatch,
        lambda: world.client().post(
            f"/api/v1/reviews/{report['review_id']}/finalize", json=finalize_body(report, 1)
        ),
        write,
    )
    assert sorted(r.status_code for r in responses) in ([200, 409], [201, 409])
    current = world.client().get(base + f"?cycle_id={cycle['id']}").json()
    assert current["state"] in ("FINALIZED", "STALE")


def test_calculate_competes_with_kpi_change_without_lost_version(world, monkeypatch):
    cycle, participant, item, base = ready_world(world)
    responses = race(
        monkeypatch,
        lambda: calculate(world, cycle, participant, base),
        lambda: world.client().patch(
            f"/api/v1/employee-kpis/{item['id']}",
            json={
                "expected_evidence_version": participant["evidence_version"],
                "actual": "99.0000",
            },
        ),
    )
    assert sorted(r.status_code for r in responses) in ([200, 201], [200, 409])
    report = world.client().get(base + f"?cycle_id={cycle['id']}").json()
    assert report["evidence_version"] == participant["evidence_version"] + 1
    assert report["state"] in ("NOT_CALCULATED", "STALE")


def test_close_competes_with_last_finalize_and_requires_explicit_new_version(world, monkeypatch):
    cycle, participant, _, base = ready_world(world)
    report = calculate(world, cycle, participant, base).json()
    responses = race(
        monkeypatch,
        lambda: world.client().post(
            f"/api/v1/reviews/{report['review_id']}/finalize", json=finalize_body(report)
        ),
        lambda: world.client().post(
            f"/api/v1/review-cycles/{cycle['id']}/close",
            json={"expected_version": cycle["version"]},
        ),
    )
    assert sorted(r.status_code for r in responses) == [200, 409]
    error = next(r.json()["error"]["code"] for r in responses if r.status_code == 409)
    assert error in ("stale_version", "cycle_reviews_incomplete")


def test_simultaneous_close_commits_once(world, monkeypatch):
    cycle, participant, _, base = ready_world(world)
    report = calculate(world, cycle, participant, base).json()
    report = (
        world.client()
        .post(f"/api/v1/reviews/{report['review_id']}/finalize", json=finalize_body(report))
        .json()
    )
    path = f"/api/v1/review-cycles/{cycle['id']}/close"
    body = {"expected_version": report["cycle_version"]}
    responses = race(
        monkeypatch,
        lambda: world.client().post(path, json=body),
        lambda: world.client().post(path, json=body),
    )
    assert sorted(r.status_code for r in responses) == [200, 409]


def test_report_read_has_one_snapshot_while_kpis_change(world, monkeypatch):
    from app.modules.performance import service

    cycle, participant, item, base = ready_world(world)
    calculate(world, cycle, participant, base)
    entered, release = Event(), Event()
    original = service.collect

    def pause(*args, **kwargs):
        entered.set()
        assert release.wait(15)
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "collect", pause)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(lambda: world.client().get(base + f"?cycle_id={cycle['id']}"))
        assert entered.wait(10)
        try:
            changed = world.client().patch(
                f"/api/v1/employee-kpis/{item['id']}",
                json={
                    "expected_evidence_version": participant["evidence_version"],
                    "actual": "11.0000",
                },
            )
            assert changed.status_code == 200
        finally:
            release.set()
        report = future.result(timeout=20).json()
    assert (
        report["state"] == "CURRENT"
        and report["evidence_version"] == participant["evidence_version"]
    )
    assert report["current_result"]["final_score"] == "87.00"


@pytest.mark.parametrize("change", ["disabled", "logout", "role", "transfer"])
def test_waiting_calculator_revalidates_current_authority(world, monkeypatch, change):
    from app.models import Employee, User
    from app.modules.organization.repository import OrganizationRepository

    cycle, participant, _, base = ready_world(world)
    entered, release = Event(), Event()
    original = OrganizationRepository.lock_guard

    def pause(self):
        if not self.session.info.get("paused"):
            self.session.info["paused"] = True
            entered.set()
            assert release.wait(15)
        return original(self)

    monkeypatch.setattr(OrganizationRepository, "lock_guard", pause)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(lambda: calculate(world, cycle, participant, base, "manager"))
        assert entered.wait(10)
        try:
            if change == "logout":
                assert world.client("manager").post("/api/v1/auth/logout").status_code == 204
            else:
                with Session(world.engine) as session, session.begin():
                    actor = session.get(User, UUID(world.users["manager"]))
                    if change == "disabled":
                        actor.is_active = False
                    elif change == "role":
                        actor.role = "EMPLOYEE"
                    else:
                        session.get(Employee, UUID(world.employees["alice"])).manager_id = UUID(
                            world.employees["other"]
                        )
        finally:
            release.set()
        assert (
            future.result(timeout=20).status_code
            == {"disabled": 401, "logout": 401, "role": 403, "transfer": 404}[change]
        )


def test_close_competes_with_next_activation_without_two_active_cycles(world, monkeypatch):
    from app.models import ReviewCycle

    from .test_review_cycles import draft, enroll

    cycle, participant, _, base = ready_world(world)
    report = calculate(world, cycle, participant, base).json()
    report = (
        world.client()
        .post(f"/api/v1/reviews/{report['review_id']}/finalize", json=finalize_body(report))
        .json()
    )
    next_cycle = enroll(world, draft(world, name="Next"), "alice")
    responses = race(
        monkeypatch,
        lambda: world.client().post(
            f"/api/v1/review-cycles/{cycle['id']}/close",
            json={"expected_version": report["cycle_version"]},
        ),
        lambda: world.client().post(
            f"/api/v1/review-cycles/{next_cycle['id']}/activate",
            json={"expected_version": next_cycle["version"]},
        ),
    )
    assert responses[0].status_code == 200
    assert responses[1].status_code in (200, 409)
    with Session(world.engine) as session:
        assert (
            session.scalar(
                select(func.count()).select_from(ReviewCycle).where(ReviewCycle.status == "ACTIVE")
            )
            <= 1
        )
