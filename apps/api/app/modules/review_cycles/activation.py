from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.domain_writes import CsrfCheck, authorize_domain_write, require_version
from app.core.errors import ApiError
from app.core.policies import AuthContext
from app.modules.audit.service import AuditWriter
from app.modules.employees.models import Employee, EmploymentStatus
from app.modules.organization.models import Department, Position
from app.modules.organization.repository import OrganizationRepository
from app.modules.review_cycles.models import CycleParticipant, CycleStatus, ReviewCycle
from app.modules.review_cycles.repository import CycleRepository
from app.modules.review_cycles.schemas import CycleView, ParticipantSnapshot, RelationshipSnapshot
from app.modules.review_cycles.service import CycleService
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.schemas import ScoringPolicy
from app.modules.users.models import User, UserRole


class CycleActivation:
    def __init__(self, session: Session) -> None:
        self.session = session

    def activate(
        self,
        identifier: UUID,
        expected_version: int,
        context: AuthContext,
        *,
        csrf: CsrfCheck,
        request_id: str,
    ) -> CycleView:
        with self.session.begin():
            OrganizationRepository(self.session).lock_guard()
            # Discover references under the graph guard; acquire user locks only
            # after the ordered active-admin locks in authorize_domain_write.
            employees = {e.id: e for e in self.session.scalars(select(Employee))}
            ids = list(
                self.session.scalars(
                    select(CycleParticipant.employee_id).where(
                        CycleParticipant.cycle_id == identifier,
                    )
                )
            )
            related: set[UUID] = set()
            for employee_id in ids:
                employee = employees[employee_id]
                manager = employees.get(employee.manager_id) if employee.manager_id else None
                related.update(e.user_id for e in (employee, manager) if e and e.user_id)
            actor = authorize_domain_write(self.session, context, csrf, (UserRole.HR,), related)
            defaults = SettingsRepository(self.session).get(lock=True)
            repository = CycleRepository(self.session)
            cycle = repository.get(identifier, actor, lock=True)
            CycleService.require_draft(cycle)
            require_version(cycle.version, expected_version)
            if self.session.scalar(
                select(ReviewCycle.id)
                .where(
                    ReviewCycle.status == CycleStatus.ACTIVE,
                )
                .limit(1)
            ):
                raise ApiError(409, "active_cycle_exists", "Another review cycle is already active")
            participants = list(
                self.session.scalars(
                    select(CycleParticipant)
                    .where(
                        CycleParticipant.cycle_id == identifier,
                    )
                    .order_by(CycleParticipant.id)
                    .with_for_update()
                )
            )
            users = {
                u.id: u
                for u in self.session.scalars(
                    select(User)
                    .where(User.id.in_(related))
                    .execution_options(populate_existing=True)
                )
            }
            departments = {d.id: d for d in self.session.scalars(select(Department))}
            positions = {p.id: p for p in self.session.scalars(select(Position))}
            issues: list[dict[str, object]] = []
            if not participants:
                issues.append({"code": "participants_required"})
            for participant in participants:
                employee = employees[participant.employee_id]
                manager = employees.get(employee.manager_id) if employee.manager_id else None
                account = users.get(employee.user_id) if employee.user_id else None
                manager_account = (
                    users.get(manager.user_id) if manager and manager.user_id else None
                )
                problems = []
                if employee.employment_status != EmploymentStatus.ACTIVE:
                    problems.append("employee_inactive")
                if not departments[employee.department_id].is_active:
                    problems.append("department_inactive")
                if not positions[employee.position_id].is_active:
                    problems.append("position_inactive")
                if not account or not account.is_active:
                    problems.append("self_account_required")
                if (
                    not manager
                    or manager.id == employee.id
                    or manager.employment_status != EmploymentStatus.ACTIVE
                ):
                    problems.append("active_manager_required")
                if (
                    not manager_account
                    or not manager_account.is_active
                    or (account and manager_account.id == account.id)
                ):
                    problems.append("manager_account_required")
                issues.extend({"employee_id": str(employee.id), "code": code} for code in problems)
            if issues:
                raise ApiError(
                    409,
                    "activation_requirements_not_met",
                    "Resolve activation requirements",
                    [*issues[:100], {"issue_count": len(issues)}],
                )
            # No partial activation: prepare every snapshot only after all checks.
            policy = ScoringPolicy.model_validate(defaults.scoring_policy)
            reports: dict[UUID, list[RelationshipSnapshot]] = {}
            for employee in sorted(employees.values(), key=lambda e: e.id):
                if employee.manager_id:
                    reports.setdefault(employee.manager_id, []).append(
                        RelationshipSnapshot(
                            employee_id=employee.id,
                            user_id=employee.user_id,
                            employment_status=employee.employment_status,
                        )
                    )
            for participant in participants:
                employee = employees[participant.employee_id]
                assert employee.manager_id is not None and employee.user_id is not None
                manager = employees[employee.manager_id]
                assert manager.user_id is not None
                department, position = (
                    departments[employee.department_id],
                    positions[employee.position_id],
                )
                snapshot = ParticipantSnapshot(
                    employee_id=employee.id,
                    user_id=employee.user_id,
                    employee_code=employee.employee_code,
                    display_name=employee.display_name,
                    department_id=department.id,
                    department_code=department.code,
                    department_name=department.name,
                    position_id=position.id,
                    position_code=position.code,
                    position_title=position.title,
                    manager_id=manager.id,
                    manager_user_id=manager.user_id,
                    manager_display_name=manager.display_name,
                    direct_reports=reports.get(employee.id, []),
                )
                participant.snapshot = snapshot.model_dump(mode="json")
                participant.evidence_version += 1
            cycle.scoring_policy_snapshot = policy.model_dump(mode="json")
            cycle.policy_source_version = defaults.version
            cycle.activated_at = datetime.now(UTC)
            cycle.status = CycleStatus.ACTIVE
            previous = cycle.version
            cycle.version += 1
            self.session.flush()
            AuditWriter().record(
                self.session,
                actor.id,
                "review_cycle.activated",
                "review_cycle",
                str(cycle.id),
                request_id,
                {
                    "previous_version": previous,
                    "version": cycle.version,
                    "count": len(participants),
                    "status": cycle.status.value,
                    "policy_source_version": defaults.version,
                },
            )
            return CycleService(self.session).view(cycle, actor)
