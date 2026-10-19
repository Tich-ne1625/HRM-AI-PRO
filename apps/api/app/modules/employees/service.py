from collections.abc import Callable
from uuid import UUID

from sqlalchemy import Row, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.policies import AuthContext
from app.modules.audit.models import AuditValue
from app.modules.audit.service import AuditWriter
from app.modules.auth.models import AuthSession
from app.modules.employees.models import Employee, EmploymentStatus
from app.modules.employees.repository import EmployeeRepository, employee_scope
from app.modules.employees.schemas import (
    AccountLookup,
    AccountMatches,
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeView,
)
from app.modules.organization.models import Department, Position
from app.modules.organization.repository import OrganizationRepository
from app.modules.organization.schemas import Page
from app.modules.users.models import User


def view(row: Row[Employee, str, str, str | None]) -> EmployeeView:
    employee, department_name, position_title, manager_name = row
    return EmployeeView(
        id=employee.id,
        employee_code=employee.employee_code,
        display_name=employee.display_name,
        department_id=employee.department_id,
        department_name=department_name,
        position_id=employee.position_id,
        position_title=position_title,
        manager_id=employee.manager_id,
        manager_name=manager_name,
        user_id=employee.user_id,
        employment_status=employee.employment_status,
        created_at=employee.created_at,
        updated_at=employee.updated_at,
    )


class EmployeeService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = EmployeeRepository(session)

    def list(
        self,
        user: User,
        *,
        page: int,
        page_size: int,
        sort: str,
        department_id: UUID | None,
        position_id: UUID | None,
        employment_status: EmploymentStatus | None,
        q: str | None,
    ) -> Page[EmployeeView]:
        filters = [employee_scope(user)]
        if department_id is not None:
            filters.append(Employee.department_id == department_id)
        if position_id is not None:
            filters.append(Employee.position_id == position_id)
        if employment_status is not None:
            filters.append(Employee.employment_status == employment_status)
        if q:
            filters.append(
                or_(
                    Employee.display_name.icontains(q, autoescape=True),
                    Employee.employee_code.icontains(q, autoescape=True),
                )
            )
        with self.session.begin():
            total = (
                self.session.scalar(select(func.count()).select_from(Employee).where(*filters)) or 0
            )
            rows = self.session.execute(
                self.repository.view_query()
                .where(*filters)
                .order_by(getattr(Employee, sort), Employee.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            return Page(
                items=[view(row) for row in rows], total=total, page=page, page_size=page_size
            )

    def detail(self, employee_id: UUID, user: User) -> EmployeeView:
        with self.session.begin():
            row = self.session.execute(
                self.repository.view_query().where(
                    Employee.id == employee_id,
                    employee_scope(user),
                )
            ).one_or_none()
            if row is None:
                raise ApiError(404, "employee_not_found", "Employee not found")
            return view(row)

    def lookup(self, email: str) -> AccountMatches:
        with self.session.begin():
            row = self.session.execute(
                select(User, Employee.id)
                .outerjoin(
                    Employee,
                    Employee.user_id == User.id,
                )
                .where(User.email == email.casefold())
            ).one_or_none()
            return AccountMatches(
                items=[]
                if row is None
                else [
                    AccountLookup(
                        id=row[0].id,
                        email=row[0].email,
                        is_active=row[0].is_active,
                        employee_id=row[1],
                    )
                ]
            )

    def _validate_references(self, row: Employee, changed: set[str], *, creating: bool) -> None:
        for field in ("department_id", "position_id"):
            if creating or field in changed:
                reference = (
                    self.session.get(Department, row.department_id)
                    if field == "department_id"
                    else self.session.get(Position, row.position_id)
                )
                if reference is None:
                    raise ApiError(404, "reference_not_found", "Reference not found")
                if not reference.is_active:
                    raise ApiError(409, "reference_inactive", "Reference is inactive")
        if row.manager_id is not None and (creating or "manager_id" in changed):
            if self.repository.would_cycle(row.id, row.manager_id):
                raise ApiError(409, "reporting_cycle", "Reporting relationship creates a cycle")
            manager = self.repository.get(row.manager_id)
            if manager is None:
                raise ApiError(404, "employee_not_found", "Manager not found")
            if manager.employment_status != EmploymentStatus.ACTIVE:
                raise ApiError(409, "manager_inactive", "Manager is inactive")
        if row.user_id is not None and (creating or "user_id" in changed):
            if self.session.get(User, row.user_id) is None:
                raise ApiError(404, "user_not_found", "User not found")
            duplicate = self.session.scalar(
                select(Employee.id).where(
                    Employee.user_id == row.user_id,
                    Employee.id != row.id,
                )
            )
            if duplicate is not None:
                raise ApiError(409, "user_already_linked", "Account already linked to an employee")

    def write(
        self,
        body: EmployeeCreate | EmployeeUpdate,
        context: AuthContext,
        *,
        employee_id: UUID | None = None,
        csrf: Callable[[AuthSession], None],
        request_id: str,
    ) -> EmployeeView:
        try:
            with self.session.begin():
                guard = OrganizationRepository(self.session)
                guard.lock_guard()
                row = self.repository.get(employee_id) if employee_id is not None else None
                participants = {
                    identifier
                    for identifier in (
                        row.user_id if row else None,
                        body.user_id,
                    )
                    if identifier is not None
                }
                guard.authorize_write(context, csrf, participants)
                if employee_id is not None and row is None:
                    raise ApiError(404, "employee_not_found", "Employee not found")
                values = body.model_dump(exclude_unset=employee_id is not None)
                creating = employee_id is None
                if creating:
                    from uuid import uuid4

                    row = Employee(id=uuid4(), **values)
                assert row is not None
                previous_user = row.user_id if not creating else None
                previous_manager = row.manager_id if not creating else None
                changed = (
                    set(values)
                    if creating
                    else {field for field, value in values.items() if getattr(row, field) != value}
                )
                if not creating:
                    for field, value in values.items():
                        setattr(row, field, value)
                self._validate_references(row, changed, creating=creating)
                if creating:
                    self.repository.add(row)
                else:
                    self.session.flush()
                metadata: dict[str, AuditValue] = {
                    "changed_fields": ",".join(sorted(changed)),
                    "employee_code": row.employee_code,
                    "previous_user_id": str(previous_user) if previous_user else None,
                    "previous_manager_id": str(previous_manager) if previous_manager else None,
                }
                for field in (
                    "department_id",
                    "position_id",
                    "manager_id",
                    "user_id",
                    "employment_status",
                ):
                    if field in changed:
                        value = getattr(row, field)
                        metadata[field] = str(value) if value is not None else None
                AuditWriter().record(
                    self.session,
                    context.user.id,
                    f"employee.{'created' if creating else 'updated'}",
                    "employee",
                    str(row.id),
                    request_id,
                    metadata,
                )
                result = self.session.execute(
                    self.repository.view_query().where(Employee.id == row.id)
                ).one()
                return view(result)
        except IntegrityError as error:
            if getattr(error.orig, "sqlstate", None) == "23505":
                constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", "")
                code = (
                    "user_already_linked"
                    if constraint == "employees_user_id_key"
                    else "employee_code_already_exists"
                )
                raise ApiError(409, code, "Employee code or account link already exists") from None
            raise
