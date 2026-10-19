from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command

from .conftest import ALEMBIC_INI


def test_organization_revision_and_metadata_match(auth_engine):
    from app.models import Department, Employee, Position

    assert ScriptDirectory.from_config(Config(str(ALEMBIC_INI))).get_heads() == ["20261019_0003"]
    assert {Department.__tablename__, Employee.__tablename__, Position.__tablename__} == {
        "departments",
        "employees",
        "positions",
    }
    inspector = inspect(auth_engine)
    for table in ("departments", "positions", "employees"):
        columns = {column["name"]: column for column in inspector.get_columns(table)}
        assert str(columns["id"]["type"]) == "UUID"
        assert all(columns[field]["type"].timezone for field in ("created_at", "updated_at"))
    assert {index["name"] for index in inspector.get_indexes("employees")} >= {
        "ix_employees_department_id",
        "ix_employees_position_id",
        "ix_employees_manager_id",
    }
    command.check(Config(str(ALEMBIC_INI)))


def test_organization_database_constraints_and_foreign_keys(auth_engine):
    department, position, first, user = [uuid4() for _ in range(4)]
    with auth_engine.begin() as connection:
        connection.execute(
            text("INSERT INTO departments (id, code, name) VALUES (:id, 'ENG', 'Engineering')"),
            {"id": department},
        )
        connection.execute(
            text("INSERT INTO positions (id, code, title) VALUES (:id, 'DEV', 'Developer')"),
            {"id": position},
        )
        connection.execute(
            text(
                "INSERT INTO users (id, email, password_hash, role) "
                "VALUES (:id, 'linked@example.com', 'hash', 'EMPLOYEE')"
            ),
            {"id": user},
        )
    insert = text(
        "INSERT INTO employees (id, employee_code, display_name, department_id, "
        "position_id, user_id, manager_id, employment_status) "
        "VALUES (:id, :code, :name, :department, :position, :user, :manager, :status)"
    )
    valid = {
        "id": first,
        "code": "EMP-01",
        "name": "First",
        "department": department,
        "position": position,
        "user": user,
        "manager": None,
        "status": "ACTIVE",
    }
    with auth_engine.begin() as connection:
        connection.execute(insert, valid)
    for change in (
        {"id": uuid4()},
        {"id": uuid4(), "code": "EMP-02"},
        {"id": uuid4(), "code": "lower", "user": None},
        {"id": uuid4(), "code": "EMP-03", "user": None, "status": "UNKNOWN"},
        {"id": uuid4(), "code": "EMP-04", "user": None, "name": " "},
        {"id": uuid4(), "code": "EMP-05", "user": None, "department": uuid4()},
    ):
        with pytest.raises(IntegrityError), auth_engine.begin() as connection:
            connection.execute(insert, {**valid, **change})
    with pytest.raises(IntegrityError), auth_engine.begin() as connection:
        connection.execute(text("UPDATE employees SET manager_id=id WHERE id=:id"), {"id": first})
    for table, identifier in (
        ("users", user),
        ("departments", department),
        ("positions", position),
    ):
        with pytest.raises(IntegrityError), auth_engine.begin() as connection:
            connection.execute(text(f"DELETE FROM {table} WHERE id=:id"), {"id": identifier})


def test_organization_downgrade_preserves_auth_schema_and_upgrade(auth_engine):
    config = Config(str(ALEMBIC_INI))
    command.downgrade(config, "20261003_0002")
    assert not {"departments", "positions", "employees"} & set(
        inspect(auth_engine).get_table_names()
    )
    assert {"users", "auth_sessions", "audit_logs"} <= set(inspect(auth_engine).get_table_names())
    command.upgrade(config, "head")
    assert "employees" in inspect(auth_engine).get_table_names()
