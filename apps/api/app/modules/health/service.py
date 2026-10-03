from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

DatabaseStatus = Literal["ok", "unavailable"]
MigrationStatus = Literal["current", "missing", "pending", "unavailable"]


@dataclass(frozen=True, slots=True)
class ReadinessResult:
    is_ready: bool
    database: DatabaseStatus
    migrations: MigrationStatus

    @classmethod
    def ready(cls) -> ReadinessResult:
        return cls(is_ready=True, database="ok", migrations="current")

    @classmethod
    def not_ready(
        cls,
        *,
        database: DatabaseStatus,
        migrations: MigrationStatus,
    ) -> ReadinessResult:
        return cls(is_ready=False, database=database, migrations=migrations)


class ReadinessService:
    def __init__(self, engine: Engine, alembic_ini_path: Path) -> None:
        self._engine = engine
        self._expected_head = _load_expected_head(alembic_ini_path)

    def check(self) -> ReadinessResult:
        try:
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                if not inspect(connection).has_table("alembic_version"):
                    return ReadinessResult.not_ready(database="ok", migrations="missing")

                current_revision = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one_or_none()
        except SQLAlchemyError:
            return ReadinessResult.not_ready(
                database="unavailable",
                migrations="unavailable",
            )

        if current_revision != self._expected_head:
            return ReadinessResult.not_ready(database="ok", migrations="pending")
        return ReadinessResult.ready()


def _load_expected_head(alembic_ini_path: Path) -> str:
    config = Config(str(alembic_ini_path))
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    if len(heads) != 1:
        raise RuntimeError("InsightHR requires exactly one Alembic head revision")
    return heads[0]

