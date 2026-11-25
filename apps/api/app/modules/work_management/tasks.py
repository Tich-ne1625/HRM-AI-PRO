from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.notifications.schemas import WorkItem as Task
from app.modules.review_cycles.models import CycleParticipant, ReviewCycle
from app.modules.users.models import User, UserRole
from app.modules.work_management.models import WorkItem, WorkPlan
from app.modules.work_management.repository import participant_query


def pending_tasks(session: Session, user: User) -> tuple[list[Task], bool]:
    """Derived workflow inbox; no writes and no claims of scheduled/offline reminders."""
    items: list[Task] = []
    participants = session.execute(
        participant_query(user)
        .outerjoin(WorkPlan, WorkPlan.participant_id == CycleParticipant.id)
        .where(WorkPlan.id.is_(None) | (WorkPlan.acknowledged_revision.is_(None)))
        .order_by(CycleParticipant.id)
        .limit(21)
    ).all()
    truncated = len(participants) > 20
    for participant, employee, cycle in participants[:20]:
        plan = session.scalar(select(WorkPlan).where(WorkPlan.participant_id == participant.id))
        manager = user.role == UserRole.MANAGER and employee.user_id != user.id
        title = (
            "Chuẩn bị / thống nhất kế hoạch"
            if manager
            else "Xem và xác nhận kế hoạch"
            if employee.user_id == user.id
            else "Theo dõi kế hoạch chưa được xác nhận"
        )
        items.append(
            Task(
                id=f"plan:{participant.id}",
                title=title,
                detail=f"{employee.display_name} · {cycle.name}",
                href=f"/work-management?plan={plan.id}"
                if plan
                else f"/work-management?cycle_id={cycle.id}",
                waiting=not manager and (not plan or plan.status != "APPROVED"),
            )
        )
    if user.role not in {UserRole.MANAGER, UserRole.EMPLOYEE}:
        return items, truncated
    base = participant_query(user, hr=False).subquery()
    query = (
        select(WorkItem, base.c.display_name, base.c.user_id)
        .join(WorkPlan, WorkItem.plan_id == WorkPlan.id)
        .join(base, WorkPlan.participant_id == base.c.id)
        .join(CycleParticipant, WorkPlan.participant_id == CycleParticipant.id)
        .join(ReviewCycle, CycleParticipant.cycle_id == ReviewCycle.id)
        .where(ReviewCycle.status == "ACTIVE", WorkItem.status.notin_(["ACCEPTED", "CANCELLED"]))
        .order_by(WorkItem.due_at, WorkItem.id)
        .limit(21)
    )
    rows = session.execute(query).all()
    for work, name, owner in rows[:20]:
        manager_step = work.status in {"SUBMITTED", "PROPOSED"} or work.blocked
        title = (
            "Hỗ trợ gỡ vướng"
            if work.blocked
            else "Xác minh bản nộp"
            if work.status == "SUBMITTED"
            else "Duyệt đề xuất việc"
            if work.status == "PROPOSED"
            else "Bổ sung công việc"
            if work.status == "CHANGES_REQUESTED"
            else "Thực hiện công việc"
        )
        items.append(
            Task(
                id=f"work:{work.id}",
                title=title,
                detail=f"{name} · {work.title}",
                href=f"/work-management?item={work.id}",
                waiting=manager_step == (owner == user.id),
            )
        )
    return items, truncated or len(rows) > 20
