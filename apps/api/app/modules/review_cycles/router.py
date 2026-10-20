from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.core.policies import AuthContext, require_roles
from app.modules.auth.router import require_csrf, require_same_origin
from app.modules.organization.schemas import Page
from app.modules.review_cycles.models import CycleStatus
from app.modules.review_cycles.schemas import (
    CycleCreate,
    CycleUpdate,
    CycleView,
    Enrollment,
    EnrollmentResult,
    ExpectedVersion,
    ParticipantView,
)
from app.modules.review_cycles.service import CycleService
from app.modules.users.models import UserRole

router = APIRouter(prefix="/api/v1/review-cycles", tags=["review-cycles"])
HR = Annotated[AuthContext, Depends(require_roles(UserRole.HR))]
Reader = Annotated[
    AuthContext, Depends(require_roles(UserRole.HR, UserRole.MANAGER, UserRole.EMPLOYEE))
]
Database = Annotated[Session, Depends(get_db_session)]


@router.get("", response_model=Page[CycleView])
def cycles(
    context: Reader,
    session: Database,
    response: Response,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: Literal["start_date", "name", "created_at"] = "start_date",
    status: CycleStatus | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[CycleView]:
    response.headers["Cache-Control"] = "no-store"
    return CycleService(session).list(
        context.user, page=page, page_size=page_size, sort=sort, status=status, q=q
    )


@router.post(
    "", status_code=201, response_model=CycleView, dependencies=[Depends(require_same_origin)]
)
def create_cycle(
    body: CycleCreate, context: HR, session: Database, request: Request, response: Response
) -> CycleView:
    response.headers["Cache-Control"] = "no-store"
    return CycleService(session).write(
        body,
        context,
        csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )


@router.get("/{identifier}", response_model=CycleView)
def cycle_detail(
    identifier: UUID, context: Reader, session: Database, response: Response
) -> CycleView:
    response.headers["Cache-Control"] = "no-store"
    return CycleService(session).detail(identifier, context.user)


@router.patch(
    "/{identifier}", response_model=CycleView, dependencies=[Depends(require_same_origin)]
)
def update_cycle(
    identifier: UUID,
    body: CycleUpdate,
    context: HR,
    session: Database,
    request: Request,
    response: Response,
) -> CycleView:
    response.headers["Cache-Control"] = "no-store"
    return CycleService(session).write(
        body,
        context,
        identifier=identifier,
        csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )


@router.get("/{identifier}/participants", response_model=Page[ParticipantView])
def cycle_participants(
    identifier: UUID,
    context: Reader,
    session: Database,
    response: Response,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: Literal["employee_code"] = "employee_code",
    q: Annotated[str | None, Query(max_length=100)] = None,
    department_id: UUID | None = None,
) -> Page[ParticipantView]:
    response.headers["Cache-Control"] = "no-store"
    return CycleService(session).participants(
        identifier, context.user, page=page, page_size=page_size, q=q, department_id=department_id
    )


@router.post(
    "/{identifier}/participants",
    response_model=EnrollmentResult,
    dependencies=[Depends(require_same_origin)],
)
def enroll_participants(
    identifier: UUID,
    body: Enrollment,
    context: HR,
    session: Database,
    request: Request,
    response: Response,
) -> EnrollmentResult:
    response.headers["Cache-Control"] = "no-store"
    return CycleService(session).enroll(
        identifier,
        body,
        context,
        csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )


@router.delete(
    "/{identifier}/participants/{participant_id}",
    response_model=EnrollmentResult,
    dependencies=[Depends(require_same_origin)],
)
def remove_participant(
    identifier: UUID,
    participant_id: UUID,
    body: ExpectedVersion,
    context: HR,
    session: Database,
    request: Request,
    response: Response,
) -> EnrollmentResult:
    response.headers["Cache-Control"] = "no-store"
    return CycleService(session).remove(
        identifier,
        participant_id,
        body.expected_version,
        context,
        csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )
