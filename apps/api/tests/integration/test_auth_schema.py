from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import DataError, IntegrityError

from alembic import command

from .conftest import ALEMBIC_INI

pytestmark = pytest.mark.integration


def test_authentication_revision_remains_in_the_single_migration_chain() -> None:
    scripts = ScriptDirectory.from_config(Config(str(ALEMBIC_INI)))
    assert len(scripts.get_heads()) == 1
    assert "20261003_0002" in {revision.revision for revision in scripts.walk_revisions()}


def test_model_aggregation_matches_the_migrated_schema(auth_engine: Engine) -> None:
    from app import models
    from app.core.database import metadata

    assert {
        model.__table__.name for model in (models.User, models.AuthSession, models.AuditLog)
    } == {
        "users",
        "auth_sessions",
        "audit_logs",
    }
    assert {"users", "auth_sessions", "audit_logs"} <= metadata.tables.keys()
    command.check(Config(str(ALEMBIC_INI)))


def test_migration_has_typed_required_columns(auth_engine: Engine) -> None:
    inspector = inspect(auth_engine)
    expected = {
        "users": {"id", "email", "password_hash", "role", "is_active", "created_at", "updated_at"},
        "auth_sessions": {
            "id",
            "family_id",
            "user_id",
            "token_hash",
            "csrf_hash",
            "expires_at",
            "consumed_at",
            "revoked_at",
            "replacement_id",
        },
        "audit_logs": {
            "id",
            "actor_id",
            "action",
            "entity_type",
            "entity_id",
            "request_id",
            "created_at",
            "metadata",
        },
    }
    for table, names in expected.items():
        columns = {column["name"]: column for column in inspector.get_columns(table)}
        assert set(columns) == names
        assert str(columns["id"]["type"]) == "UUID"
        for name in names & {"created_at", "updated_at", "expires_at", "consumed_at", "revoked_at"}:
            assert columns[name]["type"].timezone is True
    audit_columns = {column["name"]: column for column in inspector.get_columns("audit_logs")}
    assert isinstance(audit_columns["metadata"]["type"], JSONB)


def test_unique_normalized_email_and_valid_role_enforced(auth_engine: Engine) -> None:
    insert = text(
        "INSERT INTO users (id, email, password_hash, role) VALUES (:id, :email, 'hash', :role)"
    )
    with auth_engine.begin() as connection:
        connection.execute(insert, {"id": uuid4(), "email": "admin@example.com", "role": "ADMIN"})
    for email, role in (
        ("admin@example.com", "ADMIN"),
        ("ADMIN@example.com", "ADMIN"),
        ("other@example.com", "OWNER"),
    ):
        with pytest.raises(IntegrityError), auth_engine.begin() as connection:
            connection.execute(insert, {"id": uuid4(), "email": email, "role": role})
    with pytest.raises(DataError), auth_engine.begin() as connection:
        connection.execute(insert, {"id": uuid4(), "email": "x" * 255, "role": "HR"})
    with auth_engine.connect() as connection:
        row = connection.execute(text("SELECT is_active, created_at, updated_at FROM users")).one()
        assert row.is_active is True
        assert row.created_at.utcoffset() == timedelta(0)
        assert row.updated_at.utcoffset() == timedelta(0)


def test_security_foreign_keys_restrict_deletion(auth_engine: Engine) -> None:
    user_id, first_id, replacement_id = uuid4(), uuid4(), uuid4()
    with auth_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, email, password_hash, role) "
                "VALUES (:id, 'user@example.com', 'hash', 'EMPLOYEE')"
            ),
            {"id": user_id},
        )
        for session_id, token_hash in ((replacement_id, "a" * 64), (first_id, "b" * 64)):
            connection.execute(
                text(
                    "INSERT INTO auth_sessions "
                    "(id, family_id, user_id, token_hash, csrf_hash, expires_at) "
                    "VALUES (:id, :family, :user, :token, :csrf, :expiry)"
                ),
                {
                    "id": session_id,
                    "family": first_id,
                    "user": user_id,
                    "token": token_hash,
                    "csrf": "c" * 64,
                    "expiry": datetime.now(UTC),
                },
            )
        connection.execute(
            text("UPDATE auth_sessions SET replacement_id = :replacement WHERE id = :first"),
            {"replacement": replacement_id, "first": first_id},
        )
        connection.execute(
            text(
                "INSERT INTO audit_logs (id, actor_id, action, entity_type, entity_id, request_id) "
                "VALUES (:id, :actor, 'test.action', 'user', :entity, 'request-1')"
            ),
            {"id": uuid4(), "actor": user_id, "entity": str(user_id)},
        )
    for statement, identifier in (
        ("DELETE FROM users WHERE id = :id", user_id),
        ("DELETE FROM auth_sessions WHERE id = :id", replacement_id),
    ):
        with pytest.raises(IntegrityError), auth_engine.begin() as connection:
            connection.execute(text(statement), {"id": identifier})
    with auth_engine.begin() as connection:
        connection.execute(text("DELETE FROM auth_sessions WHERE id = :id"), {"id": first_id})
        connection.execute(text("DELETE FROM auth_sessions WHERE id = :id"), {"id": replacement_id})
    with pytest.raises(IntegrityError), auth_engine.begin() as connection:
        connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})


def test_session_unique_token_and_nullable_lifecycle(auth_engine: Engine) -> None:
    user_id = uuid4()
    with auth_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, email, password_hash, role) "
                "VALUES (:id, 'user@example.com', 'hash', 'MANAGER')"
            ),
            {"id": user_id},
        )
        connection.execute(
            text(
                "INSERT INTO auth_sessions "
                "(id, family_id, user_id, token_hash, csrf_hash, expires_at) "
                "VALUES (:id, :family, :user, :token, :csrf, :expiry)"
            ),
            {
                "id": uuid4(),
                "family": uuid4(),
                "user": user_id,
                "token": "a" * 64,
                "csrf": "b" * 64,
                "expiry": datetime.now(UTC),
            },
        )
    with pytest.raises(IntegrityError), auth_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO auth_sessions "
                "(id, family_id, user_id, token_hash, csrf_hash, expires_at) "
                "SELECT :id, family_id, user_id, token_hash, csrf_hash, expires_at "
                "FROM auth_sessions"
            ),
            {"id": uuid4()},
        )
    with auth_engine.connect() as connection:
        row = connection.execute(
            text("SELECT consumed_at, revoked_at, replacement_id FROM auth_sessions")
        ).one()
        assert tuple(row) == (None, None, None)


def test_lookup_indexes_and_audit_defaults(auth_engine: Engine) -> None:
    inspector = inspect(auth_engine)
    session_indexes = {index["name"]: index for index in inspector.get_indexes("auth_sessions")}
    assert session_indexes["ix_auth_sessions_active_family"]["column_names"] == ["family_id"]
    assert "consumed_at IS NULL" in str(
        session_indexes["ix_auth_sessions_active_family"]["dialect_options"]["postgresql_where"]
    )
    assert session_indexes["ix_auth_sessions_expires_at"]["column_names"] == ["expires_at"]
    audit_indexes = {index["name"]: index for index in inspector.get_indexes("audit_logs")}
    assert audit_indexes["ix_audit_logs_created_at"]["column_names"] == ["created_at"]
    assert audit_indexes["ix_audit_logs_actor_id"]["column_names"] == ["actor_id"]
    with auth_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO audit_logs (id, action, entity_type, entity_id, request_id) "
                "VALUES (:id, 'test.action', 'user', 'identifier', 'request-1')"
            ),
            {"id": uuid4()},
        )
        row = connection.execute(
            text("SELECT actor_id, created_at, metadata FROM audit_logs")
        ).one()
        assert row.actor_id is None
        assert row.created_at.utcoffset() == timedelta(0)
        assert row.metadata == {}


def test_downgrade_then_upgrade_is_reversible(auth_engine: Engine) -> None:
    config = Config(str(ALEMBIC_INI))
    command.downgrade(config, "20261003_0001")
    assert "users" not in inspect(auth_engine).get_table_names()
    command.upgrade(config, "head")
    assert {"users", "auth_sessions", "audit_logs"} <= set(inspect(auth_engine).get_table_names())
