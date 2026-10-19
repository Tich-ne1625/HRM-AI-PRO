from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.core.policies import AuthContext, require_roles
from app.modules.auth.router import require_csrf, require_same_origin
from app.modules.organization.schemas import (
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentView,
    Page,
    PositionCreate,
    PositionUpdate,
    PositionView,
)
from app.modules.organization.service import ReferenceService, ReferenceView
from app.modules.users.models import UserRole

router = APIRouter(prefix="/api/v1", tags=["organization"])
HR = Annotated[AuthContext, Depends(require_roles(UserRole.HR))]
Reader = Annotated[
    AuthContext, Depends(require_roles(UserRole.HR, UserRole.MANAGER, UserRole.EMPLOYEE))
]
Database = Annotated[Session, Depends(get_db_session)]


@router.get("/departments", response_model=Page[DepartmentView])
def departments(
    context: Reader,
    session: Database,
    response: Response,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: Literal["code", "name", "created_at", "is_active"] = "code",
    is_active: bool | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[ReferenceView]:
    response.headers["Cache-Control"] = "no-store"
    return ReferenceService(session, "department").list(
        context.user,
        page=page,
        page_size=page_size,
        sort=sort,
        is_active=is_active,
        q=q,
    )


@router.get("/positions", response_model=Page[PositionView])
def positions(
    context: Reader,
    session: Database,
    response: Response,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: Literal["code", "title", "created_at", "is_active"] = "code",
    is_active: bool | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[ReferenceView]:
    response.headers["Cache-Control"] = "no-store"
    return ReferenceService(session, "position").list(
        context.user,
        page=page,
        page_size=page_size,
        sort=sort,
        is_active=is_active,
        q=q,
    )


@router.post(
    "/departments",
    response_model=DepartmentView,
    status_code=201,
    dependencies=[Depends(require_same_origin)],
)
def create_department(
    body: DepartmentCreate, context: HR, session: Database, request: Request, response: Response
) -> ReferenceView:
    result = ReferenceService(session, "department").write(
        body,
        context,
        csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )
    response.headers["Cache-Control"] = "no-store"
    return result


@router.patch(
    "/departments/{record_id}",
    response_model=DepartmentView,
    dependencies=[Depends(require_same_origin)],
)
def update_department(
    record_id: UUID,
    body: DepartmentUpdate,
    context: HR,
    session: Database,
    request: Request,
    response: Response,
) -> ReferenceView:
    result = ReferenceService(session, "department").write(
        body,
        context,
        record_id=record_id,
        csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post(
    "/positions",
    response_model=PositionView,
    status_code=201,
    dependencies=[Depends(require_same_origin)],
)
def create_position(
    body: PositionCreate, context: HR, session: Database, request: Request, response: Response
) -> ReferenceView:
    result = ReferenceService(session, "position").write(
        body,
        context,
        csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )
    response.headers["Cache-Control"] = "no-store"
    return result


@router.patch(
    "/positions/{record_id}",
    response_model=PositionView,
    dependencies=[Depends(require_same_origin)],
)
def update_position(
    record_id: UUID,
    body: PositionUpdate,
    context: HR,
    session: Database,
    request: Request,
    response: Response,
) -> ReferenceView:
    result = ReferenceService(session, "position").write(
        body,
        context,
        record_id=record_id,
        csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )
    response.headers["Cache-Control"] = "no-store"
    return result
