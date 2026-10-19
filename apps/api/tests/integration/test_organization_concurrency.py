from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Employee


def test_admin_disabling_hr_and_hr_linking_admin_do_not_deadlock(world, monkeypatch):
    from app.modules.users.repository import UserRepository

    barrier = Barrier(2)
    original = UserRepository.lock_active_admins

    def lock(self):
        from sqlalchemy import text

        self.session.execute(text("SET LOCAL lock_timeout = '8s'"))
        barrier.wait(timeout=15)
        return original(self)

    monkeypatch.setattr(UserRepository, "lock_active_admins", lock)

    def disable():
        return world.client("admin").patch(
            f"/api/v1/users/{world.users['hr']}", json={"is_active": False}
        )

    def link():
        return world.client().patch(
            f"/api/v1/employees/{world.employees['alice']}", json={"user_id": world.users["admin"]}
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(disable), pool.submit(link)
        disabled, linked = first.result(timeout=25), second.result(timeout=25)
    assert disabled.status_code == 200
    assert linked.status_code in {200, 401}


@pytest.mark.parametrize("three_nodes", [False, True])
def test_simultaneous_manager_changes_cannot_create_reporting_cycle(
    world, monkeypatch, three_nodes
):
    from app.modules.organization.repository import OrganizationRepository

    barrier = Barrier(2)
    original = OrganizationRepository.lock_guard
    seen = []

    def acquire(self):
        seen.append(self.session)
        barrier.wait(timeout=15)
        return original(self)

    monkeypatch.setattr(OrganizationRepository, "lock_guard", acquire)
    # Existing manager -> Alice -> Indirect chain. Two new edges would
    # complete either a two-node or a four-node cycle if read concurrently.
    second = "indirect" if three_nodes else "manager"
    changes = [
        (world.employees["manager"], world.employees["other"]),
        (world.employees["other"], world.employees[second]),
    ]

    def change(item):
        return world.client().patch(f"/api/v1/employees/{item[0]}", json={"manager_id": item[1]})

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(change, changes))
    assert len(seen) == 2 and seen[0] is not seen[1]
    assert sorted(r.status_code for r in responses) == [200, 409]
    assert (
        next(r for r in responses if r.status_code == 409).json()["error"]["code"]
        == "reporting_cycle"
    )
    with Session(world.engine) as session:
        graph = {row.id: row.manager_id for row in session.scalars(select(Employee))}
        for start in graph:
            visited = set()
            cursor = start
            while cursor is not None:
                assert cursor not in visited
                visited.add(cursor)
                cursor = graph[cursor]


def test_concurrent_user_link_claims_yield_one_winner(world, monkeypatch):
    from app.modules.organization.repository import OrganizationRepository

    barrier = Barrier(2)
    original = OrganizationRepository.lock_guard

    def acquire(self):
        barrier.wait(timeout=15)
        return original(self)

    monkeypatch.setattr(OrganizationRepository, "lock_guard", acquire)

    def link(name):
        return world.client().patch(
            f"/api/v1/employees/{world.employees[name]}", json={"user_id": world.users["spare"]}
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(link, ["alice", "bob"]))
    assert sorted(response.status_code for response in responses) == [200, 409]
    assert (
        next(r for r in responses if r.status_code == 409).json()["error"]["code"]
        == "user_already_linked"
    )
    with Session(world.engine) as session:
        assert (
            len(
                session.scalars(
                    select(Employee).where(Employee.user_id == world.users["spare"])
                ).all()
            )
            == 1
        )
