"""Bounded, SQL-scoped saved advice directory. Never construct a provider client."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.modules.ai.models import AIAnalysis, AnalysisStatus
from app.modules.ai.schemas import Audience
from app.modules.employees.models import Employee
from app.modules.employees.repository import employee_scope
from app.modules.organization.schemas import Page
from app.modules.performance.engine import ENGINE_VERSION
from app.modules.performance.models import PerformanceReview
from app.modules.performance.service import PerformanceService
from app.modules.review_cycles.models import CycleParticipant, CycleStatus, ReviewCycle
from app.modules.review_cycles.repository import CycleRepository
from app.modules.users.models import User, UserRole


class SavedReport(BaseModel):
    id: UUID
    review_id: UUID
    employee_id: UUID
    display_name: str
    cycle_id: UUID
    cycle_name: str
    audience: Audience
    generation_version: int
    calculation_version: int
    model: str
    generated_at: datetime
    matches_current_calculation: bool


def saved_reports(
    session: Session,
    user: User,
    audience: Audience,
    cycle_id: UUID | None,
    page: int,
    page_size: int,
) -> Page[SavedReport]:
    if user.role not in (UserRole.HR, UserRole.MANAGER, UserRole.EMPLOYEE):
        raise ApiError(403, "forbidden", "Access is forbidden")
    if audience == Audience.HR_PRIVATE and user.role != UserRole.HR:
        raise ApiError(403, "forbidden", "Access is forbidden")
    PerformanceService(session).repeatable_read()
    if cycle_id is not None:
        CycleRepository(session).get(cycle_id, user)
    finalized = and_(
        PerformanceReview.finalized_at.is_not(None),
        PerformanceReview.finalized_at == CycleParticipant.finalized_at,
    )
    current = and_(
        AIAnalysis.calculation_version == PerformanceReview.calculation_version,
        AIAnalysis.evidence_hash == PerformanceReview.evidence_hash,
        or_(
            finalized,
            and_(
                PerformanceReview.evidence_version == CycleParticipant.evidence_version,
                PerformanceReview.engine_version == ENGINE_VERSION,
            ),
        ),
    )
    # Project metadata only: neither output nor private prompt/evidence enters this query.
    query = (
        select(
            AIAnalysis.id,
            AIAnalysis.review_id,
            Employee.id.label("employee_id"),
            case(
                (
                    CycleParticipant.snapshot.is_not(None),
                    CycleParticipant.snapshot["display_name"].astext,
                ),
                else_=Employee.display_name,
            ).label("display_name"),
            ReviewCycle.id.label("cycle_id"),
            ReviewCycle.name.label("cycle_name"),
            AIAnalysis.audience,
            AIAnalysis.generation_version,
            AIAnalysis.calculation_version,
            AIAnalysis.model,
            AIAnalysis.generated_at,
            func.coalesce(current, False).label("matches_current_calculation"),
        )
        .select_from(AIAnalysis)
        .join(PerformanceReview, AIAnalysis.review_id == PerformanceReview.id)
        .join(CycleParticipant, PerformanceReview.participant_id == CycleParticipant.id)
        .join(Employee, CycleParticipant.employee_id == Employee.id)
        .join(ReviewCycle, CycleParticipant.cycle_id == ReviewCycle.id)
        .where(
            employee_scope(user),
            ReviewCycle.status != CycleStatus.DRAFT,
            AIAnalysis.audience == audience,
            AIAnalysis.status == AnalysisStatus.SUCCEEDED,
        )
    )
    if cycle_id is not None:
        query = query.where(ReviewCycle.id == cycle_id)
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.execute(
        query.order_by(AIAnalysis.generated_at.desc(), AIAnalysis.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).mappings()
    return Page(
        items=[SavedReport.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )
