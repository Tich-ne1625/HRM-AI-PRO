from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command

from .conftest import ALEMBIC_INI

pytestmark = pytest.mark.integration


def test_phase4_schema_metadata_and_singleton(auth_engine):
    from app.models import CycleParticipant, EmployeeKPI, KPIDefinition, ReviewCycle, SystemConfig

    assert {
        m.__tablename__
        for m in (
            CycleParticipant,
            EmployeeKPI,
            KPIDefinition,
            ReviewCycle,
            SystemConfig,
        )
    } <= set(inspect(auth_engine).get_table_names())
    scripts = ScriptDirectory.from_config(Config(str(ALEMBIC_INI)))
    assert scripts.get_heads() == ["20261022_0007"]
    with Session(auth_engine) as session:
        config = session.scalars(select(SystemConfig)).one()
        assert config.id == 1 and config.version == 1
        assert config.scoring_policy["kpi_weight"] == "70.00"
    with pytest.raises(IntegrityError), auth_engine.begin() as connection:
        connection.execute(text("INSERT INTO system_config (id, scoring_policy) VALUES (2, '{}')"))
    command.check(Config(str(ALEMBIC_INI)))


def test_cycle_constraints_and_single_active(auth_engine):
    from app.models import CycleStatus, ReviewCycle

    def cycle(**kw):
        return ReviewCycle(
            name="Q4", start_date=date(2026, 10, 1), end_date=date(2026, 12, 31), **kw
        )

    def commit(row):
        with Session(auth_engine) as session, session.begin():
            session.add(row)

    commit(cycle())
    for changes in (
        {"version": 0},
        {"status": CycleStatus.ACTIVE},
        {"scoring_policy_snapshot": {}},
        {"name": " "},
    ):
        with pytest.raises(IntegrityError):
            commit(
                cycle(**changes)
                if "name" not in changes
                else ReviewCycle(name=" ", start_date=date(2026, 1, 1), end_date=date(2026, 2, 1))
            )
    from datetime import UTC, datetime

    active = {
        "status": CycleStatus.ACTIVE,
        "scoring_policy_snapshot": {"schema_version": 1},
        "policy_source_version": 1,
        "activated_at": datetime.now(UTC),
    }
    commit(cycle(**active))
    with pytest.raises(IntegrityError):
        commit(cycle(**active))
    with pytest.raises(IntegrityError), auth_engine.begin() as connection:
        connection.execute(text("UPDATE review_cycles SET end_date=start_date - 1"))


def test_participant_and_assignment_constraints_and_restrict(world):
    from app.models import CycleParticipant, EmployeeKPI, KPIDefinition, ReviewCycle
    from app.modules.kpis.models import KPIDirection

    cycle_id, participant_id, definition_id = uuid4(), uuid4(), uuid4()
    with Session(world.engine) as session, session.begin():
        session.add(
            ReviewCycle(
                id=cycle_id, name="Q4", start_date=date(2026, 10, 1), end_date=date(2026, 12, 31)
            )
        )
        session.flush()
        session.add(
            CycleParticipant(
                id=participant_id, cycle_id=cycle_id, employee_id=world.employees["alice"]
            )
        )
        session.add(
            KPIDefinition(
                id=definition_id,
                code="SALES",
                name="Sales",
                unit="VND",
                direction=KPIDirection.HIGHER_IS_BETTER,
            )
        )
        session.flush()
        session.add(
            EmployeeKPI(
                participant_id=participant_id,
                definition_id=definition_id,
                definition_snapshot={},
                target=Decimal("1"),
                weight=Decimal("100"),
            )
        )
    for sql, params in (
        (
            "INSERT INTO cycle_participants (id,cycle_id,employee_id) VALUES (:id,:c,:e)",
            {"id": uuid4(), "c": cycle_id, "e": world.employees["alice"]},
        ),
        ("UPDATE cycle_participants SET evidence_version=0", {}),
        ("UPDATE employee_kpis SET target=0", {}),
        ("UPDATE employee_kpis SET actual=-1", {}),
        ("UPDATE employee_kpis SET weight=101", {}),
        ("DELETE FROM kpi_definitions WHERE id=:id", {"id": definition_id}),
        ("DELETE FROM cycle_participants WHERE id=:id", {"id": participant_id}),
        ("DELETE FROM review_cycles WHERE id=:id", {"id": cycle_id}),
    ):
        with pytest.raises(IntegrityError), world.engine.begin() as connection:
            connection.execute(text(sql), params)


def test_upgrade_preserves_phase3_data_and_downgrade(world):
    config = Config(str(ALEMBIC_INI))
    command.downgrade(config, "20261019_0003")
    assert not {"review_cycles", "employee_kpis", "system_config"} & set(
        inspect(world.engine).get_table_names()
    )
    with world.engine.connect() as connection:
        count = connection.scalar(text("SELECT count(*) FROM employees"))
    command.upgrade(config, "head")
    with world.engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM employees")) == count
        assert connection.scalar(text("SELECT count(*) FROM system_config")) == 1
