from uuid import UUID

from sqlalchemy import Select, and_, select, true
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.core.errors import ApiError
from app.modules.employees.models import Employee, EmploymentStatus
from app.modules.employees.repository import employee_scope
from app.modules.organization.models import Department, Position
from app.modules.review_cycles.models import CycleParticipant, CycleStatus, ReviewCycle
from app.modules.review_cycles.schemas import ParticipantSnapshot, ParticipantView
from app.modules.users.models import User, UserRole


def cycle_scope(user: User) -> ColumnElement[bool]:
    if user.role == UserRole.HR:
        return true()
    scoped = (
        select(CycleParticipant.id)
        .join(Employee)
        .where(
            CycleParticipant.cycle_id == ReviewCycle.id,
            employee_scope(user),
        )
        .exists()
    )
    return and_(ReviewCycle.status != CycleStatus.DRAFT, scoped)


def participant_scope(user: User) -> ColumnElement[bool]:
    if user.role == UserRole.HR:
        return true()
    return and_(ReviewCycle.status != CycleStatus.DRAFT, employee_scope(user))


def can_write_kpis(
    user: User,
    employee: Employee,
    actor_employee: Employee | None,
    cycle: ReviewCycle,
    participant: CycleParticipant,
) -> bool:
    if cycle.status != CycleStatus.ACTIVE or participant.finalized_at is not None:
        return False
    if user.role == UserRole.HR:
        return True
    return bool(
        user.role == UserRole.MANAGER
        and actor_employee
        and actor_employee.employment_status == EmploymentStatus.ACTIVE
        and employee.employment_status == EmploymentStatus.ACTIVE
        and employee.manager_id == actor_employee.id
        and employee.id != actor_employee.id
    )


class CycleRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, identifier: UUID, user: User, *, lock: bool = False) -> ReviewCycle:
        query = select(ReviewCycle).where(ReviewCycle.id == identifier, cycle_scope(user))
        if lock:
            query = query.with_for_update()
        row = self.session.scalar(query.execution_options(populate_existing=True))
        if row is None:
            raise ApiError(404, "cycle_not_found", "Review cycle not found")
        return row

    def actor_employee(self, user: User) -> Employee | None:
        return self.session.scalar(
            select(Employee)
            .where(Employee.user_id == user.id)
            .execution_options(populate_existing=True)
        )

    def participants(self, cycle_id: UUID, user: User) -> Select[CycleParticipant, Employee]:
        return (
            select(CycleParticipant, Employee)
            .join(
                Employee,
                CycleParticipant.employee_id == Employee.id,
            )
            .join(ReviewCycle, CycleParticipant.cycle_id == ReviewCycle.id)
            .where(
                CycleParticipant.cycle_id == cycle_id,
                participant_scope(user),
            )
        )

    def participant_for_employee(
        self, employee_id: UUID, cycle_id: UUID, user: User, *, lock: bool = False
    ) -> tuple[CycleParticipant, Employee, ReviewCycle]:
        query = (
            select(CycleParticipant, Employee, ReviewCycle)
            .join(
                Employee,
                CycleParticipant.employee_id == Employee.id,
            )
            .join(ReviewCycle, CycleParticipant.cycle_id == ReviewCycle.id)
            .where(
                CycleParticipant.employee_id == employee_id,
                CycleParticipant.cycle_id == cycle_id,
                participant_scope(user),
            )
        )
        if lock:
            # Caller locks cycle first; all evidence writers lock this same participant.
            query = query.with_for_update(of=CycleParticipant)
        result = self.session.execute(query.execution_options(populate_existing=True)).one_or_none()
        if result is None:
            raise ApiError(404, "participant_not_found", "Cycle participant not found")
        return result[0], result[1], result[2]

    def present_participant(
        self,
        participant: CycleParticipant,
        employee: Employee,
        cycle: ReviewCycle,
        user: User,
        actor_employee: Employee | None,
    ) -> ParticipantView:
        if participant.snapshot is not None:
            snapshot = ParticipantSnapshot.model_validate(participant.snapshot)
            code, name = snapshot.employee_code, snapshot.display_name
            department_id, department_name = snapshot.department_id, snapshot.department_name
            position_title = snapshot.position_title
        else:
            department = self.session.get(Department, employee.department_id)
            position = self.session.get(Position, employee.position_id)
            assert department is not None and position is not None
            code, name = employee.employee_code, employee.display_name
            department_id, department_name = department.id, department.name
            position_title = position.title
        return ParticipantView(
            id=participant.id,
            cycle_id=cycle.id,
            employee_id=employee.id,
            employee_code=code,
            display_name=name,
            department_id=department_id,
            department_name=department_name,
            position_title=position_title,
            evidence_version=participant.evidence_version,
            is_snapshot=participant.snapshot is not None,
            can_manage_kpis=can_write_kpis(user, employee, actor_employee, cycle, participant),
        )
