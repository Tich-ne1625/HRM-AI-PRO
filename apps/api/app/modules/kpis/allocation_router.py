from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.core.policies import AuthContext, require_roles
from app.modules.auth.router import require_csrf, require_same_origin
from app.modules.kpis.allocation_schemas import AllocationView
from app.modules.kpis.allocations import AllocationService
from app.modules.kpis.models import KPIDirection
from app.modules.kpis.schemas import ActualUpdate, AllocationReplace, DefinitionView
from app.modules.organization.schemas import Page
from app.modules.users.models import UserRole

router = APIRouter(prefix="/api/v1", tags=["employee-kpis"])
Reader = Annotated[
    AuthContext, Depends(require_roles(UserRole.HR, UserRole.MANAGER, UserRole.EMPLOYEE))
]
Writer = Annotated[AuthContext, Depends(require_roles(UserRole.HR, UserRole.MANAGER))]
Database = Annotated[Session, Depends(get_db_session)]


@router.get("/employees/{employee_id}/kpis", response_model=AllocationView)
def employee_kpis(
    employee_id: UUID, cycle_id: UUID, context: Reader, session: Database, response: Response
) -> AllocationView:
    response.headers["Cache-Control"] = "no-store"
    return AllocationService(session).read(employee_id, cycle_id, context.user)


@router.get("/employees/{employee_id}/kpi-options", response_model=Page[DefinitionView])
def kpi_options(
    employee_id: UUID,
    cycle_id: UUID,
    context: Writer,
    session: Database,
    response: Response,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: Literal["code", "name", "created_at"] = "code",
    q: Annotated[str | None, Query(max_length=100)] = None,
    is_active: Literal[True] = True,
    direction: KPIDirection | None = None,
) -> Page[DefinitionView]:
    response.headers["Cache-Control"] = "no-store"
    return AllocationService(session).options(
        employee_id,
        cycle_id,
        context.user,
        page=page,
        page_size=page_size,
        sort=sort,
        q=q,
        direction=direction,
    )


@router.put(
    "/employees/{employee_id}/kpis",
    response_model=AllocationView,
    dependencies=[Depends(require_same_origin)],
)
def replace_allocation(
    employee_id: UUID,
    cycle_id: UUID,
    body: AllocationReplace,
    context: Writer,
    session: Database,
    request: Request,
    response: Response,
) -> AllocationView:
    response.headers["Cache-Control"] = "no-store"
    return AllocationService(session).replace(
        employee_id,
        cycle_id,
        body,
        context,
        csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )


@router.patch(
    "/employee-kpis/{identifier}",
    response_model=AllocationView,
    dependencies=[Depends(require_same_origin)],
)
def update_actual(
    identifier: UUID,
    body: ActualUpdate,
    context: Writer,
    session: Database,
    request: Request,
    response: Response,
) -> AllocationView:
    response.headers["Cache-Control"] = "no-store"
    return AllocationService(session).actual(
        identifier,
        body,
        context,
        csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )
