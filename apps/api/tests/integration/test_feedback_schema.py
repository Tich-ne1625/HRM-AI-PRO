from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command

from .conftest import ALEMBIC_INI
from .test_feedback_workflows import create_assignment, feedback_world


def test_feedback_migration_metadata_and_no_backfill(world):
    assert ScriptDirectory.from_config(Config(str(ALEMBIC_INI))).get_heads() == ["20261020_0005"]
    assert {"feedback", "feedback_assignments"} <= set(inspect(world.engine).get_table_names())
    command.check(Config(str(ALEMBIC_INI)))
    feedback_world(world)
    with world.engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM feedback_assignments")) == 0
    command.downgrade(Config(str(ALEMBIC_INI)), "20261020_0004")
    with world.engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM cycle_participants")) == 1
        users = connection.scalar(text("SELECT count(*) FROM users"))
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    with world.engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM users")) == users
        assert connection.scalar(text("SELECT count(*) FROM feedback_assignments")) == 0
        assert connection.scalar(text("SELECT count(*) FROM cycle_participants")) == 1


def test_database_constraints_reject_invalid_history(world):
    _, participant = feedback_world(world)
    row = create_assignment(world, participant).json()
    for sql, params in (
        ("UPDATE feedback_assignments SET version=0", {}),
        ("UPDATE feedback_assignments SET required=false", {}),
        ("UPDATE feedback_assignments SET eligibility_snapshot='[]'::jsonb", {}),
        ("UPDATE feedback_assignments SET status='INVALID'", {}),
        ("UPDATE feedback_assignments SET relationship='INVALID'", {}),
        ("DELETE FROM cycle_participants WHERE id=:id", {"id": participant["id"]}),
        ("DELETE FROM users WHERE id=:id", {"id": world.users["alice"]}),
        (
            "INSERT INTO feedback(id,assignment_id,rating) VALUES (:id,:a,6)",
            {"id": uuid4(), "a": row["id"]},
        ),
        (
            "INSERT INTO feedback(id,assignment_id,rating) VALUES (:id,:a,0)",
            {"id": uuid4(), "a": row["id"]},
        ),
    ):
        with pytest.raises(IntegrityError), world.engine.begin() as connection:
            connection.execute(text(sql), params)
    with world.engine.begin() as connection:
        connection.execute(
            text("INSERT INTO feedback(id,assignment_id,rating) VALUES (:id,:a,4)"),
            {"id": uuid4(), "a": row["id"]},
        )
    with pytest.raises(IntegrityError), world.engine.begin() as connection:
        connection.execute(
            text("INSERT INTO feedback(id,assignment_id,rating) VALUES (:id,:a,4)"),
            {"id": uuid4(), "a": row["id"]},
        )
    with pytest.raises(IntegrityError), world.engine.begin() as connection:
        connection.execute(text("DELETE FROM feedback_assignments WHERE id=:id"), {"id": row["id"]})


def test_assignment_full_and_partial_uniqueness_including_cancelled(world):
    _, participant = feedback_world(world)
    row = create_assignment(world, participant).json()
    duplicate = (
        "INSERT INTO feedback_assignments(id,participant_id,reviewer_id,reviewer_employee_id,"
        "relationship,required,status,eligibility_snapshot) "
        "SELECT :new,participant_id,reviewer_id,reviewer_employee_id,relationship,required,"
        "'CANCELLED',eligibility_snapshot FROM feedback_assignments WHERE id=:id"
    )
    with pytest.raises(IntegrityError), world.engine.begin() as connection:
        connection.execute(text(duplicate), {"new": uuid4(), "id": row["id"]})
    peer = create_assignment(world, {**participant, "evidence_version": 3}, "bob", "PEER").json()
    with pytest.raises(IntegrityError), world.engine.begin() as connection:
        connection.execute(
            text("UPDATE feedback_assignments SET relationship='SELF' WHERE id=:id"),
            {"id": peer["id"]},
        )


def test_phase4_upgrade_downgrade_preserves_account_kpi_and_actual(world):
    from .test_employee_kpis import allocation_world, replace_body

    _, definition, _, path = allocation_world(world)
    allocation = world.client().put(path, json=replace_body(definition)).json()
    assert (
        world.client()
        .patch(
            f"/api/v1/employee-kpis/{allocation['items'][0]['id']}",
            json={"expected_evidence_version": 3, "actual": "0.0000"},
        )
        .status_code
        == 200
    )
    config = Config(str(ALEMBIC_INI))
    sql = "SELECT count(*),sum(actual),sum(weight) FROM employee_kpis"
    with world.engine.connect() as connection:
        before = connection.execute(text(sql)).one()
        users = connection.scalar(text("SELECT count(*) FROM users"))
    command.downgrade(config, "20261020_0004")
    command.upgrade(config, "head")
    with world.engine.connect() as connection:
        assert connection.execute(text(sql)).one() == before
        assert connection.scalar(text("SELECT count(*) FROM users")) == users
        assert connection.scalar(text("SELECT count(*) FROM feedback_assignments")) == 0
