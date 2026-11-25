import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cli.seed_continuous_demo import ContinuousDemo, seed_continuous_demo
from app.cli.seed_demo import DemoConflict
from app.models import AuditLog, AuthSession, EmployeeKPI, User
from app.modules.work_management.models import EvidenceSubmission, WorkItem, WorkPlan


def test_continuous_story_idempotent_and_does_not_fabricate_actual(auth_engine):
    assert seed_continuous_demo(auth_engine)
    with Session(auth_engine) as session:
        assert session.scalar(select(func.count()).select_from(WorkPlan)) == 2
        assert session.scalar(select(func.count()).select_from(EvidenceSubmission)) == 2
        rows = session.scalars(select(WorkItem)).all()
        assert {w.status for w in rows} == {"TODO", "IN_PROGRESS", "CHANGES_REQUESTED", "ACCEPTED"}
        assert sum(w.blocked for w in rows) == 1
        assert session.scalar(select(func.count()).select_from(EmployeeKPI)) == 0
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuthSession)
                .where(AuthSession.revoked_at.is_(None))
            )
            == 0
        )
        before = session.scalar(select(func.count()).select_from(AuditLog))
    assert not seed_continuous_demo(auth_engine)
    with Session(auth_engine) as session:
        assert session.scalar(select(func.count()).select_from(AuditLog)) == before


def test_continuous_demo_refuses_existing_accounts(world):
    with pytest.raises(DemoConflict):
        seed_continuous_demo(world.engine)


def test_continuous_demo_late_failure_rolls_back_every_table(auth_engine, monkeypatch):
    original = ContinuousDemo.story

    def fail(self):
        original(self)
        raise RuntimeError("late failure")

    monkeypatch.setattr(ContinuousDemo, "story", fail)
    with pytest.raises(RuntimeError):
        seed_continuous_demo(auth_engine)
    with Session(auth_engine) as session:
        for table in (User, WorkItem, WorkPlan, AuditLog):
            assert session.scalar(select(func.count()).select_from(table)) == 0


def test_upgrade_from_legacy_preserves_existing_columns(auth_engine):
    import hashlib
    import json

    from alembic.config import Config
    from sqlalchemy import inspect, text

    from alembic import command
    from app.cli.seed_demo import seed_demo

    from .conftest import ALEMBIC_INI

    assert seed_demo(auth_engine, "1")
    config = Config(str(ALEMBIC_INI))
    command.downgrade(config, "20261114_0010")
    columns = {}
    with auth_engine.connect() as connection:
        inspector = inspect(connection)
        for table in inspector.get_table_names():
            if table != "alembic_version":
                columns[table] = [c["name"] for c in inspector.get_columns(table)]

    def fingerprint():
        records = {}
        with auth_engine.connect() as connection:
            for table, names in columns.items():
                fields = ",".join(f'"{name}"' for name in names)
                records[table] = sorted(
                    json.dumps(dict(row), sort_keys=True, default=str)
                    for row in connection.execute(
                        text(f'SELECT {fields} FROM "{table}"')
                    ).mappings()
                )
        return hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()

    before = fingerprint()
    command.upgrade(config, "head")
    assert fingerprint() == before
    with auth_engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM review_cycles "
                    "WHERE workflow_mode <> 'LEGACY' OR workflow_schedule IS NOT NULL"
                )
            )
            == 0
        )
