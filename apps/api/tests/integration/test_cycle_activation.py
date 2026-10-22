from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.service import AuditWriter

from .test_review_cycles import activate, draft, enroll


def test_activation_freezes_policy_and_relationships(world):
    from app.models import CycleParticipant

    cycle = enroll(world, draft(world), "alice")
    active = activate(world, cycle)
    assert active["status"] == "ACTIVE" and not active["policy_is_preview"]
    assert active["version"] == 3 and not active["can_edit"]
    rows = world.client().get(f"/api/v1/review-cycles/{cycle['id']}/participants").json()["items"]
    assert rows[0]["is_snapshot"] and rows[0]["evidence_version"] == 2
    with Session(world.engine) as session:
        participant = session.scalars(select(CycleParticipant)).one()
        snapshot = participant.snapshot
        assert snapshot["manager_user_id"] == world.users["manager"]
        assert snapshot["direct_reports"][0]["employee_id"] == world.employees["indirect"]
        assert "email" not in str(snapshot)
    world.client("admin").patch(
        "/api/v1/settings/scoring",
        json={
            "expected_version": 1,
            "policy": {"kpi_cap": "150.00"},
        },
    )
    assert (
        world.client().get(f"/api/v1/review-cycles/{cycle['id']}").json()["policy"]["kpi_cap"]
        == "100.00"
    )
    assert (
        world.client()
        .patch(
            f"/api/v1/review-cycles/{cycle['id']}",
            json={
                "expected_version": 3,
                "name": "Forbidden edit",
            },
        )
        .json()["error"]["code"]
        == "cycle_not_draft"
    )
    next_cycle = enroll(world, draft(world, name="Next"), "bob")
    conflict = world.client().post(
        f"/api/v1/review-cycles/{next_cycle['id']}/activate",
        json={
            "expected_version": next_cycle["version"],
        },
    )
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "active_cycle_exists"
    closing = world.client().post(
        f"/api/v1/review-cycles/{cycle['id']}/close", json={"expected_version": active["version"]}
    )
    assert closing.status_code == 409
    assert closing.json()["error"]["code"] == "cycle_reviews_incomplete"


@pytest.mark.parametrize(
    "problem",
    [
        "no_participants",
        "no_manager",
        "unlinked",
        "inactive_account",
        "inactive_manager",
        "retired_reference",
    ],
)
def test_activation_requirements_fail_atomically(world, problem):
    from app.models import CycleParticipant, Department, Employee, User

    cycle = draft(world)
    if problem != "no_participants":
        cycle = enroll(world, cycle, "alice", "bob")
    with Session(world.engine) as session, session.begin():
        alice = session.get(Employee, world.employees["alice"])
        if problem == "no_manager":
            alice.manager_id = None
        elif problem == "unlinked":
            alice.user_id = None
        elif problem == "inactive_account":
            session.get(User, world.users["alice"]).is_active = False
        elif problem == "inactive_manager":
            session.get(Employee, world.employees["manager"]).employment_status = "INACTIVE"
        elif problem == "retired_reference":
            session.get(Department, world.departments["ENG"]).is_active = False
    response = world.client().post(
        f"/api/v1/review-cycles/{cycle['id']}/activate",
        json={
            "expected_version": cycle["version"],
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "activation_requirements_not_met"
    assert response.json()["error"]["details"]
    detail = world.client().get(f"/api/v1/review-cycles/{cycle['id']}").json()
    assert detail["status"] == "DRAFT" and detail["version"] == cycle["version"]
    with Session(world.engine) as session:
        assert all(
            p.snapshot is None and p.evidence_version == 1
            for p in session.scalars(select(CycleParticipant))
        )


def test_activation_audit_failure_restores_every_participant(world, monkeypatch):
    from app.models import CycleParticipant

    cycle = enroll(world, draft(world), "alice", "bob")

    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(AuditWriter, "record", fail)
    response = world.client().post(
        f"/api/v1/review-cycles/{cycle['id']}/activate",
        json={
            "expected_version": 2,
        },
    )
    assert response.status_code == 500
    assert world.client().get(f"/api/v1/review-cycles/{cycle['id']}").json()["status"] == "DRAFT"
    with Session(world.engine) as session:
        assert all(
            p.snapshot is None and p.evidence_version == 1
            for p in session.scalars(select(CycleParticipant))
        )


def test_historical_manager_does_not_confer_current_scope(world):
    from app.models import Employee

    cycle = activate(world, enroll(world, draft(world), "alice"))
    with Session(world.engine) as session, session.begin():
        session.get(Employee, world.employees["alice"]).manager_id = UUID(world.employees["other"])
    assert world.client("manager").get(f"/api/v1/review-cycles/{cycle['id']}").status_code == 404
    assert world.client("other").get(f"/api/v1/review-cycles/{cycle['id']}").status_code == 200
