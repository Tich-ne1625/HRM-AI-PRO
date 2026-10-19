from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.modules.auth.schemas import CurrentUser
from app.modules.users.models import User
from app.modules.users.repository import UserRepository


def current_users(session: Session, users: Sequence[User]) -> list[CurrentUser]:
    links = UserRepository(session).get_employee_ids([user.id for user in users])
    return [
        CurrentUser.model_validate(user).model_copy(update={"employee_id": links.get(user.id)})
        for user in users
    ]


def current_user(session: Session, user: User) -> CurrentUser:
    return current_users(session, [user])[0]
