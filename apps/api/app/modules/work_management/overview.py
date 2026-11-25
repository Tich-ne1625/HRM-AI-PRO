from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.employees.models import Employee
from app.modules.employees.repository import employee_scope
from app.modules.review_cycles.models import CycleParticipant, ReviewCycle
from app.modules.users.models import User
from app.modules.work_management.models import WorkItem, WorkPlan


def overview(session: Session, user: User, cycle: ReviewCycle) -> dict[str, int]:
    scoped = (
        select(CycleParticipant.id)
        .join(Employee)
        .where(CycleParticipant.cycle_id == cycle.id, employee_scope(user))
    )
    participants = session.scalar(select(func.count()).select_from(scoped.subquery())) or 0
    plan_ids = select(WorkPlan.id).where(WorkPlan.participant_id.in_(scoped))
    plans, approved, acknowledged = session.execute(
        select(
            func.count(),
            func.count().filter(WorkPlan.status == "APPROVED"),
            func.count().filter(WorkPlan.acknowledged_revision == WorkPlan.revision),
        ).where(WorkPlan.id.in_(plan_ids))
    ).one()
    counts = dict(
        session.execute(
            select(WorkItem.status, func.count())
            .where(WorkItem.plan_id.in_(plan_ids))
            .group_by(WorkItem.status)
        ).all()
    )
    blocked = (
        session.scalar(
            select(func.count())
            .select_from(WorkItem)
            .where(
                WorkItem.plan_id.in_(plan_ids),
                WorkItem.blocked,
                WorkItem.status.notin_(["ACCEPTED", "CANCELLED"]),
            )
        )
        or 0
    )
    return {
        "participants": participants,
        "plans": plans,
        "approved": approved,
        "acknowledged": acknowledged,
        "missing_plans": participants - plans,
        "submitted": counts.get("SUBMITTED", 0),
        "accepted": counts.get("ACCEPTED", 0),
        "blocked": blocked,
        "open_work": sum(
            n for status, n in counts.items() if status not in {"ACCEPTED", "CANCELLED"}
        ),
    }
