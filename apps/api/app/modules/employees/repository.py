from typing import cast
from uuid import UUID

from sqlalchemy import Select, or_, select, true
from sqlalchemy.orm import Session, aliased
from sqlalchemy.sql.elements import ColumnElement

from app.modules.employees.models import Employee
from app.modules.organization.models import Department, Position
from app.modules.users.models import User, UserRole


def employee_scope(user: User) -> ColumnElement[bool]:
    if user.role == UserRole.HR:
        return true()
    identity = select(Employee.id).where(Employee.user_id == user.id).scalar_subquery()
    if user.role == UserRole.MANAGER:
        return or_(Employee.id == identity, Employee.manager_id == identity)
    return Employee.id == identity


class EmployeeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, employee_id: UUID) -> Employee | None:
        return self.session.scalar(
            select(Employee)
            .where(Employee.id == employee_id)
            .execution_options(populate_existing=True)
        )

    def view_query(self) -> Select[Employee, str, str, str | None]:
        manager = aliased(Employee)
        query = (
            select(Employee, Department.name, Position.title, manager.display_name)
            .join(Department, Employee.department_id == Department.id)
            .join(Position, Employee.position_id == Position.id)
            .outerjoin(manager, Employee.manager_id == manager.id)
        )
        # The outer join makes manager.display_name nullable at runtime.
        return cast(Select[Employee, str, str, str | None], query)

    def add(self, employee: Employee) -> Employee:
        self.session.add(employee)
        self.session.flush()
        return employee

    def would_cycle(self, employee_id: UUID, manager_id: UUID) -> bool:
        # Every graph writer holds the same transaction guard before this read.
        graph = {
            identifier: manager
            for identifier, manager in self.session.execute(
                select(Employee.id, Employee.manager_id)
            )
        }
        visited: set[UUID] = {employee_id}
        cursor: UUID | None = manager_id
        while cursor is not None:
            if cursor in visited:
                return True
            visited.add(cursor)
            cursor = graph.get(cursor)
        return False
