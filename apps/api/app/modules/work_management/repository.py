from uuid import UUID

from sqlalchemy import Select, and_, false, or_, select, true
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.core.errors import ApiError
from app.modules.employees.models import Employee, EmploymentStatus
from app.modules.review_cycles.models import CycleParticipant, ReviewCycle, WorkflowMode
from app.modules.users.models import User, UserRole
from app.modules.work_management.models import WorkPlan


def work_scope(user: User, *, hr: bool = True) -> ColumnElement[bool]:
    if user.role == UserRole.HR:
        return true() if hr else false()
    if user.role == UserRole.ADMIN:
        return false()
    own = Employee.user_id == user.id
    if user.role == UserRole.MANAGER:
        manager = (
            select(Employee.id)
            .where(
                Employee.user_id == user.id, Employee.employment_status == EmploymentStatus.ACTIVE
            )
            .scalar_subquery()
        )
        return or_(own, and_(Employee.manager_id == manager, Employee.id != manager))
    return own


def participant_query(
    user: User, *, hr: bool = True
) -> Select[CycleParticipant, Employee, ReviewCycle]:
    return (
        select(CycleParticipant, Employee, ReviewCycle)
        .join(Employee, CycleParticipant.employee_id == Employee.id)
        .join(ReviewCycle, CycleParticipant.cycle_id == ReviewCycle.id)
        .where(ReviewCycle.workflow_mode == WorkflowMode.CONTINUOUS, work_scope(user, hr=hr))
    )


class WorkRepository:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.managers: dict[UUID | None, User | None] = {}

    def prime(self, employees: list[Employee]) -> None:
        """Batch directory data for paged boards; never load the entire company."""
        ids = {e.manager_id for e in employees if e.manager_id}
        rows = self.session.execute(
            select(Employee.id, User)
            .join(User, Employee.user_id == User.id)
            .where(
                Employee.id.in_(ids),
                User.is_active,
                User.role == UserRole.MANAGER,
                Employee.employment_status == EmploymentStatus.ACTIVE,
            )
        )
        self.managers.update(dict.fromkeys(ids))
        self.managers.update({identifier: account for identifier, account in rows})
        # Retain account identity-map entries for operational checks on the same page.
        self.accounts = {
            u.id: u
            for u in self.session.scalars(
                select(User).where(User.id.in_([e.user_id for e in employees if e.user_id]))
            )
        }

    def participant(
        self, identifier: UUID, user: User, *, lock: bool = False, hr: bool = True
    ) -> tuple[CycleParticipant, Employee, ReviewCycle]:
        query = participant_query(user, hr=hr).where(CycleParticipant.id == identifier)
        row = self.session.execute(query).one_or_none()
        if row is None:
            raise ApiError(404, "work_not_found", "Work record not found")
        if lock:
            # The organization guard and user/session locks have already been acquired.
            self.session.scalar(
                select(ReviewCycle)
                .where(ReviewCycle.id == row[2].id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            self.session.scalar(
                select(CycleParticipant)
                .where(CycleParticipant.id == identifier)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        return row[0], row[1], row[2]

    def plan(
        self, identifier: UUID, user: User, *, lock: bool = False, hr: bool = True
    ) -> tuple[WorkPlan, CycleParticipant, Employee, ReviewCycle]:
        row = self.session.get(WorkPlan, identifier)
        if row is None:
            raise ApiError(404, "work_not_found", "Work record not found")
        participant, employee, cycle = self.participant(row.participant_id, user, lock=lock, hr=hr)
        if lock:
            self.session.refresh(row, with_for_update=True)
        return row, participant, employee, cycle

    def manager(self, employee: Employee) -> User | None:
        if employee.manager_id in self.managers:
            return self.managers[employee.manager_id]
        account = self.session.scalar(
            select(User)
            .join(Employee, Employee.user_id == User.id)
            .where(
                Employee.id == employee.manager_id,
                Employee.employment_status == EmploymentStatus.ACTIVE,
                User.role == UserRole.MANAGER,
                User.is_active,
            )
        )
        self.managers[employee.manager_id] = account
        return account

    def require_manager(self, employee: Employee, user: User) -> None:
        manager = self.manager(employee)
        if (
            not manager
            or manager.id != user.id
            or employee.user_id == user.id
            or employee.employment_status != EmploymentStatus.ACTIVE
            or not self.operational(employee)
        ):
            raise ApiError(
                403, "forbidden", "Only the current direct manager may perform this step"
            )

    def operational(self, employee: Employee) -> bool:
        account = self.session.get(User, employee.user_id) if employee.user_id else None
        return bool(
            account
            and account.is_active
            and account.role in {UserRole.EMPLOYEE, UserRole.MANAGER}
            and employee.employment_status == EmploymentStatus.ACTIVE
            and self.manager(employee)
        )


def require_legacy(cycle: ReviewCycle) -> None:
    if cycle.workflow_mode == WorkflowMode.CONTINUOUS:
        raise ApiError(
            409,
            "managed_by_workflow",
            "Continuous cycles use work plans; scoring awaits the verified ledger",
        )


def activation_issues(
    session: Session, participants: list[CycleParticipant]
) -> list[dict[str, object]]:
    plans = {
        p.participant_id: p
        for p in session.scalars(
            select(WorkPlan)
            .where(WorkPlan.participant_id.in_([p.id for p in participants]))
            .order_by(WorkPlan.id)
            .with_for_update()
        )
    }
    repository = WorkRepository(session)
    issues: list[dict[str, object]] = []
    for participant in participants:
        plan = plans.get(participant.id)
        employee = session.get(Employee, participant.employee_id)
        assert employee is not None
        manager = repository.manager(employee)
        code = (
            "active_work_accounts_required"
            if not manager or not repository.operational(employee)
            else "plan_approval_required"
            if not plan or plan.status != "APPROVED"
            else "plan_manager_changed"
            if plan.approved_by != manager.id
            else "plan_acknowledgement_required"
            if plan.acknowledged_revision != plan.revision
            else None
        )
        if code:
            issues.append({"employee_id": str(employee.id), "code": code})
    return issues


def guard_organization_change(session: Session, employee_id: UUID) -> None:
    affected = session.scalar(
        select(CycleParticipant.id)
        .join(ReviewCycle)
        .join(Employee)
        .where(
            ReviewCycle.workflow_mode == WorkflowMode.CONTINUOUS,
            ReviewCycle.status == "ACTIVE",
            or_(Employee.id == employee_id, Employee.manager_id == employee_id),
        )
        .limit(1)
    )
    if affected:
        raise ApiError(
            409,
            "active_workflow_handover_required",
            "Active continuous work requires a documented handover before this change",
        )
