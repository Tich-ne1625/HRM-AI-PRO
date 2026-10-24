from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.core.policies import AuthContext, require_roles
from app.modules.audit.models import AuditLog
from app.modules.organization.schemas import Page
from app.modules.performance.service import PerformanceService
from app.modules.users.models import UserRole

# Exact action/type pairs, closed by default. No auth, password, AI or raw metadata.
ADMIN_EVENTS = frozenset(
    {
        ("user.created", "user"),
        ("user.role_changed", "user"),
        ("user.status_changed", "user"),
        ("scoring_defaults.updated", "system_config"),
    }
)
HR_EVENTS = frozenset(
    {
        *(
            (f"{entity}.{action}", entity)
            for entity in ("department", "position", "employee", "kpi_definition", "review_cycle")
            for action in ("created", "updated")
        ),
        ("review_cycle.activated", "review_cycle"),
        ("review_cycle.closed", "review_cycle"),
        ("cycle_participant.enrolled", "cycle_participant"),
        ("cycle_participant.removed", "cycle_participant"),
        ("kpi_allocation.replaced", "cycle_participant"),
        ("employee_kpi.actual_updated", "employee_kpi"),
        *(
            (f"assignment.{action}", "feedback_assignment")
            for action in ("created", "updated", "cancelled", "reopened", "replaced")
        ),
        ("feedback.submitted", "feedback_assignment"),
        ("performance.calculated", "performance_review"),
        ("performance.finalized", "performance_review"),
    }
)


class AuditView(BaseModel):
    id: UUID
    action: str
    entity_type: str
    entity_id: str
    created_at: datetime


router = APIRouter(prefix="/api/v1", tags=["audit"])


@router.get("/audit-logs", response_model=Page[AuditView])
def audit_logs(
    context: Annotated[AuthContext, Depends(require_roles(UserRole.ADMIN, UserRole.HR))],
    session: Annotated[Session, Depends(get_db_session)],
    response: Response,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    action: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
) -> Page[AuditView]:
    response.headers["Cache-Control"] = "no-store"
    PerformanceService(session).repeatable_read()
    events = ADMIN_EVENTS if context.user.role == UserRole.ADMIN else HR_EVENTS
    query = select(
        AuditLog.id, AuditLog.action, AuditLog.entity_type, AuditLog.entity_id, AuditLog.created_at
    ).where(tuple_(AuditLog.action, AuditLog.entity_type).in_(sorted(events)))
    if action is not None:
        query = query.where(AuditLog.action == action)
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.execute(
        query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).mappings()
    return Page(
        items=[AuditView.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )
