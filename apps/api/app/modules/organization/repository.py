from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.policies import AuthContext
from app.modules.auth.models import AuthSession
from app.modules.auth.repository import AuthSessionRepository
from app.modules.users.models import User, UserRole
from app.modules.users.repository import UserRepository


class OrganizationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def lock_guard(self) -> None:
        self.session.execute(select(func.pg_advisory_xact_lock(730031)))

    def authorize_write(
        self,
        context: AuthContext,
        csrf: Callable[[AuthSession], None],
        participant_ids: set[UUID] | None = None,
    ) -> None:
        # Guard is already held. Match user management's admin-first lock order;
        # otherwise linking an ADMIN while that ADMIN edits HR could deadlock.
        UserRepository(self.session).lock_active_admins()
        identifiers = (participant_ids or set()) | {context.user.id}
        users = list(
            self.session.scalars(
                select(User)
                .where(User.id.in_(identifiers))
                .order_by(User.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
        actor = next((user for user in users if user.id == context.user.id), None)
        if actor is None or not actor.is_active:
            raise ApiError(401, "authentication_required", "Authentication required")
        if actor.role != UserRole.HR:
            raise ApiError(403, "forbidden", "Access is forbidden")
        rows = AuthSessionRepository(self.session).get_active_family(
            context.family_id, now=datetime.now(UTC)
        )
        if not rows or rows[0].user_id != actor.id:
            raise ApiError(401, "authentication_required", "Authentication required")
        csrf(rows[0])
