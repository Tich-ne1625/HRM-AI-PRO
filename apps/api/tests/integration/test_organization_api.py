from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import AuditLog, Department, Position
from app.modules.audit.service import AuditWriter


def test_reference_label_rejects_database_unsupported_control_characters(world):
    response = world.client().post(
        "/api/v1/departments", json={"code": "BAD-INPUT", "name": "Name\u0000Suffix"}
    )
    assert response.status_code == 422


def test_reference_search_matches_code_or_label_and_escapes_wildcards(world):
    client = world.client()
    result = client.get("/api/v1/departments", params={"q": "Eng"}).json()
    assert result["total"] == 1 and result["items"][0]["code"] == "ENG"
    assert client.get("/api/v1/departments", params={"q": "%"}).json()["total"] == 0


@pytest.mark.parametrize(
    "path,label,model", [("departments", "name", Department), ("positions", "title", Position)]
)
def test_hr_reference_create_list_update_and_audit(world, path, label, model):
    client = world.client()
    response = client.post(f"/api/v1/{path}", json={"code": " qa-team ", label: " Quality "})
    assert response.status_code == 201
    row = response.json()
    assert row["code"] == "QA-TEAM" and row[label] == "Quality"
    assert row["is_active"] is True and "created_at" in row
    duplicate = client.post(f"/api/v1/{path}", json={"code": "qa-team", label: "Duplicate"})
    assert duplicate.status_code == 409 and duplicate.json()["error"]["code"] == "duplicate_code"
    retired = client.patch(f"/api/v1/{path}/{row['id']}", json={"is_active": False})
    assert retired.status_code == 200 and not retired.json()["is_active"]
    filtered = client.get(f"/api/v1/{path}", params={"is_active": False, "page_size": 1})
    assert filtered.status_code == 200 and filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["id"] == row["id"]
    assert client.patch(f"/api/v1/{path}/{uuid4()}", json={label: "New"}).status_code == 404
    with Session(world.engine) as session:
        assert session.get(model, row["id"]).is_active is False
        assert len(session.scalars(select(AuditLog)).all()) == 2
    assert filtered.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "actor,expected",
    [
        ("hr", {"ENG", "SALES", "UNUSED"}),
        ("manager", {"ENG"}),
        ("alice", {"ENG"}),
        ("unlinked", set()),
    ],
)
def test_reference_lists_use_employee_scope(world, actor, expected):
    response = world.client(actor).get("/api/v1/departments")
    assert response.status_code == 200
    assert {row["code"] for row in response.json()["items"]} == expected
    assert response.json()["total"] == len(expected)


@pytest.mark.parametrize("path,label", [("departments", "name"), ("positions", "title")])
@pytest.mark.parametrize("actor", ["admin", "manager", "alice", "unlinked"])
def test_only_hr_can_write_reference_data(world, path, label, actor):
    response = world.client(actor).post(f"/api/v1/{path}", json={"code": "NEW", label: "New"})
    assert response.status_code == 403
    if actor == "admin":
        assert world.client(actor).get(f"/api/v1/{path}").status_code == 403


@pytest.mark.parametrize(
    "body",
    [
        {"code": "a", "name": "Name"},
        {"code": "GOOD", "name": " "},
        {"code": "BAD/CODE", "name": "Name"},
        {"code": "GOOD", "name": "x" * 201},
    ],
)
def test_reference_validation(world, body):
    assert world.client().post("/api/v1/departments", json=body).status_code == 422


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 101}, {"sort": "password_hash"}])
def test_reference_pagination_validation(world, params):
    assert world.client().get("/api/v1/departments", params=params).status_code == 422


@pytest.mark.parametrize("body", [{}, {"name": None}, {"is_active": None}, {"unknown": True}])
def test_reference_patch_rejects_empty_null_and_unknown(world, body):
    assert (
        world.client()
        .patch(f"/api/v1/departments/{world.departments['ENG']}", json=body)
        .status_code
        == 422
    )


@pytest.mark.parametrize("failure", ["origin", "csrf"])
def test_reference_mutations_reject_forged_requests_without_changes(world, failure):
    client = world.client()
    client.headers.pop("Origin" if failure == "origin" else "X-CSRF-Token")
    assert (
        client.post("/api/v1/departments", json={"code": "SECURE", "name": "Secure"}).status_code
        == 403
    )
    with Session(world.engine) as session:
        assert len(session.scalars(select(Department)).all()) == 3
        assert session.scalars(select(AuditLog)).all() == []


def test_reference_audit_failure_rolls_back(world, monkeypatch):
    def fail(*args, **kwargs):
        raise SQLAlchemyError("internal-private-detail")

    monkeypatch.setattr(AuditWriter, "record", fail)
    response = world.client().patch(
        f"/api/v1/departments/{world.departments['ENG']}", json={"is_active": False}
    )
    assert response.status_code == 500 and "internal-private-detail" not in response.text
    with Session(world.engine) as session:
        assert session.get(Department, world.departments["ENG"]).is_active
