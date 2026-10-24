from uuid import UUID

from sqlalchemy import String, case, cast, select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog
from app.modules.dashboard.schemas import Activity
from app.modules.employees.models import Employee
from app.modules.employees.repository import employee_scope
from app.modules.performance.models import PerformanceReview
from app.modules.review_cycles.models import CycleParticipant, CycleStatus, ReviewCycle
from app.modules.users.models import User, UserRole


def recent_activities(session: Session, user: User, cycle_id: UUID | None) -> list[Activity]:
    # Explicit projection and action allowlists: never return actor, metadata or request IDs.
    query = select(AuditLog.id, AuditLog.action, AuditLog.created_at.label("occurred_at"))
    if user.role == UserRole.ADMIN:
        query = query.where(
            AuditLog.entity_type == "user",
            AuditLog.action.in_(("user.created", "user.role_changed", "user.status_changed")),
        )
    elif cycle_id is not None:
        query = (
            query.add_columns(
                Employee.id.label("employee_id"),
                case(
                    (
                        CycleParticipant.snapshot.is_not(None),
                        CycleParticipant.snapshot["display_name"].astext,
                    ),
                    else_=Employee.display_name,
                ).label("display_name"),
                CycleParticipant.cycle_id,
            )
            # Compare strings rather than casting arbitrary audit identifiers to UUID.
            .join(PerformanceReview, AuditLog.entity_id == cast(PerformanceReview.id, String))
            .join(CycleParticipant, PerformanceReview.participant_id == CycleParticipant.id)
            .join(Employee, CycleParticipant.employee_id == Employee.id)
            .join(ReviewCycle, CycleParticipant.cycle_id == ReviewCycle.id)
            .where(
                AuditLog.entity_type == "performance_review",
                AuditLog.action.in_(("performance.calculated", "performance.finalized")),
                CycleParticipant.cycle_id == cycle_id,
                employee_scope(user),
                ReviewCycle.status != CycleStatus.DRAFT,
            )
        )
    else:
        return []
    return [
        Activity.model_validate(row)
        for row in session.execute(
            query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(6)
        ).mappings()
    ]
