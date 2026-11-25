import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.cli.seed_continuous_demo import seed_continuous_demo
from app.cli.seed_demo import DemoConflict
from app.cli.seed_progress_demo import ProgressDemo, seed_progress_demo
from app.models import AuditLog, AuthSession, EmployeeKPI, User, WorkPlan
from app.modules.progress.models import Checkin, Measurement, ProgressSnapshot


def test_progress_story_uses_real_services_and_is_idempotent(auth_engine):
    assert seed_progress_demo(auth_engine)
    with Session(auth_engine) as session:
        snapshot = session.scalar(
            select(ProgressSnapshot).order_by(ProgressSnapshot.version.desc()).limit(1)
        )
        assert snapshot is not None
        assert {g["method"]: g["actual"] for g in snapshot.data["goals"]} == {
            "SUM": "5.0000",
            "RATIO": "83.33",
            "MILESTONE": "30.00",
            "LAST": "50.0000",
        }
        assert (
            session.scalar(
                select(func.count()).select_from(Measurement).where(Measurement.suspended)
            )
            == 1
        )
        assert session.scalar(select(func.count()).select_from(Checkin)) == 2
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
    assert not seed_progress_demo(auth_engine)
    with Session(auth_engine) as session:
        assert session.scalar(select(func.count()).select_from(AuditLog)) == before


def test_progress_demo_refuses_existing_company(world):
    with pytest.raises(DemoConflict):
        seed_progress_demo(world.engine)


def test_progress_demo_late_failure_is_atomic(auth_engine, monkeypatch):
    original = ProgressDemo.story

    def fail(self):
        original(self)
        raise RuntimeError("late demo failure")

    monkeypatch.setattr(ProgressDemo, "story", fail)
    with pytest.raises(RuntimeError):
        seed_progress_demo(auth_engine)
    with Session(auth_engine) as session:
        for table in (User, WorkPlan, Measurement, ProgressSnapshot, Checkin, AuditLog):
            assert session.scalar(select(func.count()).select_from(table)) == 0


def test_phase11_upgrade_preserves_existing_columns(auth_engine):
    import json

    from alembic.config import Config
    from sqlalchemy import inspect

    from alembic import command

    from .conftest import ALEMBIC_INI

    assert seed_continuous_demo(auth_engine)
    config = Config(str(ALEMBIC_INI))
    command.downgrade(config, "20261125_0011")
    with auth_engine.connect() as connection:
        inspector = inspect(connection)
        columns = {
            t: [c["name"] for c in inspector.get_columns(t)]
            for t in inspector.get_table_names()
            if t != "alembic_version"
        }

    def fingerprint():
        with auth_engine.connect() as connection:
            return {
                table: sorted(
                    json.dumps(dict(r), sort_keys=True, default=str)
                    for r in connection.execute(
                        text("SELECT " + ",".join(f'"{c}"' for c in names) + f' FROM "{table}"')
                    ).mappings()
                )
                for table, names in columns.items()
            }

    before = fingerprint()
    command.upgrade(config, "head")
    assert fingerprint() == before
    with Session(auth_engine) as session:
        assert session.scalar(select(func.count()).select_from(WorkPlan)) == 2
        assert session.scalar(select(func.count()).select_from(Measurement)) == 0
