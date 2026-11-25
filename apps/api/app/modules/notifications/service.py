from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.core.domain_writes import CsrfCheck, authorize_domain_write
from app.core.errors import ApiError
from app.core.policies import AuthContext
from app.modules.collaboration.models import ChatMessage, InternalPost
from app.modules.collaboration.service import post_scope
from app.modules.employees.models import Employee
from app.modules.employees.repository import employee_scope
from app.modules.feedback.models import AssignmentStatus, FeedbackAssignment
from app.modules.notifications.models import Notification
from app.modules.notifications.schemas import NotificationPage, NotificationView, WorkItem, WorkPage
from app.modules.performance.engine import ENGINE_VERSION
from app.modules.performance.evidence import collect
from app.modules.performance.models import PerformanceReview
from app.modules.review_cycles.models import CycleParticipant, CycleStatus, ReviewCycle
from app.modules.users.models import User, UserRole

TITLES = {
    "review_cycle.activated": "Đợt đánh giá đã bắt đầu",
    "review_cycle.closed": "Đợt đánh giá đã kết thúc",
    "assignment.created": "Bạn có phiếu phản hồi mới",
    "assignment.reopened": "Phiếu phản hồi đã được mở lại",
    "assignment.updated": "Phân công phản hồi đã cập nhật",
    "assignment.cancelled": "Phân công phản hồi đã được hủy",
    "assignment.replaced": "Phân công phản hồi đã được thay đổi",
    "kpi_allocation.replaced": "KPI được giao đã cập nhật",
    "employee_kpi.actual_updated": "Kết quả thực tế KPI đã cập nhật",
    "feedback.submitted": "Hồ sơ có phản hồi mới",
    "performance.calculated": "Kết quả đánh giá đã được tính",
    "performance.finalized": "Kết quả đánh giá đã được chốt",
    "ai_analysis.succeeded": "Tư vấn AI đã được lưu",
    "ai_analysis.failed": "Lượt tạo tư vấn chưa thành công",
}


def visible(user: User) -> ColumnElement[bool]:
    from app.modules.work_management.models import WorkPlan
    from app.modules.work_management.repository import work_scope

    work_notice = (
        select(WorkPlan.id)
        .join(CycleParticipant)
        .join(Employee)
        .where(WorkPlan.id == Notification.work_plan_id, work_scope(user, hr=False))
        .exists()
    )
    post_notice = (
        select(InternalPost.id)
        .where(InternalPost.id == Notification.post_id, post_scope(user))
        .exists()
    )
    message_notice = (
        select(ChatMessage.id)
        .where(ChatMessage.id == Notification.message_id, ChatMessage.recipient_id == user.id)
        .exists()
    )
    subject = (
        select(Employee.id)
        .where(Employee.id == Notification.employee_id, employee_scope(user))
        .exists()
    )
    own_assignment = (
        select(FeedbackAssignment.id)
        .where(
            FeedbackAssignment.id == Notification.assignment_id,
            FeedbackAssignment.reviewer_id == user.id,
        )
        .exists()
    )
    return and_(
        Notification.recipient_id == user.id,
        Notification.recipient_role == user.role.value,
        or_(
            work_notice,
            post_notice,
            message_notice,
            own_assignment,
            and_(Notification.assignment_id.is_(None), subject),
        ),
    )


def present(row: Notification, user: User, subject: str = "", cycle: str = "") -> NotificationView:
    if row.kind.startswith("progress."):
        title = {
            "progress.measurement.submit": "Có số đo KPI chờ xác minh",
            "progress.measurement.verify": "Số đo KPI đã được xác minh",
            "progress.measurement.return": "Số đo KPI cần bổ sung",
            "progress.measurement.reject": "Số đo KPI chưa được chấp nhận",
            "progress.checkin.create": "Bạn có lịch check-in mới",
            "progress.checkin.publish": "Biên bản check-in đã công bố",
            "progress.checkin.clarify": "Biên bản check-in cần làm rõ",
            "progress.checkin.addendum": "Có phụ lục check-in cần đọc",
            "progress.action.create": "Bạn có hành động hỗ trợ cần theo dõi",
        }.get(row.kind, "Tiến trình công việc có cập nhật")
        target = (
            f"measurement={row.measurement_id}"
            if row.measurement_id
            else f"checkin={row.checkin_id}"
            if row.checkin_id
            else f"plan={row.work_plan_id}"
        )
        return NotificationView(
            id=row.id,
            title=title,
            message="Mở để xem bước cần xử lý. Đọc thông báo không hoàn tất hành động.",
            href=f"/work-management?{target}",
            created_at=row.created_at,
            read_at=row.read_at,
        )
    if row.work_plan_id:
        titles = {
            "work.plan_submit": "Kế hoạch đã được gửi để thống nhất",
            "work.plan_approve": "Kế hoạch đã duyệt — hãy xác nhận đã nhận",
            "work.plan_clarify": "Kế hoạch cần làm rõ",
            "work.plan_acknowledge": "Nhân viên đã xác nhận kế hoạch",
            "work.created": "Có công việc mới cần tiếp nhận",
            "work.submit": "Có bằng chứng chờ nghiệm thu",
            "work.return": "Công việc cần bổ sung bằng chứng",
            "work.accept": "Công việc đã được nghiệm thu",
            "work.block": "Nhân viên cần hỗ trợ gỡ vướng",
        }
        target = f"item={row.work_item_id}" if row.work_item_id else f"plan={row.work_plan_id}"
        return NotificationView(
            id=row.id,
            title=titles.get(row.kind, "Công việc có cập nhật"),
            message="Mở để xem nội dung và người đang giữ bước tiếp theo.",
            href=f"/work-management?{target}",
            created_at=row.created_at,
            read_at=row.read_at,
        )
    if row.post_id or row.message_id:
        title = {
            "collaboration.post": "Bảng tin có bài viết mới",
            "collaboration.comment": "Có trao đổi hoặc @nhắc bạn trong bài viết",
            "collaboration.mention": "Bạn được @nhắc trong tin nhắn",
            "collaboration.message": "Bạn có tin nhắn mới",
        }.get(row.kind, "Trao đổi mới")
        href = f"/news?post={row.post_id}" if row.post_id else f"/news?message={row.message_id}"
        return NotificationView(
            id=row.id,
            title=title,
            message="Mở để xem nội dung trong phạm vi của bạn.",
            href=href,
            created_at=row.created_at,
            read_at=row.read_at,
        )
    href = f"/employees/{row.employee_id}/performance?cycle_id={row.cycle_id}"
    message = "Mở hồ sơ để xem cập nhật trong phạm vi của bạn."
    if row.assignment_id:
        href = f"/feedback/{row.assignment_id}"
        message = "Kiểm tra người được đánh giá, thời hạn và trạng thái phiếu."
    elif row.kind in {"kpi_allocation.replaced", "employee_kpi.actual_updated"}:
        href = f"/employees/{row.employee_id}/kpis?cycle_id={row.cycle_id}"
    elif row.kind.startswith("review_cycle."):
        href = f"/review-cycles/{row.cycle_id}"
        message = "Mở chu kỳ để theo dõi phần việc của bạn."
    elif row.kind == "performance.calculated" and user.role == UserRole.HR:
        message = "Quản lý đã tính điểm. Kiểm tra bằng chứng và chốt khi kết quả hợp lệ."
    elif row.kind == "feedback.submitted" and user.role == UserRole.MANAGER:
        message = "Kiểm tra phần còn thiếu; tính hoặc tính lại điểm khi đã đủ bằng chứng."
    label = (
        cycle
        if row.kind.startswith("review_cycle.")
        else " · ".join(value for value in (subject, cycle) if value)
    )
    if label:
        message = f"{label}. {message}"
    return NotificationView(
        id=row.id,
        title=TITLES.get(row.kind, "Công việc đã cập nhật"),
        message=message,
        href=href,
        created_at=row.created_at,
        read_at=row.read_at,
    )


class NotificationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self, user: User, *, page: int, page_size: int, unread: bool) -> NotificationPage:
        with self.session.begin():
            self.session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            allowed = visible(user)
            unread_count = (
                self.session.scalar(
                    select(func.count())
                    .select_from(Notification)
                    .where(allowed, Notification.read_at.is_(None))
                )
                or 0
            )
            filters = [allowed] + ([Notification.read_at.is_(None)] if unread else [])
            total = (
                self.session.scalar(select(func.count()).select_from(Notification).where(*filters))
                or 0
            )
            rows = list(
                self.session.scalars(
                    select(Notification)
                    .where(*filters)
                    .order_by(Notification.created_at.desc(), Notification.id.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            subjects = dict(
                self.session.execute(
                    select(Employee.id, Employee.display_name).where(
                        Employee.id.in_([row.employee_id for row in rows])
                    )
                ).all()
            )
            cycles = dict(
                self.session.execute(
                    select(ReviewCycle.id, ReviewCycle.name).where(
                        ReviewCycle.id.in_([row.cycle_id for row in rows])
                    )
                ).all()
            )
            return NotificationPage(
                items=[
                    present(
                        row,
                        user,
                        subjects.get(row.employee_id, "") if row.employee_id else "",
                        cycles.get(row.cycle_id, "") if row.cycle_id else "",
                    )
                    for row in rows
                ],
                total=total,
                unread_count=unread_count,
                page=page,
                page_size=page_size,
            )

    def read(self, context: AuthContext, csrf: CsrfCheck, identifier: UUID | None) -> None:
        with self.session.begin():
            user = authorize_domain_write(self.session, context, csrf, tuple(UserRole))
            conditions = [visible(user)]
            if identifier is not None:
                conditions.append(Notification.id == identifier)
                if not self.session.scalar(select(Notification.id).where(*conditions)):
                    raise ApiError(404, "notification_not_found", "Notification not found")
            self.session.execute(
                update(Notification)
                .where(*conditions, Notification.read_at.is_(None))
                .values(read_at=datetime.now(UTC))
            )
            self.session.execute(
                text("SELECT pg_notify('insighthr_notifications', :recipient)"),
                {"recipient": str(user.id)},
            )

    def tasks(self, user: User) -> WorkPage:
        with self.session.begin():
            self.session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            assignments = list(
                self.session.execute(
                    select(FeedbackAssignment, Employee, ReviewCycle)
                    .join(
                        CycleParticipant, FeedbackAssignment.participant_id == CycleParticipant.id
                    )
                    .join(Employee, CycleParticipant.employee_id == Employee.id)
                    .join(ReviewCycle, CycleParticipant.cycle_id == ReviewCycle.id)
                    .where(
                        FeedbackAssignment.reviewer_id == user.id,
                        FeedbackAssignment.status == AssignmentStatus.OPEN,
                        ReviewCycle.status == CycleStatus.ACTIVE,
                        CycleParticipant.finalized_at.is_(None),
                    )
                    .order_by(FeedbackAssignment.due_at.asc().nulls_last(), FeedbackAssignment.id)
                    .limit(21)
                )
            )
            items = [
                WorkItem(
                    id=f"assignment:{row.id}",
                    title="Gửi phản hồi được giao",
                    detail=f"{employee.display_name} · {cycle.name}",
                    href=f"/feedback/{row.id}",
                )
                for row, employee, cycle in assignments[:20]
            ]
            truncated = len(assignments) > 20
            from app.modules.work_management.tasks import pending_tasks

            work_items, work_truncated = pending_tasks(self.session, user)
            items.extend(work_items)
            truncated = truncated or work_truncated
            from app.modules.progress.tasks import pending_tasks as progress_tasks

            progress_items, progress_truncated = progress_tasks(self.session, user)
            items.extend(progress_items)
            truncated = truncated or progress_truncated
            if user.role not in (UserRole.HR, UserRole.MANAGER):
                return WorkPage(items=items, truncated=truncated)
            scope = employee_scope(user)
            if user.role == UserRole.MANAGER:
                actor_id = select(Employee.id).where(Employee.user_id == user.id).scalar_subquery()
                scope = and_(Employee.manager_id == actor_id, Employee.id != actor_id)
            rows = list(
                self.session.execute(
                    select(CycleParticipant, Employee, ReviewCycle)
                    .join(Employee)
                    .join(ReviewCycle)
                    .where(
                        scope,
                        ReviewCycle.status == CycleStatus.ACTIVE,
                        ReviewCycle.workflow_mode == "LEGACY",
                        CycleParticipant.finalized_at.is_(None),
                    )
                    .order_by(Employee.employee_code, CycleParticipant.id)
                    .limit(21)
                )
            )
            truncated = truncated or len(rows) > 20
            reviews = {
                row.participant_id: row
                for row in self.session.scalars(
                    select(PerformanceReview).where(
                        PerformanceReview.participant_id.in_(
                            [participant.id for participant, _, _ in rows]
                        )
                    )
                )
            }
            for participant, employee, cycle in rows[:20]:
                evidence = collect(self.session, participant, employee, cycle)
                issues = {issue.code for issue in evidence.readiness.issues}
                review = reviews.get(participant.id)
                hr = user.role == UserRole.HR
                href = f"/employees/{employee.id}/performance?cycle_id={cycle.id}"
                waiting = hr
                relationships = {
                    row["relationship"]
                    for row in evidence.snapshot["assignments"]
                    if row["status"] != "CANCELLED"
                }
                missing_assignment = hr and not {"SELF", "MANAGER"}.issubset(relationships)
                if missing_assignment:
                    items.append(
                        WorkItem(
                            id=f"coverage:{participant.id}",
                            title="Giao phản hồi bắt buộc",
                            detail=f"{employee.display_name} · {cycle.name}",
                            href=f"/feedback-administration?participant_id={participant.id}&cycle_id={cycle.id}",
                        )
                    )
                if "kpi_allocation_required" in issues:
                    title = "Chờ quản lý giao KPI" if hr else "Giao KPI cho nhân viên"
                    href = f"/employees/{employee.id}/kpis?cycle_id={cycle.id}"
                elif "kpi_actual_required" in issues:
                    title = "Chờ quản lý nhập thực tế" if hr else "Nhập kết quả thực tế KPI"
                    href = f"/employees/{employee.id}/kpis?cycle_id={cycle.id}"
                elif (
                    "allocation_or_policy_invalid" in issues
                    or "scoring_policy_incompatible" in issues
                ):
                    title = "Chờ quản lý kiểm tra phân bổ KPI" if hr else "Kiểm tra phân bổ KPI"
                    href = f"/employees/{employee.id}/kpis?cycle_id={cycle.id}"
                elif issues:
                    if missing_assignment:
                        continue
                    title = (
                        "Kiểm tra phân công / dữ liệu còn thiếu"
                        if hr
                        else "Chờ đủ bằng chứng để tính điểm"
                    )
                    waiting = not hr
                    if hr:
                        href = (
                            f"/feedback-administration?participant_id={participant.id}"
                            f"&cycle_id={cycle.id}"
                        )
                elif (
                    review is None
                    or review.evidence_version != participant.evidence_version
                    or review.engine_version != ENGINE_VERSION
                ):
                    title = "Chờ quản lý tính điểm" if hr else "Tính / tính lại điểm hiệu suất"
                else:
                    title = "Kiểm tra và chốt kết quả" if hr else "Chờ HR kiểm tra và chốt"
                    waiting = not hr
                items.append(
                    WorkItem(
                        id=f"participant:{participant.id}",
                        title=title,
                        detail=f"{employee.display_name} · {cycle.name}",
                        href=href,
                        waiting=waiting,
                    )
                )
            if user.role == UserRole.HR:
                remaining = (
                    select(CycleParticipant.id)
                    .where(
                        CycleParticipant.cycle_id == ReviewCycle.id,
                        CycleParticipant.finalized_at.is_(None),
                    )
                    .exists()
                )
                for cycle in self.session.scalars(
                    select(ReviewCycle).where(
                        ReviewCycle.status == CycleStatus.ACTIVE,
                        ~remaining,
                        ReviewCycle.workflow_mode == "LEGACY",
                    )
                ):
                    items.insert(
                        0,
                        WorkItem(
                            id=f"close:{cycle.id}",
                            title="Đóng chu kỳ đã hoàn tất",
                            detail=cycle.name,
                            href=f"/review-cycles/{cycle.id}",
                        ),
                    )
            return WorkPage(items=items, truncated=truncated)
