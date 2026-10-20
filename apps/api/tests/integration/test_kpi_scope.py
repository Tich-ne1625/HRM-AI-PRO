from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from sqlalchemy.orm import Session

from .test_employee_kpis import allocation_world, replace_body


@pytest.mark.parametrize("change", ["logout", "disable", "transfer", "role"])
def test_waiting_writer_revalidates_current_identity_and_scope(world, monkeypatch, change):
    from app.modules.organization.repository import OrganizationRepository

    _cycle, first, _second, path = allocation_world(world)
    waiting, release = Event(), Event()
    original = OrganizationRepository.lock_guard

    def pause(self):
        if not waiting.is_set():
            waiting.set()
            assert release.wait(timeout=15)
        return original(self)

    monkeypatch.setattr(OrganizationRepository, "lock_guard", pause)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(lambda: world.client("manager").put(path, json=replace_body(first)))
        assert waiting.wait(timeout=15)
        try:
            if change == "logout":
                changed = world.client("manager").post("/api/v1/auth/logout")
                assert changed.status_code == 204
            elif change == "transfer":
                changed = world.client().patch(
                    f"/api/v1/employees/{world.employees['alice']}",
                    json={"manager_id": world.employees["other"]},
                )
                assert changed.status_code == 200
            else:
                changed = world.client("admin").patch(
                    f"/api/v1/users/{world.users['manager']}",
                    json={"is_active": False} if change == "disable" else {"role": "EMPLOYEE"},
                )
                assert changed.status_code == 200
        finally:
            release.set()
        response = future.result(timeout=25)
    assert (
        response.status_code
        == {"logout": 401, "disable": 401, "transfer": 404, "role": 403}[change]
    )
    assert world.client().get(path).json()["items"] == []


def test_manager_cannot_edit_self_or_indirect_report(world):
    from app.models import User, UserRole

    _cycle, first, _second, path = allocation_world(world)
    with Session(world.engine) as session, session.begin():
        session.get(User, world.users["alice"]).role = UserRole.MANAGER
    assert world.client("alice").get(path).json()["participant"]["can_manage_kpis"] is False
    assert world.client("alice").put(path, json=replace_body(first)).status_code == 403
    indirect_path = path.replace(world.employees["alice"], world.employees["indirect"])
    assert world.client("manager").put(indirect_path, json=replace_body(first)).status_code == 404


def test_inactive_employment_disables_manager_write_but_hr_can_complete_history(world):
    from app.models import Employee, EmploymentStatus

    _cycle, first, _second, path = allocation_world(world)
    with Session(world.engine) as session, session.begin():
        session.get(
            Employee, world.employees["alice"]
        ).employment_status = EmploymentStatus.INACTIVE
    assert world.client("manager").put(path, json=replace_body(first)).status_code == 403
    assert world.client().put(path, json=replace_body(first)).status_code == 200
