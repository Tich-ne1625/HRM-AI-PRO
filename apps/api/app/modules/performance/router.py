from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.core.policies import AuthContext, require_roles
from app.modules.auth.router import require_csrf, require_same_origin
from app.modules.organization.schemas import Page
from app.modules.performance.schemas import (
    CalculateInput,
    CalculationView,
    CloseResult,
    FinalizationContext,
    FinalizeInput,
    HRReadiness,
    PerformanceReport,
    Readiness,
    RevisionSummary,
)
from app.modules.performance.service import PerformanceService
from app.modules.review_cycles.schemas import ExpectedVersion
from app.modules.users.models import UserRole

router = APIRouter(prefix="/api/v1", tags=["performance"])
Database = Annotated[Session, Depends(get_db_session)]
Reader = Annotated[
    AuthContext, Depends(require_roles(UserRole.HR, UserRole.MANAGER, UserRole.EMPLOYEE))
]
Calculator = Annotated[AuthContext, Depends(require_roles(UserRole.HR, UserRole.MANAGER))]
HR = Annotated[AuthContext, Depends(require_roles(UserRole.HR))]


def private(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.get("/performance/{employee_id}", response_model=PerformanceReport)
def report(
    employee_id: UUID, cycle_id: UUID, context: Reader, session: Database, response: Response
) -> PerformanceReport:
    private(response)
    return PerformanceService(session).report(employee_id, cycle_id, context.user)


@router.get("/performance/{employee_id}/readiness", response_model=HRReadiness | Readiness)
def readiness(
    employee_id: UUID, cycle_id: UUID, context: Reader, session: Database, response: Response
) -> Readiness | HRReadiness:
    private(response)
    return PerformanceService(session).readiness(employee_id, cycle_id, context.user)


@router.post(
    "/performance/{employee_id}/calculate",
    response_model=PerformanceReport,
    dependencies=[Depends(require_same_origin)],
)
def calculate(
    employee_id: UUID,
    body: CalculateInput,
    context: Calculator,
    session: Database,
    request: Request,
    response: Response,
) -> PerformanceReport:
    private(response)
    result, created = PerformanceService(session).calculate(
        employee_id,
        body,
        context,
        csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )
    response.status_code = 201 if created else 200
    return result


@router.get("/reviews/{identifier}/revisions", response_model=Page[RevisionSummary])
def revisions(
    identifier: UUID,
    context: Reader,
    session: Database,
    response: Response,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[RevisionSummary]:
    private(response)
    return PerformanceService(session).revisions(
        identifier, context.user, page=page, page_size=page_size
    )


@router.get("/reviews/{identifier}/revisions/{version}", response_model=CalculationView)
def revision(
    identifier: UUID,
    version: Annotated[int, Path(ge=1)],
    context: Reader,
    session: Database,
    response: Response,
) -> CalculationView:
    private(response)
    return PerformanceService(session).revision(identifier, version, context.user)


@router.get("/reviews/{identifier}/finalization-context", response_model=FinalizationContext)
def finalization_context(
    identifier: UUID, context: HR, session: Database, response: Response
) -> FinalizationContext:
    private(response)
    return PerformanceService(session).finalization_context(identifier, context.user)


@router.post(
    "/reviews/{identifier}/finalize",
    response_model=PerformanceReport,
    dependencies=[Depends(require_same_origin)],
)
def finalize(
    identifier: UUID,
    body: FinalizeInput,
    context: HR,
    session: Database,
    request: Request,
    response: Response,
) -> PerformanceReport:
    private(response)
    return PerformanceService(session).finalize(
        identifier,
        body,
        context,
        csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )


@router.post(
    "/review-cycles/{identifier}/close",
    response_model=CloseResult,
    dependencies=[Depends(require_same_origin)],
)
def close(
    identifier: UUID,
    body: ExpectedVersion,
    context: HR,
    session: Database,
    request: Request,
    response: Response,
) -> CloseResult:
    private(response)
    return PerformanceService(session).close(
        identifier,
        body.expected_version,
        context,
        csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )
