from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.service import AuditWriter


def definition(**changes):
    return {
        "code": " sales ",
        "name": " Sales ",
        "unit": "VND",
        "direction": "HIGHER_IS_BETTER",
        **changes,
    }


def test_hr_catalog_create_patch_and_scoped_empty_lists(world):
    hr = world.client()
    response = hr.post("/api/v1/kpis", json=definition())
    assert response.status_code == 201
    row = response.json()
    assert row["code"] == "SALES" and row["name"] == "Sales" and row["version"] == 1
    assert "score" not in row
    for role in ("manager", "alice", "unlinked", "other"):
        assert world.client(role).get("/api/v1/kpis").json()["total"] == 0
        assert world.client(role).post("/api/v1/kpis", json=definition()).status_code == 403
        assert (
            world.client(role)
            .patch(
                f"/api/v1/kpis/{row['id']}",
                json={
                    "expected_version": 1,
                    "name": "Forgery",
                },
            )
            .status_code
            == 403
        )
    assert world.client("admin").get("/api/v1/kpis").status_code == 403
    assert hr.get("/api/v1/kpis?q=sal").json()["total"] == 1
    assert hr.get("/api/v1/kpis?q=%").json()["total"] == 0
    assert hr.get("/api/v1/kpis?sort=not_a_column").status_code == 422
    duplicate = hr.post("/api/v1/kpis", json=definition())
    assert duplicate.status_code == 409 and duplicate.json()["error"]["code"] == "duplicate_code"
    changed = hr.patch(
        f"/api/v1/kpis/{row['id']}",
        json={
            "expected_version": 1,
            "is_active": False,
        },
    )
    assert changed.status_code == 200 and changed.json()["version"] == 2
    assert (
        hr.patch(
            f"/api/v1/kpis/{row['id']}",
            json={
                "expected_version": 1,
                "name": "Old version",
            },
        ).json()["error"]["code"]
        == "stale_version"
    )
    assert hr.get("/api/v1/kpis?is_active=true").json()["total"] == 0
    assert hr.get("/api/v1/kpis?is_active=false").json()["total"] == 1
    assert (
        hr.patch(
            f"/api/v1/kpis/{uuid4()}",
            json={
                "expected_version": 1,
                "name": "Missing",
            },
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"name": "bad\x00name"},
        {"unit": " "},
        {"direction": "OTHER"},
        {"description": "bad\x01description"},
        {"scope": "HR"},
    ],
)
def test_invalid_definitions_422(world, changes):
    assert world.client().post("/api/v1/kpis", json=definition(**changes)).status_code == 422


def test_definition_audit_failure_rolls_back(world, monkeypatch):
    from app.models import KPIDefinition

    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(AuditWriter, "record", fail)
    assert world.client().post("/api/v1/kpis", json=definition()).status_code == 500
    with Session(world.engine) as session:
        assert not list(session.scalars(select(KPIDefinition)))
