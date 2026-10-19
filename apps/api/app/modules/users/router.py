from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.core.policies import AuthContext, require_roles
from app.modules.auth.router import require_csrf, require_same_origin
from app.modules.auth.schemas import CurrentUser
from app.modules.users.models import UserRole
from app.modules.users.schemas import UserCreate, UserPage, UserUpdate
from app.modules.users.service import UserService, UserSort

router = APIRouter(prefix="/api/v1/users", tags=["users"])
Admin = Annotated[AuthContext, Depends(require_roles(UserRole.ADMIN))]
Database = Annotated[Session, Depends(get_db_session)]


@router.get("", response_model=UserPage)
def list_users(
    context: Admin,
    session: Database,
    response: Response,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: UserSort = "email",
    role: UserRole | None = None,
    is_active: bool | None = None,
) -> UserPage:
    response.headers["Cache-Control"] = "no-store"
    return UserService(session).list_users(
        page=page,
        page_size=page_size,
        sort=sort,
        role=role,
        is_active=is_active,
    )


@router.post("", response_model=CurrentUser, status_code=201)
def create_user(
    context: Admin,
    body: UserCreate,
    request: Request,
    session: Database,
    response: Response,
) -> CurrentUser:
    require_same_origin(request)
    result = UserService(session).create(
        body,
        context,
        csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )
    response.headers["Cache-Control"] = "no-store"
    return result


@router.patch("/{user_id}", response_model=CurrentUser)
def update_user(
    user_id: UUID,
    body: UserUpdate,
    context: Admin,
    request: Request,
    session: Database,
    response: Response,
) -> CurrentUser:
    require_same_origin(request)
    result = UserService(session).update(
        user_id,
        body,
        context,
        csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )
    response.headers["Cache-Control"] = "no-store"
    return result
