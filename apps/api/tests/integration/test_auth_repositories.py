from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models import AuditLog, AuthSession, User, UserRole

pytestmark = pytest.mark.integration


def user(email: str = "user@example.com", **values: object) -> User:
    return User(email=email, password_hash="hash", role=UserRole.ADMIN, **values)


def auth_session(user_id: UUID, **values: object) -> AuthSession:
    defaults: dict[str, object] = {
        "user_id": user_id,
        "family_id": uuid4(),
        "token_hash": uuid4().hex,
        "csrf_hash": "c" * 64,
        "expires_at": datetime.now(UTC) + timedelta(days=7),
    }
    defaults.update(values)
    return AuthSession(**defaults)


def test_user_repository_flushes_queries_and_leaves_transaction_to_caller(
    auth_engine: Engine,
) -> None:
    from app.modules.users.repository import UserRepository

    with Session(auth_engine) as session:
        repository = UserRepository(session)
        record = repository.add(user())
        assert record.id is not None
        assert repository.get_by_normalized_email("user@example.com") is record
        assert repository.get_by_normalized_email("absent@example.com") is None
        assert repository.get_by_id(record.id) is record
        assert repository.get_by_id(uuid4()) is None
        with Session(auth_engine) as observer:
            assert observer.scalar(select(func.count()).select_from(User)) == 0
        session.rollback()
    with Session(auth_engine) as observer:
        assert observer.scalar(select(func.count()).select_from(User)) == 0


def test_active_admin_lock_is_ordered_and_locks_only_active_admins(auth_engine: Engine) -> None:
    from app.modules.users.repository import UserRepository

    with Session(auth_engine) as session, session.begin():
        session.add_all(
            [
                user("later@example.com", id=UUID(int=2)),
                user("first@example.com", id=UUID(int=1)),
                user("inactive@example.com", id=UUID(int=3), is_active=False),
                User(
                    id=UUID(int=4), email="hr@example.com", password_hash="hash", role=UserRole.HR
                ),
            ]
        )
    with Session(auth_engine) as owner:
        locked = UserRepository(owner).lock_active_admins()
        assert [record.id for record in locked] == [UUID(int=1), UUID(int=2)]
        for identifier in (1, 2):
            with Session(auth_engine) as contender, pytest.raises(OperationalError) as error:
                contender.execute(
                    select(User).where(User.id == UUID(int=identifier)).with_for_update(nowait=True)
                )
            assert error.value.orig.sqlstate == "55P03"
        for identifier in (3, 4):
            with Session(auth_engine) as contender:
                assert (
                    contender.scalar(
                        select(User)
                        .where(User.id == UUID(int=identifier))
                        .with_for_update(nowait=True)
                    )
                    is not None
                )


def test_token_lookup_locks_even_consumed_sessions(auth_engine: Engine) -> None:
    from app.modules.auth.repository import AuthSessionRepository

    with Session(auth_engine) as session, session.begin():
        account = user()
        session.add(account)
        session.flush()
        record = auth_session(account.id, token_hash="lookup", consumed_at=datetime.now(UTC))
        session.add(record)
    with Session(auth_engine) as owner:
        repository = AuthSessionRepository(owner)
        found = repository.get_by_token_hash_for_update("lookup")
        assert found is not None and found.consumed_at is not None
        assert repository.get_by_token_hash_for_update("missing") is None
        with Session(auth_engine) as contender, pytest.raises(OperationalError) as error:
            contender.execute(
                select(AuthSession)
                .where(AuthSession.token_hash == "lookup")
                .with_for_update(nowait=True)
            )
        assert error.value.orig.sqlstate == "55P03"


def test_active_family_excludes_expired_consumed_and_revoked(auth_engine: Engine) -> None:
    from app.modules.auth.repository import AuthSessionRepository

    now, family = datetime.now(UTC), uuid4()
    with Session(auth_engine) as session:
        account = user()
        session.add(account)
        session.flush()
        repository = AuthSessionRepository(session)
        valid = repository.add(auth_session(account.id, family_id=family))
        for changes in ({"expires_at": now}, {"consumed_at": now}, {"revoked_at": now}):
            repository.add(auth_session(account.id, family_id=family, **changes))
        repository.add(auth_session(account.id))
        assert repository.get_active_family(family, now=now) == [valid]
        assert repository.get_active_family(uuid4(), now=now) == []
        with Session(auth_engine) as observer:
            assert observer.scalar(select(func.count()).select_from(AuthSession)) == 0


def test_successor_preserves_absolute_expiry_and_links_predecessor(auth_engine: Engine) -> None:
    from app.modules.auth.repository import AuthSessionRepository

    now = datetime.now(UTC)
    with Session(auth_engine) as session:
        account = user()
        session.add(account)
        session.flush()
        repository = AuthSessionRepository(session)
        previous = repository.add(auth_session(account.id))
        expiry = previous.expires_at
        successor = repository.add_successor(
            previous,
            token_hash="successor",
            csrf_hash="csrf",
            consumed_at=now,
        )
        assert successor.id is not None and successor.id != previous.id
        assert successor.family_id == previous.family_id
        assert successor.user_id == account.id
        assert successor.expires_at == expiry
        assert previous.expires_at == expiry
        assert previous.consumed_at == now and previous.replacement_id == successor.id
        assert repository.get_active_family(previous.family_id, now=now) == [successor]
        assert successor.token_hash == "successor" and successor.csrf_hash == "csrf"
        session.rollback()
    with Session(auth_engine) as observer:
        assert observer.scalar(select(func.count()).select_from(AuthSession)) == 0


def test_revocations_preserve_history_and_other_users(auth_engine: Engine) -> None:
    from app.modules.auth.repository import AuthSessionRepository

    now, earlier = datetime.now(UTC), datetime.now(UTC) - timedelta(hours=1)
    with Session(auth_engine) as session:
        account, other = user(), user("other@example.com")
        session.add_all([account, other])
        session.flush()
        repository = AuthSessionRepository(session)
        keep = repository.add(auth_session(account.id))
        revoke = repository.add(auth_session(account.id, consumed_at=earlier))
        old = repository.add(
            auth_session(account.id, family_id=revoke.family_id, revoked_at=earlier)
        )
        unrelated = repository.add(auth_session(other.id))
        assert repository.revoke_other_families(account.id, keep.family_id, revoked_at=now) == 1
        assert keep.revoked_at is None and unrelated.revoked_at is None
        assert revoke.revoked_at == now and old.revoked_at == earlier
        assert repository.revoke_family(keep.family_id, revoked_at=now) == 1
        assert keep.revoked_at == now
        assert repository.revoke_family(keep.family_id, revoked_at=now) == 0
        session.rollback()
    with Session(auth_engine) as observer:
        assert observer.scalar(select(func.count()).select_from(AuthSession)) == 0


def test_audit_writer_flushes_safe_metadata_without_committing(auth_engine: Engine) -> None:
    from app.modules.audit.service import AuditWriter

    with Session(auth_engine) as session:
        metadata = {"role": "ADMIN"}
        record = AuditWriter().record(
            session, None, "user.bootstrap_created", "user", "some-id", "request-id", metadata
        )
        metadata["role"] = "HR"
        assert record.id is not None and record.metadata_ == {"role": "ADMIN"}
        assert record.created_at.utcoffset() == timedelta(0)
        assert session.scalar(select(AuditLog)) is record
        with Session(auth_engine) as observer:
            assert observer.scalar(select(func.count()).select_from(AuditLog)) == 0
        session.rollback()
    with Session(auth_engine) as observer:
        assert observer.scalar(select(func.count()).select_from(AuditLog)) == 0


@pytest.mark.parametrize("secret_key", ["password", "password_hash", "token", "csrf_hash"])
def test_audit_writer_rejects_unallowlisted_metadata(auth_engine: Engine, secret_key: str) -> None:
    from app.modules.audit.service import AuditWriter

    with Session(auth_engine) as session:
        with pytest.raises(ValueError):
            AuditWriter().record(
                session, None, "test", "user", "id", "request", {secret_key: "never-log-this"}
            )
        assert session.scalar(select(func.count()).select_from(AuditLog)) == 0
