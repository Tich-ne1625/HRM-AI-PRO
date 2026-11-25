from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.modules.notifications.schemas import WorkItem as Task
from app.modules.progress.models import Checkin, CheckinAction, Measurement
from app.modules.review_cycles.models import ReviewCycle
from app.modules.users.models import User, UserRole
from app.modules.work_management.models import WorkPlan
from app.modules.work_management.repository import participant_query


def pending_tasks(session: Session, user: User) -> tuple[list[Task], bool]:
    if user.role not in {UserRole.MANAGER, UserRole.EMPLOYEE}:
        return [], False
    scope = participant_query(user, hr=False).subquery()
    plan_ids = (
        select(WorkPlan.id)
        .join(scope, WorkPlan.participant_id == scope.c.id)
        .join(ReviewCycle, scope.c.cycle_id == ReviewCycle.id)
        .where(ReviewCycle.status == "ACTIVE")
    )
    items: list[Task] = []
    measurement_rows = session.execute(
        select(Measurement, scope.c.user_id)
        .join(WorkPlan, Measurement.plan_id == WorkPlan.id)
        .join(scope, WorkPlan.participant_id == scope.c.id)
        .where(
            Measurement.plan_id.in_(plan_ids),
            Measurement.status.in_(["DRAFT", "SUBMITTED", "RETURNED"]),
        )
        .order_by(Measurement.created_at, Measurement.id)
        .limit(21)
    ).all()
    for row, owner in measurement_rows[:20]:
        manager_step = row.status == "SUBMITTED"
        items.append(
            Task(
                id=f"measurement:{row.id}",
                title="Xác minh số đo KPI" if manager_step else "Bổ sung và nộp số đo KPI",
                detail=f"Nguồn {row.source_label}",
                href=f"/work-management?measurement={row.id}",
                waiting=manager_step == (owner == user.id),
            )
        )
    meetings = session.execute(
        select(Checkin, scope.c.user_id)
        .join(WorkPlan, Checkin.plan_id == WorkPlan.id)
        .join(scope, WorkPlan.participant_id == scope.c.id)
        .where(
            Checkin.plan_id.in_(plan_ids),
            Checkin.status != "CANCELLED",
            or_(
                Checkin.status != "PUBLISHED",
                Checkin.clarification_pending,
                Checkin.acknowledged_publication.is_(None),
            ),
        )
        .order_by(Checkin.scheduled_at, Checkin.id)
        .limit(21)
    ).all()
    for row, owner in meetings[:20]:
        manager_step = row.status != "PUBLISHED" or row.clarification_pending
        items.append(
            Task(
                id=f"checkin:{row.id}",
                title="Chuẩn bị / phản hồi check-in" if manager_step else "Đọc biên bản check-in",
                detail="Rà soát hai chiều, xác nhận đã đọc không phải đồng ý đánh giá.",
                href=f"/work-management?checkin={row.id}",
                waiting=manager_step == (owner == user.id),
            )
        )
    actions = session.scalars(
        select(CheckinAction)
        .where(
            CheckinAction.plan_id.in_(plan_ids),
            CheckinAction.status.notin_(["DONE", "CANCELLED"]),
            or_(
                and_(CheckinAction.status == "SUBMITTED", CheckinAction.reviewer_id == user.id),
                and_(CheckinAction.status != "SUBMITTED", CheckinAction.owner_id == user.id),
            ),
        )
        .order_by(CheckinAction.due_at, CheckinAction.id)
        .limit(21)
    ).all()
    for row in actions[:20]:
        items.append(
            Task(
                id=f"checkin-action:{row.id}",
                title="Kiểm tra hỗ trợ đã hoàn thành"
                if row.status == "SUBMITTED"
                else "Thực hiện hành động hỗ trợ",
                detail="Có người phụ trách và thời hạn; không tự tạo điểm KPI.",
                href=f"/work-management?checkin={row.checkin_id}",
            )
        )
    return items[:40], any(len(rows) > 20 for rows in (measurement_rows, meetings, actions)) or len(
        items
    ) > 40
