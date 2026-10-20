from sqlalchemy import Select, select, true
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.modules.employees.models import Employee
from app.modules.employees.repository import employee_scope
from app.modules.kpis.models import EmployeeKPI, KPIDefinition
from app.modules.review_cycles.models import CycleParticipant, CycleStatus, ReviewCycle
from app.modules.users.models import User, UserRole


def definition_scope(user: User) -> ColumnElement[bool]:
    if user.role == UserRole.HR:
        return true()
    return KPIDefinition.id.in_(
        select(EmployeeKPI.definition_id)
        .join(CycleParticipant, EmployeeKPI.participant_id == CycleParticipant.id)
        .join(ReviewCycle, CycleParticipant.cycle_id == ReviewCycle.id)
        .join(Employee, CycleParticipant.employee_id == Employee.id)
        .where(ReviewCycle.status != CycleStatus.DRAFT, employee_scope(user))
    )


class KPIRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def definitions(self, user: User) -> Select[KPIDefinition]:
        return select(KPIDefinition).where(definition_scope(user))
