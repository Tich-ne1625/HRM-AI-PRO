from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import AuditLog, Employee, UserRole
from app.modules.audit.service import AuditWriter


@pytest.mark.parametrize("kind", ["department", "employee"])
def test_creation_audit_failure_leaves_no_partial_organization_row(world, monkeypatch, kind):
    def fail(*args, **kwargs):
        raise SQLAlchemyError("private-create-error")

    monkeypatch.setattr(AuditWriter, "record", fail)
    client = world.client()
    response = (
        client.post("/api/v1/departments", json={"code": "ROLLBACK", "name": "Rollback"})
        if kind == "department"
        else client.post("/api/v1/employees", json=world.employee_payload())
    )
    assert response.status_code == 500
    assert "private-create-error" not in response.text
    with Session(world.engine) as session:
        from app.models import Department

        if kind == "department":
            assert session.scalar(select(Department).where(Department.code == "ROLLBACK")) is None
        else:
            assert (
                session.scalar(select(Employee).where(Employee.employee_code == "NEW-01")) is None
            )


@pytest.mark.parametrize(
    "actor,expected",
    [
        ("hr", {"manager", "other", "alice", "bob", "indirect"}),
        ("manager", {"manager", "alice"}),
        ("alice", {"alice"}),
        ("unlinked", set()),
    ],
)
def test_employee_list_and_detail_apply_same_sql_scope(world, actor, expected):
    client = world.client(actor)
    response = client.get("/api/v1/employees")
    assert response.status_code == 200
    assert {row["id"] for row in response.json()["items"]} == {
        world.employees[name] for name in expected
    }
    assert response.json()["total"] == len(expected)
    for name, identifier in world.employees.items():
        assert client.get(f"/api/v1/employees/{identifier}").status_code == (
            200 if name in expected else 404
        )
    assert client.get(f"/api/v1/employees/{uuid4()}").status_code == 404
    assert "password_hash" not in response.text and "token_hash" not in response.text


def test_hr_create_update_link_unlink_and_me_identity(world):
    client = world.client()
    response = client.post(
        "/api/v1/employees", json=world.employee_payload(user_id=world.users["spare"])
    )
    assert response.status_code == 201
    row = response.json()
    assert row["department_name"] == "Eng" and row["position_title"] == "Dev"
    assert world.client("spare").get("/api/v1/auth/me").json()["employee_id"] == row["id"]
    changed = client.patch(
        f"/api/v1/employees/{row['id']}",
        json={
            "manager_id": world.employees["manager"],
            "employment_status": "INACTIVE",
        },
    )
    assert changed.status_code == 200 and changed.json()["manager_name"] == "Manager"
    assert client.patch(f"/api/v1/employees/{row['id']}", json={"user_id": None}).status_code == 200
    assert world.client("spare").get("/api/v1/auth/me").json()["employee_id"] is None
    with Session(world.engine) as session:
        assert {a.action for a in session.scalars(select(AuditLog))} >= {
            "employee.created",
            "employee.updated",
        }


@pytest.mark.parametrize("actor", ["admin", "manager", "alice"])
def test_non_hr_employee_writes_denied(world, actor):
    client = world.client(actor)
    assert client.post("/api/v1/employees", json=world.employee_payload()).status_code == 403
    assert (
        client.patch(
            f"/api/v1/employees/{world.employees['alice']}", json={"display_name": "Changed"}
        ).status_code
        == 403
    )
    if actor == "admin":
        assert client.get("/api/v1/employees").status_code == 403


@pytest.mark.parametrize(
    "overrides,status,code",
    [
        ({"department_id": str(uuid4())}, 404, "reference_not_found"),
        ({"position_id": str(uuid4())}, 404, "reference_not_found"),
        ({"manager_id": str(uuid4())}, 404, "employee_not_found"),
        ({"user_id": str(uuid4())}, 404, "user_not_found"),
        ({"user_id": "linked"}, 409, "user_already_linked"),
        ({"employee_code": "EMP-ALICE"}, 409, "employee_code_already_exists"),
    ],
)
def test_employee_reference_errors_are_stable(world, overrides, status, code):
    if overrides.get("user_id") == "linked":
        overrides = {"user_id": world.users["alice"]}
    response = world.client().post("/api/v1/employees", json=world.employee_payload(**overrides))
    assert response.status_code == status and response.json()["error"]["code"] == code


def test_retired_references_remain_readable_but_cannot_be_newly_assigned(world):
    client = world.client()
    assert (
        client.patch(
            f"/api/v1/departments/{world.departments['ENG']}", json={"is_active": False}
        ).status_code
        == 200
    )
    assert (
        world.client("alice").get(f"/api/v1/employees/{world.employees['alice']}").status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/employees/{world.employees['alice']}", json={"display_name": "Alice Updated"}
        ).status_code
        == 200
    )
    response = client.post("/api/v1/employees", json=world.employee_payload())
    assert response.status_code == 409 and response.json()["error"]["code"] == "reference_inactive"


@pytest.mark.parametrize(
    "employee,manager", [("manager", "manager"), ("manager", "alice"), ("manager", "indirect")]
)
def test_reporting_cycles_are_rejected(world, employee, manager):
    response = world.client().patch(
        f"/api/v1/employees/{world.employees[employee]}",
        json={"manager_id": world.employees[manager]},
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "reporting_cycle"


def test_manager_scope_changes_immediately_after_transfer(world):
    client = world.client("manager")
    assert client.get(f"/api/v1/employees/{world.employees['alice']}").status_code == 200
    assert (
        world.client()
        .patch(
            f"/api/v1/employees/{world.employees['alice']}",
            json={"manager_id": world.employees["other"]},
        )
        .status_code
        == 200
    )
    assert client.get(f"/api/v1/employees/{world.employees['alice']}").status_code == 404
    assert (
        world.client("other").get(f"/api/v1/employees/{world.employees['alice']}").status_code
        == 200
    )


@pytest.mark.parametrize(
    "params",
    [{"page": 0}, {"page_size": 101}, {"sort": "password_hash"}, {"employment_status": "UNKNOWN"}],
)
def test_employee_query_validation(world, params):
    assert world.client().get("/api/v1/employees", params=params).status_code == 422


def test_filters_search_count_and_pagination_stay_scoped(world):
    client = world.client("manager")
    assert (
        client.get(
            "/api/v1/employees", params={"department_id": world.departments["SALES"]}
        ).json()["total"]
        == 0
    )
    filtered = client.get("/api/v1/employees", params={"q": "Alice", "page_size": 1}).json()
    assert filtered["total"] == 1 and filtered["items"][0]["id"] == world.employees["alice"]
    assert client.get("/api/v1/employees", params={"q": "%"}).json()["total"] == 0


def test_hr_exact_account_lookup_is_bounded_and_sanitized(world):
    client = world.client()
    response = client.get("/api/v1/employees/linkable-users", params={"email": "SPARE@EXAMPLE.com"})
    assert response.status_code == 200
    assert response.json()["items"] == [
        {
            "id": world.users["spare"],
            "email": "spare@example.com",
            "is_active": True,
            "employee_id": None,
        }
    ]
    assert client.get("/api/v1/employees/linkable-users").status_code == 422
    assert (
        client.get(
            "/api/v1/employees/linkable-users", params={"email": "missing@example.com"}
        ).json()["items"]
        == []
    )
    assert (
        world.client("manager")
        .get("/api/v1/employees/linkable-users", params={"email": "spare@example.com"})
        .status_code
        == 403
    )


@pytest.mark.parametrize(
    "body", [{}, {"display_name": None}, {"department_id": None}, {"unknown": True}]
)
def test_employee_update_rejects_empty_unknown_or_null_required_fields(world, body):
    assert (
        world.client().patch(f"/api/v1/employees/{world.employees['alice']}", json=body).status_code
        == 422
    )


def test_employee_audit_failure_rolls_back_link_and_reporting_change(world, monkeypatch):
    def fail(*args, **kwargs):
        raise SQLAlchemyError("private-db-error")

    monkeypatch.setattr(AuditWriter, "record", fail)
    response = world.client().patch(
        f"/api/v1/employees/{world.employees['alice']}",
        json={"user_id": world.users["spare"], "manager_id": world.employees["other"]},
    )
    assert response.status_code == 500 and "private-db-error" not in response.text
    with Session(world.engine) as session:
        alice = session.get(Employee, world.employees["alice"])
        assert str(alice.user_id) == world.users["alice"]
        assert str(alice.manager_id) == world.employees["manager"]


def test_hr_cannot_mutate_after_current_role_is_removed(world):
    with Session(world.engine) as session, session.begin():
        from app.models import User

        session.get(User, world.users["hr"]).role = UserRole.EMPLOYEE
    assert (
        world.client().post("/api/v1/employees", json=world.employee_payload()).status_code == 403
    )


def test_unchanged_retired_reference_is_not_treated_as_a_new_assignment(world):
    client = world.client()
    assert (
        client.patch(
            f"/api/v1/departments/{world.departments['ENG']}", json={"is_active": False}
        ).status_code
        == 200
    )
    response = client.patch(
        f"/api/v1/employees/{world.employees['alice']}",
        json={
            "department_id": world.departments["ENG"],
            "display_name": "Changed Name",
        },
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "Changed Name"


@pytest.mark.parametrize("failure", ["origin", "csrf", "cross_family"])
def test_employee_mutations_require_origin_and_family_bound_csrf(world, failure):
    client = world.client()
    if failure == "cross_family":
        token = world.cookies["manager"]["insighthr_csrf"]
        client.cookies.set("insighthr_csrf", token)
        client.headers["X-CSRF-Token"] = token
    else:
        client.headers.pop("Origin" if failure == "origin" else "X-CSRF-Token")
    assert (
        client.patch(
            f"/api/v1/employees/{world.employees['alice']}", json={"display_name": "Forged"}
        ).status_code
        == 403
    )
    with Session(world.engine) as session:
        assert session.get(Employee, world.employees["alice"]).display_name == "Alice"


def test_inactive_manager_cannot_be_newly_selected(world):
    client = world.client()
    assert (
        client.patch(
            f"/api/v1/employees/{world.employees['other']}", json={"employment_status": "INACTIVE"}
        ).status_code
        == 200
    )
    response = client.post(
        "/api/v1/employees",
        json=world.employee_payload(
            manager_id=world.employees["other"],
        ),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "manager_inactive"
