from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.feedback.models import Feedback, FeedbackAssignment

from .test_feedback_workflows import create_assignment, feedback_world, submit, versions
from .test_kpi_concurrency import race


def test_simultaneous_assignment_creation_has_one_winner(world, monkeypatch):
    _, participant = feedback_world(world)
    responses = race(
        monkeypatch,
        lambda: create_assignment(world, participant),
        lambda: create_assignment(world, participant),
    )
    assert sorted(r.status_code for r in responses) == [201, 409]
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(FeedbackAssignment)) == 1


def test_simultaneous_submission_is_committed_once(world, monkeypatch):
    _, participant = feedback_world(world)
    row = create_assignment(world, participant).json()
    responses = race(monkeypatch, lambda: submit(world, row), lambda: submit(world, row))
    assert sorted(r.status_code for r in responses) == [201, 409]
    assert (
        next(r for r in responses if r.status_code == 409).json()["error"]["code"]
        == "feedback_already_submitted"
    )
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(Feedback)) == 1


def test_different_reviewers_share_participant_version(world, monkeypatch):
    _, participant = feedback_world(world)
    first = create_assignment(world, participant).json()
    second = create_assignment(
        world, {**participant, "evidence_version": 3}, "manager", "MANAGER"
    ).json()
    first = world.client("alice").get(f"/api/v1/feedback-assignments/{first['id']}").json()
    responses = race(
        monkeypatch, lambda: submit(world, first), lambda: submit(world, second, "manager")
    )
    assert sorted(r.status_code for r in responses) == [201, 409]
    assert (
        next(r for r in responses if r.status_code == 409).json()["error"]["code"]
        == "stale_evidence_version"
    )


@pytest.mark.parametrize("operation", ["cancel", "replace", "update"])
def test_submit_competes_with_hr_mutation(world, monkeypatch, operation):
    _, participant = feedback_world(world)
    row = create_assignment(world, participant, "bob", "PEER", required=False).json()
    path = f"/api/v1/feedback-assignments/{row['id']}"

    def mutate():
        if operation == "cancel":
            return world.client().request(
                "DELETE", path, json={**versions(row), "reason_code": "WRONG_SELECTION"}
            )
        if operation == "replace":
            return world.client().post(
                path + "/replace",
                json={
                    **versions(row),
                    "reviewer_id": world.users["other"],
                    "reason_code": "REVIEWER_UNAVAILABLE",
                },
            )
        return world.client().patch(path, json={**versions(row), "required": True})

    responses = race(monkeypatch, lambda: submit(world, row, "bob"), mutate)
    assert sorted(r.status_code for r in responses) in ([200, 409], [201, 409])
    assert sum(r.status_code in (200, 201) for r in responses) == 1


def test_submit_and_kpi_mutation_share_version(world, monkeypatch):
    from .test_employee_kpis import allocation_world, replace_body

    _, definition, _, path = allocation_world(world)
    participant = world.client().get(path).json()["participant"]
    row = create_assignment(world, participant).json()
    responses = race(
        monkeypatch,
        lambda: submit(world, row),
        lambda: world.client("manager").put(path, json=replace_body(definition, version=3)),
    )
    assert sorted(r.status_code for r in responses) in ([200, 409], [201, 409])


@pytest.mark.parametrize("change", ["disabled", "logout", "hr_role"])
def test_waiting_writer_revalidates_account_session_and_role(world, monkeypatch, change):
    from app.models import User
    from app.modules.organization.repository import OrganizationRepository

    _, participant = feedback_world(world)
    row = create_assignment(world, participant).json()
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
        if change == "hr_role":
            future = pool.submit(
                lambda: world.client().patch(
                    f"/api/v1/feedback-assignments/{row['id']}",
                    json={**versions(row), "due_at": None},
                )
            )
        else:
            future = pool.submit(lambda: submit(world, row))
        assert entered.wait(10)
        try:
            if change == "logout":
                assert world.client("alice").post("/api/v1/auth/logout").status_code == 204
            else:
                with Session(world.engine) as session, session.begin():
                    user = session.get(
                        User, UUID(world.users["hr" if change == "hr_role" else "alice"])
                    )
                    if change == "hr_role":
                        user.role = "EMPLOYEE"
                    else:
                        user.is_active = False
        finally:
            release.set()
        assert future.result(timeout=20).status_code == (403 if change == "hr_role" else 401)
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(Feedback)) == 0


def test_deadline_checked_after_waiting_for_guard_at_exact_boundary(world, monkeypatch):
    from datetime import UTC, datetime, timedelta

    from app.modules.feedback import service
    from app.modules.organization.repository import OrganizationRepository

    _, participant = feedback_world(world)
    due = datetime.now(UTC) + timedelta(hours=1)
    row = create_assignment(world, participant, due_at=due.isoformat()).json()
    current = [due - timedelta(seconds=1)]

    class Clock:
        @staticmethod
        def now(tz):
            return current[0]

    monkeypatch.setattr(service, "datetime", Clock)
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
        future = pool.submit(lambda: submit(world, row))
        assert entered.wait(10)
        current[0] = due
        release.set()
        response = future.result(timeout=20)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "deadline_passed"
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(Feedback)) == 0
