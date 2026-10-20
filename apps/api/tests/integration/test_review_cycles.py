from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.service import AuditWriter


def draft(world, **changes):
    response = world.client().post(
        "/api/v1/review-cycles",
        json={
            "name": "Q4",
            "start_date": "2026-10-01",
            "end_date": "2026-12-31",
            **changes,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def enroll(world, cycle, *names):
    response = world.client().post(
        f"/api/v1/review-cycles/{cycle['id']}/participants",
        json={
            "expected_version": cycle["version"],
            "employee_ids": [world.employees[name] for name in names],
        },
    )
    assert response.status_code == 200, response.text
    return world.client().get(f"/api/v1/review-cycles/{cycle['id']}").json()


def activate(world, cycle):
    response = world.client().post(
        f"/api/v1/review-cycles/{cycle['id']}/activate",
        json={
            "expected_version": cycle["version"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_hr_draft_lifecycle_and_versioned_enrollment(world):
    hr = world.client()
    cycle = draft(world)
    assert cycle["status"] == "DRAFT" and cycle["policy_is_preview"]
    assert cycle["can_edit"] and cycle["participant_count"] == 0
    for role in ("admin", "manager", "alice", "unlinked"):
        assert (
            world.client(role)
            .post(
                "/api/v1/review-cycles",
                json={
                    "name": "No",
                    "start_date": "2026-01-01",
                    "end_date": "2026-02-01",
                },
            )
            .status_code
            == 403
        )
    for role in ("manager", "alice", "unlinked"):
        assert world.client(role).get("/api/v1/review-cycles").json()["total"] == 0
        assert world.client(role).get(f"/api/v1/review-cycles/{cycle['id']}").status_code == 404
    cycle = enroll(world, cycle, "alice", "bob")
    assert cycle["version"] == 2 and cycle["participant_count"] == 2
    path = f"/api/v1/review-cycles/{cycle['id']}"
    assert (
        hr.post(
            f"{path}/participants",
            json={
                "expected_version": 1,
                "employee_ids": [world.employees["indirect"]],
            },
        ).json()["error"]["code"]
        == "stale_version"
    )
    assert (
        hr.post(
            f"{path}/participants",
            json={
                "expected_version": 2,
                "employee_ids": [world.employees["alice"]],
            },
        ).json()["error"]["code"]
        == "participant_already_enrolled"
    )
    assert hr.patch(path, json={"expected_version": 2, "end_date": "2026-09-01"}).status_code == 422
    saved = hr.patch(path, json={"expected_version": 2, "name": "Renamed"})
    assert saved.status_code == 200 and saved.json()["version"] == 3
    rows = hr.get(f"{path}/participants?page_size=1").json()
    assert rows["total"] == 2 and len(rows["items"]) == 1
    removed = hr.request(
        "DELETE", f"{path}/participants/{rows['items'][0]['id']}", json={"expected_version": 3}
    )
    assert removed.status_code == 200 and removed.json()["version"] == 4
    assert hr.get(path).json()["participant_count"] == 1


def test_enrollment_batch_is_atomic_and_requires_active_employees(world):
    from app.models import Employee

    cycle = draft(world)
    with Session(world.engine) as session, session.begin():
        employee = session.get(Employee, world.employees["bob"])
        employee.employment_status = "INACTIVE"
    response = world.client().post(
        f"/api/v1/review-cycles/{cycle['id']}/participants",
        json={
            "expected_version": 1,
            "employee_ids": [world.employees["alice"], world.employees["bob"]],
        },
    )
    assert response.status_code == 409
    assert (
        world.client().get(f"/api/v1/review-cycles/{cycle['id']}").json()["participant_count"] == 0
    )
    assert (
        world.client()
        .post(
            f"/api/v1/review-cycles/{cycle['id']}/participants",
            json={
                "expected_version": 1,
                "employee_ids": [str(uuid4())],
            },
        )
        .status_code
        == 404
    )


@pytest.mark.parametrize("operation", ["create", "enroll", "remove"])
def test_cycle_mutations_rollback_when_audit_fails(world, monkeypatch, operation):
    from app.models import CycleParticipant, ReviewCycle

    cycle = enroll(world, draft(world), "alice") if operation != "create" else None
    if cycle:
        participant = (
            world.client()
            .get(f"/api/v1/review-cycles/{cycle['id']}/participants")
            .json()["items"][0]
        )

    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(AuditWriter, "record", fail)
    client = world.client()
    if operation == "create":
        response = client.post(
            "/api/v1/review-cycles",
            json={
                "name": "Fail",
                "start_date": "2026-01-01",
                "end_date": "2026-02-01",
            },
        )
    elif operation == "enroll":
        response = client.post(
            f"/api/v1/review-cycles/{cycle['id']}/participants",
            json={
                "expected_version": 2,
                "employee_ids": [world.employees["bob"]],
            },
        )
    else:
        response = client.request(
            "DELETE",
            f"/api/v1/review-cycles/{cycle['id']}/participants/{participant['id']}",
            json={"expected_version": 2},
        )
    assert response.status_code == 500
    with Session(world.engine) as session:
        rows = list(session.scalars(select(ReviewCycle)))
        if operation == "create":
            assert not rows
        else:
            assert len(rows) == 1 and rows[0].version == 2
            assert len(list(session.scalars(select(CycleParticipant)))) == 1
