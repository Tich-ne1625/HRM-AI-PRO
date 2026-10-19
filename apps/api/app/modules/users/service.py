from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.policies import AuthContext
from app.core.security import PasswordService
from app.modules.audit.service import AuditWriter
from app.modules.auth.models import AuthSession
from app.modules.auth.repository import AuthSessionRepository
from app.modules.auth.schemas import CurrentUser
from app.modules.users.models import User, UserRole
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate, UserPage, UserUpdate

UserSort = Literal["email", "created_at", "role", "is_active"]


class UserService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.audit = AuditWriter()

    def list_users(
        self,
        *,
        page: int,
        page_size: int,
        sort: UserSort,
        role: UserRole | None,
        is_active: bool | None,
    ) -> UserPage:
        filters = []
        if role is not None:
            filters.append(User.role == role)
        if is_active is not None:
            filters.append(User.is_active == is_active)
        with self.session.begin():
            total = self.session.scalar(select(func.count()).select_from(User).where(*filters)) or 0
            rows = self.session.scalars(
                select(User)
                .where(*filters)
                .order_by(getattr(User, sort), User.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            return UserPage(
                items=[CurrentUser.model_validate(row) for row in rows],
                total=total,
                page=page,
                page_size=page_size,
            )

    def _authorize_mutation(
        self,
        context: AuthContext,
        csrf: Callable[[AuthSession], None],
    ) -> list[User]:
        # All user-management mutations acquire active-admin locks in UUID order
        # before any individual user lock. Auth mutations only lock their owner.
        users = UserRepository(self.session)
        admins = users.lock_active_admins()
        actor = users.get_by_id_for_update(context.user.id)
        if actor is None or not actor.is_active:
            raise ApiError(401, "authentication_required", "Authentication required")
        if actor.role != UserRole.ADMIN:
            raise ApiError(403, "forbidden", "Access is forbidden")
        rows = AuthSessionRepository(self.session).get_active_family(
            context.family_id, now=datetime.now(UTC)
        )
        if not rows or rows[0].user_id != actor.id:
            raise ApiError(401, "authentication_required", "Authentication required")
        csrf(rows[0])
        return admins

    def create(
        self,
        body: UserCreate,
        context: AuthContext,
        *,
        csrf: Callable[[AuthSession], None],
        request_id: str,
    ) -> CurrentUser:
        try:
            with self.session.begin():
                self._authorize_mutation(context, csrf)
                users = UserRepository(self.session)
                if users.get_by_normalized_email(str(body.email)) is not None:
                    raise ApiError(409, "email_already_exists", "Email already exists")
                user = users.add(
                    User(
                        email=str(body.email),
                        role=body.role,
                        is_active=True,
                        password_hash=PasswordService().hash(body.password.get_secret_value()),
                    )
                )
                self.audit.record(
                    self.session,
                    context.user.id,
                    "user.created",
                    "user",
                    str(user.id),
                    request_id,
                    {"role": user.role.value},
                )
                return CurrentUser.model_validate(user)
        except IntegrityError as error:
            if getattr(error.orig, "sqlstate", None) == "23505":
                raise ApiError(409, "email_already_exists", "Email already exists") from None
            raise

    def update(
        self,
        user_id: UUID,
        body: UserUpdate,
        context: AuthContext,
        *,
        csrf: Callable[[AuthSession], None],
        request_id: str,
    ) -> CurrentUser:
        with self.session.begin():
            admins = self._authorize_mutation(context, csrf)
            user = UserRepository(self.session).get_by_id_for_update(user_id)
            if user is None:
                raise ApiError(404, "user_not_found", "User not found")
            next_role = body.role if body.role is not None else user.role
            next_active = body.is_active if body.is_active is not None else user.is_active
            if (
                user.role == UserRole.ADMIN
                and user.is_active
                and (next_role != UserRole.ADMIN or not next_active)
                and len(admins) <= 1
            ):
                raise ApiError(
                    409, "last_active_admin", "The last active administrator is protected"
                )
            previous_role, previous_active = user.role, user.is_active
            user.role, user.is_active = next_role, next_active
            if previous_active and not next_active:
                self.session.execute(
                    update(AuthSession)
                    .where(
                        AuthSession.user_id == user.id,
                        AuthSession.revoked_at.is_(None),
                    )
                    .values(revoked_at=datetime.now(UTC))
                )
            if previous_role != next_role:
                self.audit.record(
                    self.session,
                    context.user.id,
                    "user.role_changed",
                    "user",
                    str(user.id),
                    request_id,
                    {"previous_role": previous_role.value, "role": next_role.value},
                )
            if previous_active != next_active:
                self.audit.record(
                    self.session,
                    context.user.id,
                    "user.status_changed",
                    "user",
                    str(user.id),
                    request_id,
                    {"previous_is_active": previous_active, "is_active": next_active},
                )
            self.session.flush()
            return CurrentUser.model_validate(user)
