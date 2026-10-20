from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.core.policies import AuthContext, get_auth_context, require_roles
from app.modules.auth.router import require_csrf, require_same_origin
from app.modules.feedback.models import AssignmentStatus, Relationship
from app.modules.feedback.repository import FeedbackRepository
from app.modules.feedback.schemas import (
    AdministrationContext,
    AdministrationView,
    AssignmentCancel,
    AssignmentCreate,
    AssignmentReplace,
    AssignmentUpdate,
    AssignmentView,
    CoverageView,
    FeedbackCreate,
    ReviewerOption,
    SummaryView,
)
from app.modules.feedback.service import FeedbackService, writable
from app.modules.feedback.summary import coverage, employee_summary
from app.modules.organization.schemas import Page
from app.modules.review_cycles.models import ReviewCycle
from app.modules.review_cycles.schemas import ParticipantSnapshot
from app.modules.users.models import UserRole

router = APIRouter(prefix="/api/v1", tags=["feedback"])
Actor = Annotated[AuthContext, Depends(get_auth_context)]
HR = Annotated[AuthContext, Depends(require_roles(UserRole.HR))]
Reader = Annotated[
    AuthContext, Depends(require_roles(UserRole.HR, UserRole.MANAGER, UserRole.EMPLOYEE))
]
Database = Annotated[Session, Depends(get_db_session)]
PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]
RawOrOwn = AdministrationView | AssignmentView


def private(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.get("/feedback-context", response_model=AdministrationContext)
def administration_context(
    participant_id: UUID,
    context: HR,
    session: Database,
    response: Response,
) -> AdministrationContext:
    private(response)
    with session.begin():
        participant = FeedbackRepository(session).participant(participant_id)
        cycle = session.get(ReviewCycle, participant.cycle_id)
        assert cycle is not None
        if participant.snapshot is None:
            from app.core.errors import ApiError

            raise ApiError(409, "cycle_not_active", "Activate the cycle before assigning feedback")
        snapshot = ParticipantSnapshot.model_validate(participant.snapshot)
        return AdministrationContext(
            participant_id=participant.id,
            cycle_id=cycle.id,
            employee_id=snapshot.employee_id,
            employee_code=snapshot.employee_code,
            display_name=snapshot.display_name,
            evidence_version=participant.evidence_version,
            cycle_status=cycle.status,
            finalized=participant.finalized_at is not None,
            coverage=coverage(session, participant.id),
        )


@router.get("/feedback-assignments", response_model=Page[RawOrOwn])
def assignments(
    context: Actor,
    session: Database,
    response: Response,
    view: Literal["mine", "administration"] = "mine",
    cycle_id: UUID | None = None,
    participant_id: UUID | None = None,
    status: AssignmentStatus | None = None,
    relationship: Relationship | None = None,
    page: PageNumber = 1,
    page_size: PageSize = 20,
    sort: Literal["due_at", "created_at"] = "due_at",
) -> Page[AssignmentView | AdministrationView]:
    private(response)
    with session.begin():
        return FeedbackRepository(session).listing(
            context.user,
            administration=view == "administration",
            cycle_id=cycle_id,
            participant_id=participant_id,
            status=status,
            relationship=relationship,
            page=page,
            page_size=page_size,
            sort=sort,
        )


@router.get("/feedback-assignments/{identifier}", response_model=RawOrOwn)
def assignment(
    identifier: UUID, context: Actor, session: Database, response: Response
) -> AssignmentView:
    private(response)
    with session.begin():
        repository = FeedbackRepository(session)
        row = repository.assignment(identifier, context.user)
        return repository.view(row, administration=context.user.role == UserRole.HR)


@router.get("/feedback-reviewer-options", response_model=Page[ReviewerOption])
def reviewer_options(
    participant_id: UUID,
    relationship: Relationship,
    context: HR,
    session: Database,
    response: Response,
    page: PageNumber = 1,
    page_size: PageSize = 20,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[ReviewerOption]:
    private(response)
    with session.begin():
        repository = FeedbackRepository(session)
        participant = repository.participant(participant_id)
        cycle = session.get(ReviewCycle, participant.cycle_id)
        assert cycle is not None
        writable(participant, cycle)
        return repository.options(participant, relationship, page=page, page_size=page_size, q=q)


@router.get("/feedback-coverage", response_model=CoverageView)
def participant_coverage(
    participant_id: UUID,
    context: HR,
    session: Database,
    response: Response,
) -> CoverageView:
    private(response)
    with session.begin():
        FeedbackRepository(session).participant(participant_id)
        return coverage(session, participant_id)


@router.post(
    "/feedback-assignments",
    response_model=AdministrationView,
    status_code=201,
    dependencies=[Depends(require_same_origin)],
)
def create_assignment(
    body: AssignmentCreate,
    context: HR,
    session: Database,
    request: Request,
    response: Response,
) -> AssignmentView:
    private(response)
    return FeedbackService(session).create(
        body,
        context,
        csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )


@router.patch(
    "/feedback-assignments/{identifier}",
    response_model=AdministrationView,
    dependencies=[Depends(require_same_origin)],
)
def update_assignment(
    identifier: UUID,
    body: AssignmentUpdate,
    context: HR,
    session: Database,
    request: Request,
    response: Response,
) -> AssignmentView:
    private(response)
    return FeedbackService(session).update(
        identifier,
        body,
        context,
        csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )


@router.delete(
    "/feedback-assignments/{identifier}",
    response_model=AdministrationView,
    dependencies=[Depends(require_same_origin)],
)
def cancel_assignment(
    identifier: UUID,
    body: AssignmentCancel,
    context: HR,
    session: Database,
    request: Request,
    response: Response,
) -> AssignmentView:
    private(response)
    return FeedbackService(session).cancel(
        identifier,
        body,
        context,
        csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )


@router.post(
    "/feedback-assignments/{identifier}/replace",
    response_model=AdministrationView,
    dependencies=[Depends(require_same_origin)],
)
def replace_assignment(
    identifier: UUID,
    body: AssignmentReplace,
    context: HR,
    session: Database,
    request: Request,
    response: Response,
) -> AssignmentView:
    private(response)
    return FeedbackService(session).replace(
        identifier,
        body,
        context,
        csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )


@router.post(
    "/feedback",
    response_model=AssignmentView,
    status_code=201,
    dependencies=[Depends(require_same_origin)],
)
def submit_feedback(
    body: FeedbackCreate,
    context: Actor,
    session: Database,
    request: Request,
    response: Response,
) -> AssignmentView:
    private(response)
    return FeedbackService(session).submit(
        body,
        context,
        csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )


@router.get("/employees/{employee_id}/feedback", response_model=SummaryView)
def summary(
    employee_id: UUID,
    cycle_id: UUID,
    context: Reader,
    session: Database,
    response: Response,
) -> SummaryView:
    private(response)
    return employee_summary(session, employee_id, cycle_id, context.user)
