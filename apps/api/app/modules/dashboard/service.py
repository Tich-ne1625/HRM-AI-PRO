from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import String, and_, case, cast, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.modules.dashboard.schemas import AdminDashboard, CycleOption, Dashboard, DepartmentMetric
from app.modules.employees.models import Employee, EmploymentStatus
from app.modules.employees.repository import employee_scope
from app.modules.feedback.models import AssignmentStatus, FeedbackAssignment
from app.modules.kpis.models import EmployeeKPI
from app.modules.organization.models import Department
from app.modules.performance.engine import ENGINE_VERSION
from app.modules.performance.models import PerformanceReview
from app.modules.performance.service import PerformanceService
from app.modules.review_cycles.models import CycleParticipant, CycleStatus, ReviewCycle
from app.modules.review_cycles.repository import cycle_scope
from app.modules.users.models import User, UserRole


def rounded(value: Decimal | None) -> Decimal | None:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if value is not None else None


class DashboardService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def read(self, user: User, cycle_id: UUID | None) -> Dashboard | AdminDashboard:
        PerformanceService(self.session).repeatable_read()
        pending = (
            self.session.scalar(
                select(func.count())
                .select_from(FeedbackAssignment)
                .join(CycleParticipant)
                .join(ReviewCycle)
                .where(
                    FeedbackAssignment.reviewer_id == user.id,
                    FeedbackAssignment.status == AssignmentStatus.OPEN,
                    CycleParticipant.finalized_at.is_(None),
                    ReviewCycle.status == CycleStatus.ACTIVE,
                )
            )
            or 0
        )
        if user.role == UserRole.ADMIN:
            # ADMIN is deliberately not passed to employee_scope (which allows self).
            if cycle_id is not None:
                raise ApiError(404, "cycle_not_found", "Review cycle not found")
            rows = self.session.execute(
                select(User.role, User.is_active, func.count()).group_by(User.role, User.is_active)
            ).all()
            return AdminDashboard(
                role=user.role,
                pending_feedback=pending,
                active_accounts=sum(n for _, active, n in rows if active),
                inactive_accounts=sum(n for _, active, n in rows if not active),
                account_roles={
                    r.value: sum(n for role, _, n in rows if role == r) for r in UserRole
                },
            )
        result = Dashboard(role=user.role, pending_feedback=pending)
        result.active_employees = (
            self.session.scalar(
                select(func.count())
                .select_from(Employee)
                .where(employee_scope(user), Employee.employment_status == EmploymentStatus.ACTIVE)
            )
            or 0
        )
        cycles = self.session.scalars(
            select(ReviewCycle)
            .where(cycle_scope(user))
            .order_by(
                case(
                    (ReviewCycle.status == CycleStatus.ACTIVE, 0),
                    (ReviewCycle.status == CycleStatus.CLOSED, 1),
                    else_=2,
                ),
                ReviewCycle.start_date.desc(),
                ReviewCycle.id.desc(),
            )
            .limit(101)
        ).all()
        result.cycles_truncated = len(cycles) > 100
        result.cycles = [CycleOption(id=c.id, name=c.name, status=c.status) for c in cycles[:100]]
        selected = None
        if cycle_id is not None:
            selected = self.session.scalar(
                select(ReviewCycle).where(ReviewCycle.id == cycle_id, cycle_scope(user))
            )
            if selected is None:
                raise ApiError(404, "cycle_not_found", "Review cycle not found")
        elif cycles:
            selected = cycles[0]
        if selected is None:
            return result
        result.selected_cycle = CycleOption(
            id=selected.id, name=selected.name, status=selected.status
        )
        # A pinned older cycle remains selectable even when outside the latest 100.
        if all(c.id != selected.id for c in result.cycles):
            result.cycles.append(result.selected_cycle)
        finalized = and_(
            PerformanceReview.finalized_at.is_not(None),
            PerformanceReview.finalized_at == CycleParticipant.finalized_at,
        )
        valid = or_(
            finalized,
            and_(
                PerformanceReview.evidence_version == CycleParticipant.evidence_version,
                PerformanceReview.engine_version == ENGINE_VERSION,
            ),
        )
        department = case(
            (ReviewCycle.status == CycleStatus.DRAFT, Department.name),
            else_=CycleParticipant.snapshot["department_name"].astext,
        )
        department_id = case(
            (ReviewCycle.status == CycleStatus.DRAFT, cast(Department.id, String)),
            else_=CycleParticipant.snapshot["department_id"].astext,
        )
        scoped = (
            select(
                CycleParticipant.id.label("participant_id"),
                department.label("department"),
                department_id.label("department_id"),
                PerformanceReview.id.label("review_id"),
                finalized.label("finalized"),
                func.coalesce(valid, False).label("valid"),
                PerformanceReview.final_score.label("score"),
            )
            .select_from(CycleParticipant)
            .join(Employee)
            .join(ReviewCycle)
            .join(Department, Employee.department_id == Department.id)
            .outerjoin(PerformanceReview, PerformanceReview.participant_id == CycleParticipant.id)
            .where(CycleParticipant.cycle_id == selected.id, employee_scope(user))
            .subquery()
        )
        c = scoped.c
        metrics = self.session.execute(
            select(
                func.count(),
                func.count().filter(c.finalized),
                func.count().filter(and_(c.valid, ~func.coalesce(c.finalized, False))),
                func.count().filter(and_(c.review_id.is_not(None), ~c.valid)),
                func.count().filter(c.review_id.is_(None)),
                func.count().filter(c.valid),
                func.avg(c.score).filter(c.valid),
                *(
                    func.count().filter(and_(c.valid, condition))
                    for condition in (
                        c.score < 65,
                        and_(c.score >= 65, c.score < 80),
                        and_(c.score >= 80, c.score < 90),
                        c.score >= 90,
                    )
                ),
            )
        ).one()
        (
            result.participants,
            result.finalized,
            result.current,
            result.stale,
            result.not_calculated,
            result.sample_size,
            average,
            *bands,
        ) = metrics
        result.average = rounded(average)
        result.score_bands = dict(zip(("<65", "65-<80", "80-<90", "≥90"), bands, strict=True))
        result.awaiting_completion = result.participants - result.finalized
        assigned, entered = self.session.execute(
            select(func.count(), func.count(EmployeeKPI.actual))
            .select_from(EmployeeKPI)
            .where(EmployeeKPI.participant_id.in_(select(c.participant_id)))
        ).one()
        result.kpis_assigned, result.kpis_entered = assigned, entered
        result.kpi_entry_percent = rounded(Decimal(entered) * 100 / assigned) if assigned else None
        departments = self.session.execute(
            select(
                c.department_id,
                c.department,
                func.count(),
                func.count().filter(c.valid),
                func.avg(c.score).filter(c.valid),
            )
            .group_by(c.department_id, c.department)
            .order_by(c.department, c.department_id)
            .limit(101)
        ).all()
        result.departments_truncated = len(departments) > 100
        result.departments = [
            DepartmentMetric(
                id=identifier,
                name=name or "Chưa có phòng ban",
                participants=count,
                sample_size=sample,
                average=rounded(avg),
            )
            for identifier, name, count, sample, avg in departments[:100]
        ]
        return result
