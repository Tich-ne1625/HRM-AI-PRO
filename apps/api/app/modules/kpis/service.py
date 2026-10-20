from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.domain_writes import CsrfCheck, authorize_domain_write, require_version
from app.core.errors import ApiError
from app.core.policies import AuthContext
from app.modules.audit.service import AuditWriter
from app.modules.kpis.models import KPIDefinition, KPIDirection
from app.modules.kpis.repository import definition_scope
from app.modules.kpis.schemas import DefinitionCreate, DefinitionUpdate, DefinitionView
from app.modules.organization.schemas import Page
from app.modules.users.models import User, UserRole


class DefinitionService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(
        self,
        user: User,
        *,
        page: int,
        page_size: int,
        sort: str,
        q: str | None,
        is_active: bool | None,
        direction: KPIDirection | None,
        options: bool = False,
    ) -> Page[DefinitionView]:
        filters = [] if options else [definition_scope(user)]
        if q:
            filters.append(
                or_(
                    KPIDefinition.code.icontains(q, autoescape=True),
                    KPIDefinition.name.icontains(q, autoescape=True),
                )
            )
        if is_active is not None:
            filters.append(KPIDefinition.is_active == is_active)
        if direction is not None:
            filters.append(KPIDefinition.direction == direction)
        # Caller owns the transaction when listing authorized allocation options.
        total = self.session.scalar(select(func.count()).select_from(KPIDefinition).where(*filters))
        rows = self.session.scalars(
            select(KPIDefinition)
            .where(*filters)
            .order_by(getattr(KPIDefinition, sort), KPIDefinition.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return Page(
            items=[DefinitionView.model_validate(row) for row in rows],
            total=total or 0,
            page=page,
            page_size=page_size,
        )

    def write(
        self,
        body: DefinitionCreate | DefinitionUpdate,
        context: AuthContext,
        *,
        csrf: CsrfCheck,
        request_id: str,
        identifier: UUID | None = None,
    ) -> DefinitionView:
        try:
            with self.session.begin():
                authorize_domain_write(self.session, context, csrf, (UserRole.HR,))
                if isinstance(body, DefinitionCreate):
                    row = KPIDefinition(**body.model_dump())
                    self.session.add(row)
                    changed = set(body.model_fields_set)
                    previous = 0
                else:
                    existing = self.session.get(
                        KPIDefinition, identifier, with_for_update=True, populate_existing=True
                    )
                    if existing is None:
                        raise ApiError(404, "kpi_not_found", "KPI definition not found")
                    row = existing
                    require_version(row.version, body.expected_version)
                    values = body.model_dump(exclude_unset=True, exclude={"expected_version"})
                    changed = {key for key, value in values.items() if getattr(row, key) != value}
                    previous = row.version
                    if changed:
                        for key, value in values.items():
                            setattr(row, key, value)
                        row.version += 1
                self.session.flush()
                if changed:
                    action = (
                        "kpi_definition.created" if identifier is None else "kpi_definition.updated"
                    )
                    AuditWriter().record(
                        self.session,
                        context.user.id,
                        action,
                        "kpi_definition",
                        str(row.id),
                        request_id,
                        {
                            "changed_fields": ",".join(sorted(changed)),
                            "code": row.code,
                            "is_active": row.is_active,
                            "previous_version": previous,
                            "version": row.version,
                        },
                    )
                return DefinitionView.model_validate(row)
        except IntegrityError as error:
            if getattr(error.orig, "sqlstate", None) == "23505":
                raise ApiError(409, "duplicate_code", "KPI code already exists") from None
            raise
