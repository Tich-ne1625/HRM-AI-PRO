from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.domain_writes import CsrfCheck, authorize_domain_write, require_version
from app.core.errors import ApiError
from app.core.policies import AuthContext
from app.modules.audit.service import AuditWriter
from app.modules.employees.models import Employee, EmploymentStatus
from app.modules.organization.schemas import Page
from app.modules.review_cycles.models import CycleParticipant, CycleStatus, ReviewCycle
from app.modules.review_cycles.repository import CycleRepository, cycle_scope
from app.modules.review_cycles.schemas import (
    CycleCreate,
    CycleUpdate,
    CycleView,
    Enrollment,
    EnrollmentResult,
    ParticipantView,
)
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.schemas import ScoringPolicy
from app.modules.users.models import User, UserRole


class CycleService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = CycleRepository(session)

    def view(self, cycle: ReviewCycle, user: User) -> CycleView:
        count = (
            self.session.scalar(
                select(func.count()).select_from(
                    self.repository.participants(cycle.id, user).subquery(),
                )
            )
            or 0
        )
        draft = cycle.status == CycleStatus.DRAFT
        if draft:
            defaults = SettingsRepository(self.session).get()
            policy, source_version = defaults.scoring_policy, defaults.version
        else:
            assert cycle.scoring_policy_snapshot is not None and cycle.policy_source_version
            policy, source_version = cycle.scoring_policy_snapshot, cycle.policy_source_version
        editable = user.role == UserRole.HR and draft
        return CycleView(
            id=cycle.id,
            name=cycle.name,
            start_date=cycle.start_date,
            end_date=cycle.end_date,
            status=cycle.status,
            version=cycle.version,
            policy=ScoringPolicy.model_validate(policy),
            policy_source_version=source_version,
            policy_is_preview=draft,
            participant_count=count,
            can_edit=editable,
            can_activate=editable and count > 0,
            activated_at=cycle.activated_at,
        )

    def list(
        self,
        user: User,
        *,
        page: int,
        page_size: int,
        sort: str,
        status: CycleStatus | None,
        q: str | None,
    ) -> Page[CycleView]:
        with self.session.begin():
            filters = [cycle_scope(user)]
            if status is not None:
                filters.append(ReviewCycle.status == status)
            if q:
                filters.append(ReviewCycle.name.icontains(q, autoescape=True))
            total = self.session.scalar(
                select(func.count()).select_from(ReviewCycle).where(*filters)
            )
            rows = self.session.scalars(
                select(ReviewCycle)
                .where(*filters)
                .order_by(getattr(ReviewCycle, sort), ReviewCycle.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            return Page(
                items=[self.view(row, user) for row in rows],
                total=total or 0,
                page=page,
                page_size=page_size,
            )

    def detail(self, identifier: UUID, user: User) -> CycleView:
        with self.session.begin():
            return self.view(self.repository.get(identifier, user), user)

    def participants(
        self,
        identifier: UUID,
        user: User,
        *,
        page: int,
        page_size: int,
        q: str | None,
        department_id: UUID | None,
    ) -> Page[ParticipantView]:
        with self.session.begin():
            cycle = self.repository.get(identifier, user)
            query = self.repository.participants(identifier, user)
            frozen = cycle.status != CycleStatus.DRAFT
            code = (
                CycleParticipant.snapshot["employee_code"].astext
                if frozen
                else Employee.employee_code
            )
            name = (
                CycleParticipant.snapshot["display_name"].astext
                if frozen
                else Employee.display_name
            )
            if q:
                query = query.where(
                    or_(code.icontains(q, autoescape=True), name.icontains(q, autoescape=True))
                )
            if department_id:
                query = query.where(
                    CycleParticipant.snapshot["department_id"].astext == str(department_id)
                    if frozen
                    else Employee.department_id == department_id
                )
            total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
            actor = self.repository.actor_employee(user)
            rows = self.session.execute(
                query.order_by(code, CycleParticipant.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            return Page(
                items=[
                    self.repository.present_participant(p, e, cycle, user, actor) for p, e in rows
                ],
                total=total,
                page=page,
                page_size=page_size,
            )

    def write(
        self,
        body: CycleCreate | CycleUpdate,
        context: AuthContext,
        *,
        csrf: CsrfCheck,
        request_id: str,
        identifier: UUID | None = None,
    ) -> CycleView:
        with self.session.begin():
            user = authorize_domain_write(self.session, context, csrf, (UserRole.HR,))
            if isinstance(body, CycleCreate):
                cycle = ReviewCycle(**body.model_dump())
                self.session.add(cycle)
                changed = set(body.model_fields_set)
                previous = 0
            else:
                assert identifier is not None
                cycle = self.repository.get(identifier, user, lock=True)
                self.require_draft(cycle)
                require_version(cycle.version, body.expected_version)
                values = body.model_dump(exclude_unset=True, exclude={"expected_version"})
                changed = {key for key, value in values.items() if getattr(cycle, key) != value}
                previous = cycle.version
                for key, value in values.items():
                    setattr(cycle, key, value)
                if cycle.start_date > cycle.end_date:
                    raise ApiError(422, "validation_error", "start_date must not be after end_date")
                if changed:
                    cycle.version += 1
            self.session.flush()
            if changed:
                AuditWriter().record(
                    self.session,
                    user.id,
                    "review_cycle.created" if identifier is None else "review_cycle.updated",
                    "review_cycle",
                    str(cycle.id),
                    request_id,
                    {
                        "changed_fields": ",".join(sorted(changed)),
                        "previous_version": previous,
                        "version": cycle.version,
                    },
                )
            return self.view(cycle, user)

    @staticmethod
    def require_draft(cycle: ReviewCycle) -> None:
        if cycle.status != CycleStatus.DRAFT:
            raise ApiError(409, "cycle_not_draft", "Only DRAFT cycles can be edited")

    def enroll(
        self,
        identifier: UUID,
        body: Enrollment,
        context: AuthContext,
        *,
        csrf: CsrfCheck,
        request_id: str,
    ) -> EnrollmentResult:
        with self.session.begin():
            user = authorize_domain_write(self.session, context, csrf, (UserRole.HR,))
            cycle = self.repository.get(identifier, user, lock=True)
            self.require_draft(cycle)
            require_version(cycle.version, body.expected_version)
            employees = list(
                self.session.scalars(
                    select(Employee).where(Employee.id.in_(body.employee_ids)).order_by(Employee.id)
                )
            )
            if len(employees) != len(body.employee_ids):
                raise ApiError(404, "employee_not_found", "Employee not found")
            if any(e.employment_status != EmploymentStatus.ACTIVE for e in employees):
                raise ApiError(409, "reference_inactive", "Employee is inactive")
            exists = self.session.scalar(
                select(CycleParticipant.id)
                .where(
                    CycleParticipant.cycle_id == identifier,
                    CycleParticipant.employee_id.in_(body.employee_ids),
                )
                .limit(1)
            )
            if exists:
                raise ApiError(409, "participant_already_enrolled", "Employee already enrolled")
            for employee in employees:
                row = CycleParticipant(cycle_id=identifier, employee_id=employee.id)
                self.session.add(row)
                self.session.flush()
                AuditWriter().record(
                    self.session,
                    user.id,
                    "cycle_participant.enrolled",
                    "cycle_participant",
                    str(row.id),
                    request_id,
                    {"cycle_id": str(identifier), "employee_id": str(employee.id)},
                )
            cycle.version += 1
            self.session.flush()
            return EnrollmentResult(version=cycle.version, count=len(employees))

    def remove(
        self,
        identifier: UUID,
        participant_id: UUID,
        expected_version: int,
        context: AuthContext,
        *,
        csrf: CsrfCheck,
        request_id: str,
    ) -> EnrollmentResult:
        with self.session.begin():
            user = authorize_domain_write(self.session, context, csrf, (UserRole.HR,))
            cycle = self.repository.get(identifier, user, lock=True)
            self.require_draft(cycle)
            require_version(cycle.version, expected_version)
            row = self.session.scalar(
                select(CycleParticipant)
                .where(
                    CycleParticipant.id == participant_id,
                    CycleParticipant.cycle_id == identifier,
                )
                .with_for_update()
            )
            if row is None:
                raise ApiError(404, "participant_not_found", "Participant not found")
            from app.modules.kpis.models import EmployeeKPI

            if (
                row.snapshot is not None
                or row.finalized_at is not None
                or self.session.scalar(
                    select(EmployeeKPI.id).where(EmployeeKPI.participant_id == row.id).limit(1),
                )
            ):
                raise ApiError(409, "cycle_not_draft", "Participant already has evidence")
            self.session.delete(row)
            cycle.version += 1
            AuditWriter().record(
                self.session,
                user.id,
                "cycle_participant.removed",
                "cycle_participant",
                str(row.id),
                request_id,
                {"cycle_id": str(identifier), "employee_id": str(row.employee_id)},
            )
            self.session.flush()
            return EnrollmentResult(version=cycle.version, count=1)
