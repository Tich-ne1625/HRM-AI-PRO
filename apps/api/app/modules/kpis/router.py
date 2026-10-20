from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.core.policies import AuthContext, require_roles
from app.modules.auth.router import require_csrf, require_same_origin
from app.modules.kpis.models import KPIDirection
from app.modules.kpis.schemas import DefinitionCreate, DefinitionUpdate, DefinitionView
from app.modules.kpis.service import DefinitionService
from app.modules.organization.schemas import Page
from app.modules.users.models import UserRole

router = APIRouter(prefix="/api/v1", tags=["kpis"])
HR = Annotated[AuthContext, Depends(require_roles(UserRole.HR))]
Reader = Annotated[
    AuthContext, Depends(require_roles(UserRole.HR, UserRole.MANAGER, UserRole.EMPLOYEE))
]
Database = Annotated[Session, Depends(get_db_session)]


@router.get("/kpis", response_model=Page[DefinitionView])
def definitions(
    context: Reader,
    session: Database,
    response: Response,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: Literal["code", "name", "created_at"] = "code",
    q: Annotated[str | None, Query(max_length=100)] = None,
    is_active: bool | None = None,
    direction: KPIDirection | None = None,
) -> Page[DefinitionView]:
    response.headers["Cache-Control"] = "no-store"
    with session.begin():
        return DefinitionService(session).list(
            context.user,
            page=page,
            page_size=page_size,
            sort=sort,
            q=q,
            is_active=is_active,
            direction=direction,
        )


@router.post(
    "/kpis",
    response_model=DefinitionView,
    status_code=201,
    dependencies=[Depends(require_same_origin)],
)
def create_definition(
    body: DefinitionCreate, context: HR, session: Database, request: Request, response: Response
) -> DefinitionView:
    response.headers["Cache-Control"] = "no-store"
    return DefinitionService(session).write(
        body,
        context,
        csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )


@router.patch(
    "/kpis/{identifier}", response_model=DefinitionView, dependencies=[Depends(require_same_origin)]
)
def update_definition(
    identifier: UUID,
    body: DefinitionUpdate,
    context: HR,
    session: Database,
    request: Request,
    response: Response,
) -> DefinitionView:
    response.headers["Cache-Control"] = "no-store"
    return DefinitionService(session).write(
        body,
        context,
        identifier=identifier,
        csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )
