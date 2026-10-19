from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import EmailStr
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.core.policies import AuthContext, require_roles
from app.modules.auth.router import require_csrf, require_same_origin
from app.modules.employees.models import EmploymentStatus
from app.modules.employees.schemas import (
    AccountMatches,
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeView,
)
from app.modules.employees.service import EmployeeService
from app.modules.organization.schemas import Page
from app.modules.users.models import UserRole

router = APIRouter(prefix="/api/v1/employees", tags=["employees"])
HR = Annotated[AuthContext, Depends(require_roles(UserRole.HR))]
Reader = Annotated[
    AuthContext, Depends(require_roles(UserRole.HR, UserRole.MANAGER, UserRole.EMPLOYEE))
]
Database = Annotated[Session, Depends(get_db_session)]


@router.get("", response_model=Page[EmployeeView])
def employees(
    context: Reader,
    session: Database,
    response: Response,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: Literal[
        "employee_code", "display_name", "created_at", "employment_status"
    ] = "employee_code",
    department_id: UUID | None = None,
    position_id: UUID | None = None,
    employment_status: EmploymentStatus | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[EmployeeView]:
    response.headers["Cache-Control"] = "no-store"
    return EmployeeService(session).list(
        context.user,
        page=page,
        page_size=page_size,
        sort=sort,
        department_id=department_id,
        position_id=position_id,
        employment_status=employment_status,
        q=q,
    )


@router.get("/linkable-users", response_model=AccountMatches)
def linkable_users(
    context: HR,
    session: Database,
    response: Response,
    email: Annotated[EmailStr, Query(max_length=254)],
) -> AccountMatches:
    response.headers["Cache-Control"] = "no-store"
    return EmployeeService(session).lookup(str(email))


@router.get("/{employee_id}", response_model=EmployeeView)
def employee_detail(
    employee_id: UUID, context: Reader, session: Database, response: Response
) -> EmployeeView:
    response.headers["Cache-Control"] = "no-store"
    return EmployeeService(session).detail(employee_id, context.user)


@router.post(
    "", response_model=EmployeeView, status_code=201, dependencies=[Depends(require_same_origin)]
)
def create_employee(
    body: EmployeeCreate, context: HR, session: Database, request: Request, response: Response
) -> EmployeeView:
    result = EmployeeService(session).write(
        body,
        context,
        csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )
    response.headers["Cache-Control"] = "no-store"
    return result


@router.patch(
    "/{employee_id}", response_model=EmployeeView, dependencies=[Depends(require_same_origin)]
)
def update_employee(
    employee_id: UUID,
    body: EmployeeUpdate,
    context: HR,
    session: Database,
    request: Request,
    response: Response,
) -> EmployeeView:
    result = EmployeeService(session).write(
        body,
        context,
        employee_id=employee_id,
        csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )
    response.headers["Cache-Control"] = "no-store"
    return result
