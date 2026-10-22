from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.domain_writes import CsrfCheck, authorize_domain_write, require_version
from app.core.errors import ApiError
from app.core.policies import AuthContext
from app.modules.audit.service import AuditWriter
from app.modules.employees.models import Employee
from app.modules.employees.repository import employee_scope
from app.modules.organization.schemas import Page
from app.modules.performance.engine import ENGINE_VERSION, compute
from app.modules.performance.evidence import Evidence, collect
from app.modules.performance.models import PerformanceReview, PerformanceReviewRevision
from app.modules.performance.presenter import calculation
from app.modules.performance.schemas import (
    CalculateInput,
    CalculationView,
    CloseResult,
    FinalizationContext,
    FinalizeInput,
    HRReadiness,
    PerformanceReport,
    Readiness,
    RevisionSummary,
)
from app.modules.review_cycles.models import CycleParticipant, CycleStatus, ReviewCycle
from app.modules.review_cycles.repository import CycleRepository, can_write_kpis
from app.modules.users.models import User, UserRole


class PerformanceService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.cycles = CycleRepository(session)

    def repeatable_read(self) -> None:
        # Must be the first SQL statement: every aggregate belongs to one MVCC snapshot.
        self.session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))

    def review(self, participant_id: UUID, *, lock: bool = False) -> PerformanceReview | None:
        query = select(PerformanceReview).where(PerformanceReview.participant_id == participant_id)
        if lock:
            query = query.with_for_update()
        return self.session.scalar(query.execution_options(populate_existing=True))

    def scoped_review(
        self, identifier: UUID, user: User
    ) -> tuple[PerformanceReview, CycleParticipant, Employee, ReviewCycle]:
        row = self.session.execute(
            select(PerformanceReview, CycleParticipant, Employee, ReviewCycle)
            .join(CycleParticipant, PerformanceReview.participant_id == CycleParticipant.id)
            .join(Employee, CycleParticipant.employee_id == Employee.id)
            .join(ReviewCycle, CycleParticipant.cycle_id == ReviewCycle.id)
            .where(
                PerformanceReview.id == identifier,
                employee_scope(user),
                ReviewCycle.status != CycleStatus.DRAFT,
            )
        ).one_or_none()
        if row is None:
            raise ApiError(404, "review_not_found", "Performance review not found")
        return row[0], row[1], row[2], row[3]

    def present(
        self,
        participant: CycleParticipant,
        employee: Employee,
        cycle: ReviewCycle,
        user: User,
        evidence: Evidence | None = None,
        *,
        reused: bool = False,
    ) -> PerformanceReport:
        evidence = evidence or collect(self.session, participant, employee, cycle)
        row = self.review(participant.id)
        finalized = bool(row and row.finalized_at and participant.finalized_at == row.finalized_at)
        current = bool(
            row
            and (
                finalized
                or (
                    row.evidence_version == participant.evidence_version
                    and row.engine_version == ENGINE_VERSION
                )
            )
        )
        result = calculation(self.session, row, user) if row else None
        allowed = can_write_kpis(
            user, employee, self.cycles.actor_employee(user), cycle, participant
        )
        subject = evidence.snapshot["subject"]
        return PerformanceReport(
            review_id=row.id if row else None,
            participant_id=participant.id,
            employee_id=employee.id,
            employee_code=subject["employee_code"],
            display_name=subject["display_name"],
            cycle_id=cycle.id,
            cycle_name=cycle.name,
            cycle_status=cycle.status,
            cycle_version=cycle.version,
            evidence_version=participant.evidence_version,
            state="FINALIZED"
            if finalized
            else "CURRENT"
            if current
            else "STALE"
            if row
            else "NOT_CALCULATED",
            current_result=result if current else None,
            last_calculation=result,
            readiness=Readiness.model_validate(evidence.readiness.model_dump()),
            can_calculate=allowed and evidence.readiness.ready,
            can_finalize=user.role == UserRole.HR
            and cycle.status == CycleStatus.ACTIVE
            and not participant.finalized_at
            and current
            and evidence.readiness.ready,
            finalized_at=row.finalized_at if row else None,
            reused=reused,
        )

    def report(self, employee_id: UUID, cycle_id: UUID, user: User) -> PerformanceReport:
        with self.session.begin():
            self.repeatable_read()
            return self.present(
                *self.cycles.participant_for_employee(employee_id, cycle_id, user), user
            )

    def readiness(self, employee_id: UUID, cycle_id: UUID, user: User) -> Readiness | HRReadiness:
        with self.session.begin():
            self.repeatable_read()
            result = collect(
                self.session, *self.cycles.participant_for_employee(employee_id, cycle_id, user)
            ).readiness
            return (
                result
                if user.role == UserRole.HR
                else Readiness.model_validate(result.model_dump())
            )

    def lock_scope(
        self, employee_id: UUID, cycle_id: UUID, user: User
    ) -> tuple[CycleParticipant, Employee, ReviewCycle]:
        self.cycles.get(cycle_id, user, lock=True)
        return self.cycles.participant_for_employee(employee_id, cycle_id, user, lock=True)

    @staticmethod
    def writable(participant: CycleParticipant, cycle: ReviewCycle) -> None:
        if cycle.status != CycleStatus.ACTIVE:
            raise ApiError(409, "cycle_not_active", "An ACTIVE cycle is required")
        if participant.finalized_at:
            raise ApiError(409, "participant_finalized", "The review has been finalized")

    @staticmethod
    def require_ready(evidence: Evidence) -> None:
        if not evidence.readiness.ready:
            raise ApiError(
                409, "evidence_incomplete", "Complete KPI actuals and required feedback first"
            )

    def audit(
        self,
        actor: User,
        action: str,
        row: PerformanceReview,
        participant: CycleParticipant,
        request_id: str,
    ) -> None:
        AuditWriter().record(
            self.session,
            actor.id,
            action,
            "performance_review",
            str(row.id),
            request_id,
            {
                "participant_id": str(participant.id),
                "cycle_id": str(participant.cycle_id),
                "calculation_version": row.calculation_version,
                "evidence_version": row.evidence_version,
                "engine_version": row.engine_version,
                "evidence_hash": row.evidence_hash,
            },
        )

    def calculate(
        self,
        employee_id: UUID,
        body: CalculateInput,
        context: AuthContext,
        *,
        csrf: CsrfCheck,
        request_id: str,
    ) -> tuple[PerformanceReport, bool]:
        with self.session.begin():
            actor = authorize_domain_write(
                self.session, context, csrf, (UserRole.HR, UserRole.MANAGER)
            )
            participant, employee, cycle = self.lock_scope(employee_id, body.cycle_id, actor)
            self.writable(participant, cycle)
            if not can_write_kpis(
                actor, employee, self.cycles.actor_employee(actor), cycle, participant
            ):
                raise ApiError(
                    403, "forbidden", "Only HR or the current direct manager may calculate"
                )
            require_version(
                participant.evidence_version, body.expected_evidence_version, evidence=True
            )
            evidence = collect(self.session, participant, employee, cycle)
            self.require_ready(evidence)
            row = self.review(participant.id, lock=True)
            if (
                row
                and row.evidence_hash == evidence.digest
                and row.engine_version == ENGINE_VERSION
            ):
                return self.present(
                    participant, employee, cycle, actor, evidence, reused=True
                ), False
            try:
                result = compute(evidence.snapshot["items"], evidence.ratings, evidence.policy)
            except ValueError as error:
                raise ApiError(409, "evidence_inconsistent", "Evidence cannot be scored") from error
            created = row is None
            if row is None:
                row = PerformanceReview(participant_id=participant.id)
                self.session.add(row)
            values = {
                "calculation_version": 1 if created else row.calculation_version + 1,
                "evidence_version": participant.evidence_version,
                "engine_version": ENGINE_VERSION,
                "evidence_hash": evidence.digest,
                "calculated_at": datetime.now(UTC),
                "policy_snapshot": evidence.policy,
                "evidence_snapshot": {**evidence.snapshot, "results": result["items"]},
                **{
                    key: Decimal(result[key])
                    for key in ("kpi_score", "feedback_score", "final_score")
                },
            }
            for key, value in values.items():
                setattr(row, key, value)
            self.session.flush()
            self.session.add(PerformanceReviewRevision(review_id=row.id, **values))
            self.audit(actor, "performance.calculated", row, participant, request_id)
            self.session.flush()
            return self.present(participant, employee, cycle, actor, evidence), created

    def revisions(
        self, identifier: UUID, user: User, *, page: int, page_size: int
    ) -> Page[RevisionSummary]:
        with self.session.begin():
            self.repeatable_read()
            self.scoped_review(identifier, user)
            query = select(PerformanceReviewRevision).where(
                PerformanceReviewRevision.review_id == identifier
            )
            total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
            rows = self.session.scalars(
                query.order_by(PerformanceReviewRevision.calculation_version.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            return Page(
                items=[
                    RevisionSummary(
                        calculation_version=r.calculation_version,
                        evidence_version=r.evidence_version,
                        calculated_at=r.calculated_at,
                        kpi_score=format(r.kpi_score, ".2f"),
                        feedback_score=format(r.feedback_score, ".2f"),
                        final_score=format(r.final_score, ".2f"),
                    )
                    for r in rows
                ],
                total=total,
                page=page,
                page_size=page_size,
            )

    def revision(self, identifier: UUID, version: int, user: User) -> CalculationView:
        with self.session.begin():
            self.repeatable_read()
            self.scoped_review(identifier, user)
            row = self.session.scalar(
                select(PerformanceReviewRevision).where(
                    PerformanceReviewRevision.review_id == identifier,
                    PerformanceReviewRevision.calculation_version == version,
                )
            )
            if row is None:
                raise ApiError(404, "revision_not_found", "Calculation revision not found")
            return calculation(self.session, row, user)

    @staticmethod
    def open_optional(evidence: Evidence) -> int:
        return sum(
            a["status"] == "OPEN" and not a["required"] for a in evidence.snapshot["assignments"]
        )

    def finalization_context(self, identifier: UUID, user: User) -> FinalizationContext:
        with self.session.begin():
            self.repeatable_read()
            row, participant, employee, cycle = self.scoped_review(identifier, user)
            evidence = collect(self.session, participant, employee, cycle)
            return FinalizationContext(
                review_id=row.id,
                evidence_version=participant.evidence_version,
                calculation_version=row.calculation_version,
                readiness=evidence.readiness,
                open_optional_count=self.open_optional(evidence),
            )

    def finalize(
        self,
        identifier: UUID,
        body: FinalizeInput,
        context: AuthContext,
        *,
        csrf: CsrfCheck,
        request_id: str,
    ) -> PerformanceReport:
        with self.session.begin():
            actor = authorize_domain_write(self.session, context, csrf, (UserRole.HR,))
            _, _, employee, cycle = self.scoped_review(identifier, actor)
            participant, employee, cycle = self.lock_scope(employee.id, cycle.id, actor)
            row = self.review(participant.id, lock=True)
            assert row is not None
            if row.finalized_at:
                raise ApiError(
                    409, "review_already_finalized", "The review has already been finalized"
                )
            self.writable(participant, cycle)
            require_version(
                participant.evidence_version, body.expected_evidence_version, evidence=True
            )
            if row.calculation_version != body.expected_calculation_version:
                raise ApiError(
                    409, "stale_calculation_version", "Calculation has changed; reload explicitly"
                )
            evidence = collect(self.session, participant, employee, cycle)
            self.require_ready(evidence)
            if (
                row.evidence_version != participant.evidence_version
                or row.engine_version != ENGINE_VERSION
                or row.evidence_hash != evidence.digest
            ):
                raise ApiError(409, "review_stale", "Recalculate before finalizing")
            if self.open_optional(evidence) != body.acknowledge_open_optional_count:
                raise ApiError(
                    409,
                    "optional_feedback_acknowledgement_required",
                    "Confirm the current number of open optional assignments",
                )
            row.finalized_at = participant.finalized_at = datetime.now(UTC)
            cycle.version += 1
            self.audit(actor, "performance.finalized", row, participant, request_id)
            return self.present(participant, employee, cycle, actor, evidence)

    def close(
        self,
        identifier: UUID,
        expected_version: int,
        context: AuthContext,
        *,
        csrf: CsrfCheck,
        request_id: str,
    ) -> CloseResult:
        with self.session.begin():
            actor = authorize_domain_write(self.session, context, csrf, (UserRole.HR,))
            cycle = self.cycles.get(identifier, actor, lock=True)
            if cycle.status == CycleStatus.CLOSED:
                raise ApiError(409, "cycle_already_closed", "The cycle has already been closed")
            if cycle.status != CycleStatus.ACTIVE:
                raise ApiError(409, "cycle_not_active", "Only ACTIVE cycles can be closed")
            require_version(cycle.version, expected_version)
            rows = list(
                self.session.execute(
                    self.cycles.participants(identifier, actor)
                    .order_by(CycleParticipant.id)
                    .with_for_update(of=CycleParticipant)
                )
            )
            issues: list[dict[str, object]] = []
            count = 0
            for participant, employee in rows:
                review = self.review(participant.id, lock=True)
                if (
                    not review
                    or not participant.finalized_at
                    or review.finalized_at != participant.finalized_at
                    or review.evidence_version != participant.evidence_version
                    or review.evidence_hash
                    != collect(self.session, participant, employee, cycle).digest_for(
                        review.engine_version
                    )
                ):
                    count += 1
                    if len(issues) < 100:
                        issues.append(
                            {"participant_id": str(participant.id), "code": "review_not_finalized"}
                        )
            if not rows or count:
                raise ApiError(
                    409,
                    "cycle_reviews_incomplete",
                    "All participants must have finalized reviews",
                    [{"issue_count": count, "participant_count": len(rows)}, *issues],
                )
            cycle.status = CycleStatus.CLOSED
            cycle.version += 1
            AuditWriter().record(
                self.session,
                actor.id,
                "review_cycle.closed",
                "review_cycle",
                str(cycle.id),
                request_id,
                {
                    "cycle_id": str(cycle.id),
                    "version": cycle.version,
                    "count": len(rows),
                    "status": cycle.status.value,
                },
            )
            self.session.flush()
            return CloseResult(id=cycle.id, status=CycleStatus.CLOSED, version=cycle.version)
