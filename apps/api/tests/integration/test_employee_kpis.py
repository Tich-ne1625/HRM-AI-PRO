from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.service import AuditWriter

from .test_kpi_definitions import definition
from .test_review_cycles import activate, draft, enroll


def allocation_world(world):
    cycle = activate(world, enroll(world, draft(world), "alice", "bob"))
    first = world.client().post("/api/v1/kpis", json=definition()).json()
    second = (
        world.client()
        .post(
            "/api/v1/kpis",
            json=definition(code="ERRORS", name="Errors", direction="LOWER_IS_BETTER"),
        )
        .json()
    )
    path = f"/api/v1/employees/{world.employees['alice']}/kpis?cycle_id={cycle['id']}"
    return cycle, first, second, path


def replace_body(first, second=None, version=2):
    items = [
        {
            "definition_id": first["id"],
            "target": "100.0000",
            "weight": "60.00" if second else "100.00",
        }
    ]
    if second:
        items.append({"definition_id": second["id"], "target": "5.0000", "weight": "40.00"})
    return {"expected_evidence_version": version, "items": items}


def test_complete_allocation_actuals_and_scope(world):
    _cycle, first, second, path = allocation_world(world)
    initial = world.client("alice").get(path)
    assert initial.status_code == 200 and initial.json()["items"] == []
    assert initial.json()["participant"]["evidence_version"] == 2
    saved = world.client("manager").put(path, json=replace_body(first, second))
    assert saved.status_code == 200, saved.text
    data = saved.json()
    assert data["participant"]["evidence_version"] == 3
    assert len(data["items"]) == 2
    assert all(row["actual"] is None and "score" not in row for row in data["items"])
    for role in ("other", "bob", "unlinked"):
        assert world.client(role).get(path).status_code == 404
        assert world.client(role).put(path, json=replace_body(first, version=3)).status_code in (
            403,
            404,
        )
    assert world.client("alice").put(path, json=replace_body(first, version=3)).status_code == 403
    assert world.client("admin").get(path).status_code == 403
    assert world.client("manager").get("/api/v1/kpis").json()["total"] == 2
    assert world.client("bob").get("/api/v1/kpis").json()["total"] == 0
    row = data["items"][0]
    actual_path = f"/api/v1/employee-kpis/{row['id']}"
    result = world.client("manager").patch(
        actual_path,
        json={
            "expected_evidence_version": 3,
            "actual": "0.0000",
        },
    )
    assert result.status_code == 200
    assert result.json()["participant"]["evidence_version"] == 4
    assert next(r for r in result.json()["items"] if r["id"] == row["id"])["actual"] == "0.0000"
    stale = world.client().patch(
        actual_path, json={"expected_evidence_version": 3, "actual": "7.0000"}
    )
    assert stale.json()["error"]["code"] == "stale_evidence_version"
    cleared = world.client().patch(
        actual_path, json={"expected_evidence_version": 4, "actual": None}
    )
    assert cleared.status_code == 200
    assert all(r["actual"] is None for r in cleared.json()["items"])


def test_replacement_retains_snapshot_and_actual_until_target_changes(world):
    _cycle, first, second, path = allocation_world(world)
    saved = world.client().put(path, json=replace_body(first)).json()
    row = saved["items"][0]
    world.client().patch(
        f"/api/v1/employee-kpis/{row['id']}",
        json={
            "expected_evidence_version": 3,
            "actual": "50.0000",
        },
    )
    world.client().patch(
        f"/api/v1/kpis/{first['id']}",
        json={
            "expected_version": 1,
            "name": "Renamed definition",
            "direction": "LOWER_IS_BETTER",
        },
    )
    kept = world.client().put(path, json=replace_body(first, second, version=4)).json()
    old = next(r for r in kept["items"] if r["definition_id"] == first["id"])
    assert old["id"] == row["id"] and old["actual"] == "50.0000"
    assert old["definition"]["name"] == "Sales"
    assert old["definition"]["direction"] == "HIGHER_IS_BETTER"
    body = replace_body(first, second, version=5)
    body["items"][0]["target"] = "200.0000"
    changed = world.client().put(path, json=body)
    assert changed.status_code == 200
    assert all(r["actual"] is None for r in changed.json()["items"])
    # Removing then assigning again takes the current definition snapshot.
    world.client().put(path, json=replace_body(second, version=6))
    readded = world.client().put(path, json=replace_body(first, second, version=7)).json()
    assert (
        next(r for r in readded["items"] if r["definition_id"] == first["id"])["definition"]["name"]
        == "Renamed definition"
    )


def test_retired_definition_can_be_kept_but_not_newly_assigned(world):
    _cycle, first, second, path = allocation_world(world)
    saved = world.client().put(path, json=replace_body(first)).json()
    world.client().patch(
        f"/api/v1/kpis/{first['id']}", json={"expected_version": 1, "is_active": False}
    )
    # Exact no-op retains version even for a retired definition.
    assert (
        world.client()
        .put(path, json=replace_body(first, version=3))
        .json()["participant"]["evidence_version"]
        == 3
    )
    row = saved["items"][0]
    assert (
        world.client()
        .patch(
            f"/api/v1/employee-kpis/{row['id']}",
            json={
                "expected_evidence_version": 3,
                "actual": "3.0000",
            },
        )
        .status_code
        == 200
    )
    world.client().put(path, json=replace_body(second, version=4))
    failed = world.client().put(path, json=replace_body(first, version=5))
    assert failed.status_code == 409 and failed.json()["error"]["code"] == "kpi_definition_inactive"


@pytest.mark.parametrize("failure", ["empty", "sum", "duplicate", "target", "precision", "unknown"])
def test_invalid_allocations_never_store_partial_evidence(world, failure):
    _cycle, first, _second, path = allocation_world(world)
    body = replace_body(first)
    if failure == "empty":
        body["items"] = []
    elif failure == "sum":
        body["items"][0]["weight"] = "99.99"
    elif failure == "duplicate":
        body = replace_body(first, first)
    elif failure == "target":
        body["items"][0]["target"] = "0.0000"
    elif failure == "precision":
        body["items"][0]["target"] = "1.00001"
    else:
        body["items"][0]["definition_id"] = str(uuid4())
    response = world.client().put(path, json=body)
    assert response.status_code == (404 if failure == "unknown" else 422)
    assert world.client().get(path).json()["items"] == []
    assert world.client().get(path).json()["participant"]["evidence_version"] == 2


@pytest.mark.parametrize("mutation", ["replace", "actual"])
def test_evidence_audit_failure_restores_rows_and_version(world, monkeypatch, mutation):
    from app.models import EmployeeKPI

    _cycle, first, second, path = allocation_world(world)
    saved = world.client().put(path, json=replace_body(first)).json()
    row = saved["items"][0]

    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(AuditWriter, "record", fail)
    if mutation == "replace":
        response = world.client().put(path, json=replace_body(second, version=3))
    else:
        response = world.client().patch(
            f"/api/v1/employee-kpis/{row['id']}",
            json={
                "expected_evidence_version": 3,
                "actual": "25.0000",
            },
        )
    assert response.status_code == 500
    current = world.client().get(path).json()
    assert current["participant"]["evidence_version"] == 3
    assert current["items"][0]["id"] == row["id"] and current["items"][0]["actual"] is None
    with Session(world.engine) as session:
        assert len(list(session.scalars(select(EmployeeKPI)))) == 1


def test_manager_options_are_scoped_and_transfer_takes_effect(world):
    from app.models import Employee

    _cycle, first, _second, path = allocation_world(world)
    options = path.replace("/kpis?", "/kpi-options?")
    assert world.client("manager").get(options).json()["total"] == 2
    assert world.client("other").get(options).status_code == 404
    assert world.client("alice").get(options).status_code == 403
    with Session(world.engine) as session, session.begin():
        session.get(Employee, world.employees["alice"]).manager_id = UUID(world.employees["other"])
    assert world.client("manager").put(path, json=replace_body(first)).status_code == 404
    assert world.client("other").put(path, json=replace_body(first)).status_code == 200


def test_uncapped_policy_rejects_new_lower_kpis(world):
    world.client("admin").patch(
        "/api/v1/settings/scoring",
        json={
            "expected_version": 1,
            "policy": {"kpi_cap": None},
        },
    )
    _cycle, _first, second, path = allocation_world(world)
    result = world.client().put(path, json=replace_body(second))
    assert result.status_code == 409 and result.json()["error"]["code"] == "kpi_policy_incompatible"


def test_finalized_and_closed_evidence_is_immutable(world):
    from datetime import UTC, datetime

    from app.models import CycleParticipant, ReviewCycle

    cycle, first, second, path = allocation_world(world)
    saved = world.client().put(path, json=replace_body(first)).json()
    with Session(world.engine) as session, session.begin():
        row = session.get(CycleParticipant, saved["participant"]["id"])
        row.finalized_at = datetime.now(UTC)
    response = world.client().put(path, json=replace_body(second, version=3))
    assert response.json()["error"]["code"] == "participant_finalized"
    with Session(world.engine) as session, session.begin():
        session.get(ReviewCycle, cycle["id"]).status = "CLOSED"
    response = world.client().put(path, json=replace_body(second, version=3))
    assert response.json()["error"]["code"] == "cycle_not_active"
