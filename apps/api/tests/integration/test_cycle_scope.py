from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session


def active_cycle_fixture(world):
    """Prepare persisted history without relying on the activation endpoint under test."""
    from app.models import CycleParticipant, CycleStatus, ReviewCycle
    from app.modules.review_cycles.schemas import ParticipantSnapshot
    from app.modules.settings.schemas import ScoringPolicy

    identifier = uuid4()
    with Session(world.engine) as session, session.begin():
        session.add(
            ReviewCycle(
                id=identifier,
                name="Historical",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 3, 31),
                status=CycleStatus.ACTIVE,
                activated_at=datetime.now(UTC),
                policy_source_version=1,
                scoring_policy_snapshot=ScoringPolicy().model_dump(mode="json"),
            )
        )
        session.flush()
        for name, manager in [("alice", "manager"), ("bob", "other"), ("indirect", "alice")]:
            snapshot = ParticipantSnapshot(
                employee_id=UUID(world.employees[name]),
                user_id=UUID(world.users[name]),
                employee_code=f"EMP-{name.upper()}",
                display_name=f"Frozen {name}",
                department_id=UUID(world.departments["ENG"]),
                department_code="ENG",
                department_name="Frozen department",
                position_id=UUID(world.positions["DEV"]),
                position_code="DEV",
                position_title="Frozen role",
                manager_id=UUID(world.employees[manager]),
                manager_user_id=UUID(world.users[manager]),
                manager_display_name=manager,
                direct_reports=[],
            )
            session.add(
                CycleParticipant(
                    cycle_id=identifier,
                    employee_id=world.employees[name],
                    snapshot=snapshot.model_dump(mode="json"),
                )
            )
    return str(identifier)


def test_cycle_lists_counts_and_participants_are_scoped_in_sql(world):
    identifier = active_cycle_fixture(world)
    for role, expected in [
        ("hr", ["alice", "bob", "indirect"]),
        ("manager", ["alice"]),
        ("other", ["bob"]),
        ("alice", ["alice"]),
        ("unlinked", []),
    ]:
        client = world.client(role)
        listing = client.get("/api/v1/review-cycles?page_size=1")
        assert listing.status_code == 200
        assert listing.json()["total"] == int(bool(expected))
        detail = client.get(f"/api/v1/review-cycles/{identifier}")
        if not expected:
            assert detail.status_code == 404
            continue
        assert detail.status_code == 200
        assert detail.json()["participant_count"] == len(expected)
        rows = client.get(f"/api/v1/review-cycles/{identifier}/participants").json()
        assert rows["total"] == len(expected)
        assert {r["employee_id"] for r in rows["items"]} == {world.employees[n] for n in expected}
        assert all(r["display_name"].startswith("Frozen ") for r in rows["items"])
        assert all(
            "snapshot" not in r and "user_id" not in r and "direct_reports" not in r
            for r in rows["items"]
        )
    assert world.client("admin").get("/api/v1/review-cycles").status_code == 403
    assert (
        world.client("manager")
        .get(f"/api/v1/review-cycles/{identifier}/participants?q=Frozen%20bob")
        .json()["total"]
        == 0
    )
    assert (
        world.client().get(f"/api/v1/review-cycles/{uuid4()}").json()["error"]["code"]
        == "cycle_not_found"
    )


def test_transfer_changes_live_scope_without_changing_snapshot(world):
    from app.models import Employee

    identifier = active_cycle_fixture(world)
    with Session(world.engine) as session, session.begin():
        employee = session.get(Employee, world.employees["alice"])
        employee.manager_id = UUID(world.employees["other"])
        employee.department_id = UUID(world.departments["SALES"])
        employee.display_name = "Changed name"
    assert world.client("manager").get(f"/api/v1/review-cycles/{identifier}").status_code == 404
    rows = world.client("other").get(f"/api/v1/review-cycles/{identifier}/participants").json()
    assert rows["total"] == 2
    alice = next(r for r in rows["items"] if r["employee_id"] == world.employees["alice"])
    assert alice["display_name"] == "Frozen alice"
    assert alice["department_id"] == world.departments["ENG"]
