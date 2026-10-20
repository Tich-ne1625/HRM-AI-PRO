from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.domain_writes import CsrfCheck, authorize_domain_write, require_version
from app.core.errors import ApiError
from app.core.policies import AuthContext
from app.modules.audit.service import AuditWriter
from app.modules.employees.models import Employee
from app.modules.kpis.allocation_schemas import AllocationLine, AllocationView, DefinitionSnapshot
from app.modules.kpis.models import EmployeeKPI, KPIDefinition, KPIDirection
from app.modules.kpis.schemas import ActualUpdate, AllocationReplace, DefinitionView
from app.modules.kpis.service import DefinitionService
from app.modules.organization.schemas import Page
from app.modules.review_cycles.models import CycleParticipant, CycleStatus, ReviewCycle
from app.modules.review_cycles.repository import CycleRepository, can_write_kpis
from app.modules.settings.schemas import ScoringPolicy
from app.modules.users.models import User, UserRole


class AllocationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = CycleRepository(session)

    def view(
        self, participant: CycleParticipant, employee: Employee, cycle: ReviewCycle, user: User
    ) -> AllocationView:
        rows = self.session.scalars(
            select(EmployeeKPI)
            .where(
                EmployeeKPI.participant_id == participant.id,
            )
            .order_by(EmployeeKPI.definition_snapshot["code"].astext, EmployeeKPI.id)
        )
        return AllocationView(
            participant=self.repository.present_participant(
                participant, employee, cycle, user, self.repository.actor_employee(user)
            ),
            cycle_status=cycle.status,
            items=[
                AllocationLine(
                    id=row.id,
                    definition_id=row.definition_id,
                    definition=DefinitionSnapshot.model_validate(row.definition_snapshot),
                    target=row.target,
                    actual=row.actual,
                    weight=row.weight,
                )
                for row in rows
            ],
        )

    def read(self, employee_id: UUID, cycle_id: UUID, user: User) -> AllocationView:
        with self.session.begin():
            self.repository.get(cycle_id, user)
            return self.view(
                *self.repository.participant_for_employee(employee_id, cycle_id, user), user
            )

    def require_writable(
        self, participant: CycleParticipant, employee: Employee, cycle: ReviewCycle, user: User
    ) -> None:
        if cycle.status != CycleStatus.ACTIVE:
            raise ApiError(409, "cycle_not_active", "KPI evidence requires an ACTIVE cycle")
        if participant.finalized_at is not None:
            raise ApiError(409, "participant_finalized", "Finalized evidence cannot be changed")
        if not can_write_kpis(
            user, employee, self.repository.actor_employee(user), cycle, participant
        ):
            raise ApiError(403, "forbidden", "Access is forbidden")

    def options(
        self,
        employee_id: UUID,
        cycle_id: UUID,
        user: User,
        *,
        page: int,
        page_size: int,
        sort: str,
        q: str | None,
        direction: KPIDirection | None,
    ) -> Page[DefinitionView]:
        with self.session.begin():
            self.repository.get(cycle_id, user)
            self.require_writable(
                *self.repository.participant_for_employee(employee_id, cycle_id, user), user
            )
            return DefinitionService(self.session).list(
                user,
                page=page,
                page_size=page_size,
                sort=sort,
                q=q,
                is_active=True,
                direction=direction,
                options=True,
            )

    def replace(
        self,
        employee_id: UUID,
        cycle_id: UUID,
        body: AllocationReplace,
        context: AuthContext,
        *,
        csrf: CsrfCheck,
        request_id: str,
    ) -> AllocationView:
        with self.session.begin():
            user = authorize_domain_write(
                self.session, context, csrf, (UserRole.HR, UserRole.MANAGER)
            )
            self.repository.get(cycle_id, user, lock=True)
            participant, employee, cycle = self.repository.participant_for_employee(
                employee_id,
                cycle_id,
                user,
                lock=True,
            )
            self.require_writable(participant, employee, cycle, user)
            require_version(
                participant.evidence_version, body.expected_evidence_version, evidence=True
            )
            identifiers = {item.definition_id for item in body.items}
            definitions = {
                d.id: d
                for d in self.session.scalars(
                    select(KPIDefinition)
                    .where(KPIDefinition.id.in_(identifiers))
                    .order_by(KPIDefinition.id)
                    .with_for_update()
                )
            }
            if len(definitions) != len(identifiers):
                raise ApiError(404, "kpi_not_found", "KPI definition not found")
            existing = {
                r.definition_id: r
                for r in self.session.scalars(
                    select(EmployeeKPI)
                    .where(EmployeeKPI.participant_id == participant.id)
                    .order_by(EmployeeKPI.id)
                    .with_for_update()
                )
            }
            policy = ScoringPolicy.model_validate(cycle.scoring_policy_snapshot)
            for item in body.items:
                definition = definitions[item.definition_id]
                if item.definition_id not in existing:
                    if not definition.is_active:
                        raise ApiError(409, "kpi_definition_inactive", "KPI definition is inactive")
                    if (
                        definition.direction == KPIDirection.LOWER_IS_BETTER
                        and policy.kpi_cap is None
                    ):
                        raise ApiError(
                            409, "kpi_policy_incompatible", "Lower-is-better requires a finite cap"
                        )
            changed = set(existing) != identifiers or any(
                item.definition_id not in existing
                or existing[item.definition_id].target != item.target
                or existing[item.definition_id].weight != item.weight
                for item in body.items
            )
            if changed:
                for identifier, row in existing.items():
                    if identifier not in identifiers:
                        self.session.delete(row)
                for item in body.items:
                    if item.definition_id in existing:
                        row = existing[item.definition_id]
                        if row.target != item.target:
                            row.actual = None
                        row.target, row.weight = item.target, item.weight
                    else:
                        definition = definitions[item.definition_id]
                        snapshot = DefinitionSnapshot(
                            version=definition.version,
                            code=definition.code,
                            name=definition.name,
                            description=definition.description,
                            unit=definition.unit,
                            direction=definition.direction,
                        )
                        self.session.add(
                            EmployeeKPI(
                                participant_id=participant.id,
                                definition_id=definition.id,
                                definition_snapshot=snapshot.model_dump(mode="json"),
                                target=item.target,
                                weight=item.weight,
                            )
                        )
                previous = participant.evidence_version
                participant.evidence_version += 1
                self.session.flush()
                AuditWriter().record(
                    self.session,
                    user.id,
                    "kpi_allocation.replaced",
                    "cycle_participant",
                    str(participant.id),
                    request_id,
                    {
                        "cycle_id": str(cycle.id),
                        "employee_id": str(employee.id),
                        "previous_evidence_version": previous,
                        "evidence_version": participant.evidence_version,
                        "count": len(body.items),
                    },
                )
            return self.view(participant, employee, cycle, user)

    def actual(
        self,
        identifier: UUID,
        body: ActualUpdate,
        context: AuthContext,
        *,
        csrf: CsrfCheck,
        request_id: str,
    ) -> AllocationView:
        with self.session.begin():
            user = authorize_domain_write(
                self.session, context, csrf, (UserRole.HR, UserRole.MANAGER)
            )
            # First resolve only scoped IDs; lock cycle then participant, as for PUT.
            from app.modules.review_cycles.repository import participant_scope

            ids = self.session.execute(
                select(CycleParticipant.employee_id, CycleParticipant.cycle_id)
                .join(EmployeeKPI, EmployeeKPI.participant_id == CycleParticipant.id)
                .join(Employee, CycleParticipant.employee_id == Employee.id)
                .join(ReviewCycle, CycleParticipant.cycle_id == ReviewCycle.id)
                .where(EmployeeKPI.id == identifier, participant_scope(user))
            ).one_or_none()
            if ids is None:
                raise ApiError(404, "employee_kpi_not_found", "Assigned KPI not found")
            self.repository.get(ids[1], user, lock=True)
            participant, employee, cycle = self.repository.participant_for_employee(
                ids[0],
                ids[1],
                user,
                lock=True,
            )
            self.require_writable(participant, employee, cycle, user)
            require_version(
                participant.evidence_version, body.expected_evidence_version, evidence=True
            )
            row = self.session.get(
                EmployeeKPI, identifier, with_for_update=True, populate_existing=True
            )
            if row is None:
                raise ApiError(404, "employee_kpi_not_found", "Assigned KPI not found")
            if row.actual != body.actual:
                row.actual = body.actual
                previous = participant.evidence_version
                participant.evidence_version += 1
                self.session.flush()
                AuditWriter().record(
                    self.session,
                    user.id,
                    "employee_kpi.actual_updated",
                    "employee_kpi",
                    str(row.id),
                    request_id,
                    {
                        "participant_id": str(participant.id),
                        "definition_id": str(row.definition_id),
                        "previous_evidence_version": previous,
                        "evidence_version": participant.evidence_version,
                    },
                )
            return self.view(participant, employee, cycle, user)
