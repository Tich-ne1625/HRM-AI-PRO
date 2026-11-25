import hashlib
import json

from alembic.config import Config
from sqlalchemy import inspect, text

from alembic import command

from .conftest import ALEMBIC_INI
from .test_ai_workflows import ai_world as ai_world


def test_new_limiter_migration_roundtrip_preserves_all_previous_records(ai_world):
    world, _, _, path, body, _ = ai_world
    assert world.client().post(path, json=body).status_code == 201

    def fingerprint():
        data = {}
        with world.engine.connect() as conn:
            # This round trip targets 0007. Later, intentionally dropped tables must
            # not change its fingerprint merely by appearing/disappearing empty.
            original_tables = {
                "users",
                "auth_sessions",
                "audit_logs",
                "departments",
                "positions",
                "employees",
                "system_config",
                "review_cycles",
                "cycle_participants",
                "kpi_definitions",
                "employee_kpis",
                "feedback_assignments",
                "feedback",
                "performance_reviews",
                "performance_review_revisions",
                "ai_analyses",
            }
            assert original_tables <= set(inspect(conn).get_table_names())
            tables = sorted(original_tables)
            for table in tables:
                rows = [dict(r) for r in conn.execute(text(f'SELECT * FROM "{table}"')).mappings()]
                if table == "review_cycles":
                    for row in rows:
                        row.pop("workflow_mode", None)
                        row.pop("workflow_schedule", None)
                data[table] = sorted(json.dumps(r, sort_keys=True, default=str) for r in rows)
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    before = fingerprint()
    config = Config(str(ALEMBIC_INI))
    command.downgrade(config, "20261022_0007")
    assert fingerprint() == before
    command.upgrade(config, "head")
    assert fingerprint() == before
    with world.engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM auth_login_limits")) == 0
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "20261125_0012"
