from collections.abc import Callable, Sequence
from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.policies import AuthContext
from app.modules.audit.service import AuditWriter
from app.modules.auth.models import AuthSession
from app.modules.employees.models import Employee
from app.modules.employees.repository import employee_scope
from app.modules.organization.models import Department, Position
from app.modules.organization.repository import OrganizationRepository
from app.modules.organization.schemas import DepartmentView, Page, PositionView
from app.modules.users.models import User, UserRole

ReferenceView = DepartmentView | PositionView


class ReferenceService:
    def __init__(self, session: Session, kind: Literal["department", "position"]) -> None:
        self.session = session
        self.kind = kind
        self.model: type[Department] | type[Position] = (
            Department if kind == "department" else Position
        )

    @staticmethod
    def view(row: Department | Position) -> ReferenceView:
        return (
            DepartmentView.model_validate(row)
            if isinstance(row, Department)
            else PositionView.model_validate(row)
        )

    def list(
        self,
        user: User,
        *,
        page: int,
        page_size: int,
        sort: str,
        is_active: bool | None,
        q: str | None = None,
    ) -> Page[ReferenceView]:
        filters = []
        if is_active is not None:
            filters.append(self.model.is_active == is_active)
        if q:
            label = getattr(self.model, "name" if self.kind == "department" else "title")
            filters.append(
                or_(
                    self.model.code.icontains(q, autoescape=True),
                    label.icontains(q, autoescape=True),
                )
            )
        if user.role != UserRole.HR:
            reference = (
                Employee.department_id if self.kind == "department" else Employee.position_id
            )
            filters.append(self.model.id.in_(select(reference).where(employee_scope(user))))
        with self.session.begin():
            total = (
                self.session.scalar(select(func.count()).select_from(self.model).where(*filters))
                or 0
            )
            rows = self.session.scalars(
                select(self.model)
                .where(*filters)
                .order_by(getattr(self.model, sort), self.model.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            return Page(
                items=[self.view(row) for row in cast(Sequence[Department | Position], rows)],
                total=total,
                page=page,
                page_size=page_size,
            )

    def write(
        self,
        body: BaseModel,
        context: AuthContext,
        *,
        record_id: UUID | None = None,
        csrf: Callable[[AuthSession], None],
        request_id: str,
    ) -> ReferenceView:
        try:
            with self.session.begin():
                repository = OrganizationRepository(self.session)
                repository.lock_guard()
                repository.authorize_write(context, csrf)
                values = body.model_dump(exclude_unset=record_id is not None)
                if record_id is None:
                    row = self.model(**values)
                    self.session.add(row)
                else:
                    row = self.session.scalar(
                        select(self.model)
                        .where(self.model.id == record_id)
                        .with_for_update()
                        .execution_options(populate_existing=True)
                    )
                    if row is None:
                        raise ApiError(404, "reference_not_found", "Reference not found")
                    for field, value in values.items():
                        setattr(row, field, value)
                self.session.flush()
                AuditWriter().record(
                    self.session,
                    context.user.id,
                    f"{self.kind}.{'created' if record_id is None else 'updated'}",
                    self.kind,
                    str(row.id),
                    request_id,
                    {
                        "code": row.code,
                        "is_active": row.is_active,
                        "changed_fields": ",".join(sorted(values)),
                    },
                )
                return self.view(row)
        except IntegrityError as error:
            if getattr(error.orig, "sqlstate", None) == "23505":
                raise ApiError(409, "duplicate_code", "Code already exists") from None
            raise
