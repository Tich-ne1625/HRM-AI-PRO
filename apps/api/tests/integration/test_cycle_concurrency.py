from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .test_kpi_concurrency import race
from .test_review_cycles import draft, enroll


def test_concurrent_enrollment_uses_cycle_version(world, monkeypatch):
    cycle = draft(world)

    def add(name):
        return world.client().post(
            f"/api/v1/review-cycles/{cycle['id']}/participants",
            json={
                "expected_version": 1,
                "employee_ids": [world.employees[name]],
            },
        )

    responses = race(monkeypatch, lambda: add("alice"), lambda: add("bob"))
    assert sorted(r.status_code for r in responses) == [200, 409]
    current = world.client().get(f"/api/v1/review-cycles/{cycle['id']}").json()
    assert current["version"] == 2 and current["participant_count"] == 1


def test_concurrent_removal_and_metadata_do_not_lose_changes(world, monkeypatch):
    cycle = enroll(world, draft(world), "alice")
    path = f"/api/v1/review-cycles/{cycle['id']}"
    participant = world.client().get(f"{path}/participants").json()["items"][0]
    responses = race(
        monkeypatch,
        lambda: world.client().request(
            "DELETE", f"{path}/participants/{participant['id']}", json={"expected_version": 2}
        ),
        lambda: world.client().patch(path, json={"expected_version": 2, "name": "Renamed"}),
    )
    assert sorted(r.status_code for r in responses) == [200, 409]
    assert world.client().get(path).json()["version"] == 3


def test_two_cycles_cannot_activate_together(world, monkeypatch):
    first = enroll(world, draft(world, name="First"), "alice")
    second = enroll(world, draft(world, name="Second"), "bob")

    def activate(cycle):
        return world.client().post(
            f"/api/v1/review-cycles/{cycle['id']}/activate", json={"expected_version": 2}
        )

    responses = race(monkeypatch, lambda: activate(first), lambda: activate(second))
    assert sorted(r.status_code for r in responses) == [200, 409]
    assert world.client().get("/api/v1/review-cycles?status=ACTIVE").json()["total"] == 1


def test_activation_and_default_change_have_a_single_serial_order(world, monkeypatch):
    from app.modules.audit.service import AuditWriter

    cycle = enroll(world, draft(world), "alice")
    actions = []
    original = AuditWriter.record

    def audit(self, session, actor, action, *args, **kwargs):
        actions.append(action)
        return original(self, session, actor, action, *args, **kwargs)

    monkeypatch.setattr(AuditWriter, "record", audit)
    active, changed = race(
        monkeypatch,
        lambda: world.client().post(
            f"/api/v1/review-cycles/{cycle['id']}/activate", json={"expected_version": 2}
        ),
        lambda: world.client("admin").patch(
            "/api/v1/settings/scoring",
            json={
                "expected_version": 1,
                "policy": {"kpi_cap": "150.00"},
            },
        ),
    )
    assert active.status_code == changed.status_code == 200
    cap = "100.00" if actions[0] == "review_cycle.activated" else "150.00"
    assert active.json()["policy"]["kpi_cap"] == cap


def test_activation_and_transfer_freeze_one_consistent_manager(world, monkeypatch):
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app.models import CycleParticipant
    from app.modules.audit.service import AuditWriter

    cycle = enroll(world, draft(world), "alice")
    actions = []
    original = AuditWriter.record

    def audit(self, session, actor, action, *args, **kwargs):
        actions.append(action)
        return original(self, session, actor, action, *args, **kwargs)

    monkeypatch.setattr(AuditWriter, "record", audit)
    active, moved = race(
        monkeypatch,
        lambda: world.client().post(
            f"/api/v1/review-cycles/{cycle['id']}/activate", json={"expected_version": 2}
        ),
        lambda: world.client().patch(
            f"/api/v1/employees/{world.employees['alice']}",
            json={
                "manager_id": world.employees["other"],
            },
        ),
    )
    assert active.status_code == moved.status_code == 200
    expected = "manager" if actions[0] == "review_cycle.activated" else "other"
    with Session(world.engine) as session:
        snapshot = session.scalars(select(CycleParticipant)).one().snapshot
        assert snapshot["manager_id"] == world.employees[expected]
        assert snapshot["manager_user_id"] == world.users[expected]


@pytest.mark.parametrize("change", ["reference", "user_link"])
def test_activation_serializes_retirement_and_account_links(world, monkeypatch, change):
    from app.models import CycleParticipant
    from app.modules.audit.service import AuditWriter

    cycle = enroll(world, draft(world), "alice")
    actions = []
    original = AuditWriter.record

    def audit(self, session, actor, action, *args, **kwargs):
        actions.append(action)
        return original(self, session, actor, action, *args, **kwargs)

    monkeypatch.setattr(AuditWriter, "record", audit)

    def mutate():
        if change == "reference":
            return world.client().patch(
                f"/api/v1/departments/{world.departments['ENG']}", json={"is_active": False}
            )
        return world.client().patch(
            f"/api/v1/employees/{world.employees['alice']}", json={"user_id": world.users["spare"]}
        )

    active, changed = race(
        monkeypatch,
        lambda: world.client().post(
            f"/api/v1/review-cycles/{cycle['id']}/activate", json={"expected_version": 2}
        ),
        mutate,
    )
    assert changed.status_code == 200
    activated_first = actions[0] == "review_cycle.activated"
    if change == "reference":
        assert active.status_code == (200 if activated_first else 409)
    else:
        assert active.status_code == 200
        with Session(world.engine) as session:
            snapshot = session.scalars(select(CycleParticipant)).one().snapshot
            assert snapshot["user_id"] == world.users["alice" if activated_first else "spare"]


def test_activation_vs_account_deactivation_does_not_deadlock(world, monkeypatch):
    from app.modules.users.repository import UserRepository

    cycle = enroll(world, draft(world), "alice")
    barrier = Barrier(2)
    original = UserRepository.lock_active_admins

    def lock(self):
        self.session.execute(text("SET LOCAL lock_timeout = '8s'"))
        barrier.wait(timeout=15)
        return original(self)

    monkeypatch.setattr(UserRepository, "lock_active_admins", lock)
    with ThreadPoolExecutor(max_workers=2) as pool:
        activated = pool.submit(
            lambda: world.client().post(
                f"/api/v1/review-cycles/{cycle['id']}/activate", json={"expected_version": 2}
            )
        )
        disabled = pool.submit(
            lambda: world.client("admin").patch(
                f"/api/v1/users/{world.users['alice']}", json={"is_active": False}
            )
        )
        active, changed = activated.result(timeout=25), disabled.result(timeout=25)
    assert changed.status_code == 200
    assert active.status_code in (200, 409)
    # Whichever committed first, an old cookie cannot authenticate the disabled account.
    assert world.client("alice").get("/api/v1/review-cycles").status_code == 401
