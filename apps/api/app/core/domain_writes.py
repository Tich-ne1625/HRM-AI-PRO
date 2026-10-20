"""Shared Phase 4 write authorization, using the established organization lock order."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.policies import AuthContext
from app.modules.auth.models import AuthSession
from app.modules.auth.repository import AuthSessionRepository
from app.modules.organization.repository import OrganizationRepository
from app.modules.users.models import User, UserRole
from app.modules.users.repository import UserRepository

CsrfCheck = Callable[[AuthSession], None]


def authorize_domain_write(
    session: Session,
    context: AuthContext,
    csrf: CsrfCheck,
    roles: tuple[UserRole, ...],
    related_user_ids: set[UUID] | None = None,
) -> User:
    """Call inside a transaction, before taking any user/domain row locks.

    Callers that need to discover related IDs may acquire the same advisory guard
    first (it is transaction-reentrant), read IDs, then call this function.
    """
    OrganizationRepository(session).lock_guard()
    UserRepository(session).lock_active_admins()
    users = list(
        session.scalars(
            select(User)
            .where(User.id.in_((related_user_ids or set()) | {context.user.id}))
            .order_by(User.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )
    actor = next((user for user in users if user.id == context.user.id), None)
    if actor is None or not actor.is_active:
        raise ApiError(401, "authentication_required", "Authentication required")
    if actor.role not in roles:
        raise ApiError(403, "forbidden", "Access is forbidden")
    family = AuthSessionRepository(session).get_active_family_for_update(
        context.family_id,
        now=datetime.now(UTC),
    )
    if not family or family[0].user_id != actor.id:
        raise ApiError(401, "authentication_required", "Authentication required")
    csrf(family[0])
    return actor


def require_version(current: int, expected: int, *, evidence: bool = False) -> None:
    if current != expected:
        code = "stale_evidence_version" if evidence else "stale_version"
        raise ApiError(409, code, "Data has changed; reload before editing")
