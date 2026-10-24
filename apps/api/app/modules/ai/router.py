from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_db_session
from app.core.policies import AuthContext, require_roles
from app.modules.ai.provider import Provider
from app.modules.ai.reports import SavedReport, saved_reports
from app.modules.ai.schemas import AnalysisState, AnalysisView, Audience, GenerateInput
from app.modules.ai.service import AIService
from app.modules.auth.router import require_csrf, require_same_origin
from app.modules.organization.schemas import Page
from app.modules.users.models import UserRole

router = APIRouter(prefix="/api/v1", tags=["ai-analysis"])
Database = Annotated[Session, Depends(get_db_session)]
Reader = Annotated[
    AuthContext, Depends(require_roles(UserRole.HR, UserRole.MANAGER, UserRole.EMPLOYEE))
]
HR = Annotated[AuthContext, Depends(require_roles(UserRole.HR))]


def service(request: Request, session: Database) -> AIService:
    return AIService(
        session,
        cast(Settings, request.app.state.settings),
        cast(Provider, request.app.state.ai_provider),
    )


Service = Annotated[AIService, Depends(service)]


@router.get("/ai-reports", response_model=Page[SavedReport])
def reports(
    context: Reader,
    session: Database,
    response: Response,
    audience: Audience = Audience.PUBLIC,
    cycle_id: UUID | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[SavedReport]:
    response.headers["Cache-Control"] = "no-store"
    return saved_reports(session, context.user, audience, cycle_id, page, page_size)


@router.get("/performance/{review_id}/ai-analysis", response_model=AnalysisState)
def state(
    review_id: UUID,
    context: Reader,
    ai: Service,
    response: Response,
    audience: Audience = Audience.PUBLIC,
) -> AnalysisState:
    response.headers["Cache-Control"] = "no-store"
    return ai.state(review_id, audience, context.user)


@router.post(
    "/performance/{review_id}/ai-analysis",
    response_model=AnalysisView,
    dependencies=[Depends(require_same_origin)],
)
def generate(
    review_id: UUID,
    body: GenerateInput,
    context: HR,
    ai: Service,
    request: Request,
    response: Response,
) -> AnalysisView:
    response.headers["Cache-Control"] = "no-store"
    result, code = ai.generate(
        review_id, body, context, lambda row: require_csrf(request, row), request.state.request_id
    )
    response.status_code = code
    return result


@router.get("/reviews/{review_id}/ai-analyses", response_model=Page[AnalysisView])
def history(
    review_id: UUID,
    context: Reader,
    ai: Service,
    response: Response,
    audience: Audience = Audience.PUBLIC,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[AnalysisView]:
    response.headers["Cache-Control"] = "no-store"
    return ai.history(review_id, audience, context.user, page, page_size)


@router.get("/reviews/{review_id}/ai-analyses/{analysis_id}", response_model=AnalysisView)
def detail(
    review_id: UUID, analysis_id: UUID, context: Reader, ai: Service, response: Response
) -> AnalysisView:
    response.headers["Cache-Control"] = "no-store"
    return ai.detail(review_id, analysis_id, context.user)
