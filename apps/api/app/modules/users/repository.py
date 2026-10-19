from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.users.models import User, UserRole


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_normalized_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(User.email == email))

    def get_by_id(self, user_id: UUID) -> User | None:
        return self.session.get(User, user_id)

    def add(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()
        return user

    def lock_active_admins(self) -> list[User]:
        """Call before locking individual users to maintain a consistent lock order."""
        return list(
            self.session.scalars(
                select(User)
                .where(User.role == UserRole.ADMIN, User.is_active.is_(True))
                .order_by(User.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
