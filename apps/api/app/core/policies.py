from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Annotated, cast
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_db_session
from app.core.errors import ApiError
from app.core.security import ACCESS_COOKIE_NAME, InvalidAccessToken, TokenService
from app.modules.auth.models import AuthSession
from app.modules.auth.repository import AuthSessionRepository
from app.modules.users.models import User, UserRole
from app.modules.users.repository import UserRepository


@dataclass(frozen=True)
class AuthContext:
    user: User = field(repr=False)
    family_id: UUID
    session: AuthSession = field(repr=False)


def get_auth_context(
    request: Request, session: Annotated[Session, Depends(get_db_session)]
) -> AuthContext:
    token = request.cookies.get(ACCESS_COOKIE_NAME)
    error = ApiError(401, "authentication_required", "Authentication required")
    if not token:
        raise error
    settings = cast(Settings, request.app.state.settings)
    try:
        claims = TokenService(settings.access_signing_key).decode_access_token(token)
    except InvalidAccessToken:
        raise error from None
    # Close the read transaction before a downstream service starts its own write
    # transaction. Mutation services revalidate authorization under their locks.
    with session.begin():
        user = UserRepository(session).get_by_id(claims.user_id)
        rows = AuthSessionRepository(session).get_active_family(
            claims.family_id, now=datetime.now(UTC)
        )
        if user is None or not user.is_active or not rows or rows[0].user_id != user.id:
            raise error
        return AuthContext(user=user, family_id=claims.family_id, session=rows[0])


def require_roles(
    *allowed: UserRole,
) -> Callable[..., AuthContext]:
    def policy(context: Annotated[AuthContext, Depends(get_auth_context)]) -> AuthContext:
        if context.user.role not in allowed:
            raise ApiError(403, "forbidden", "Access is forbidden")
        return context

    return policy
