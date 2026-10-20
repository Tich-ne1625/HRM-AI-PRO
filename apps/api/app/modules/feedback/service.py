from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.domain_writes import CsrfCheck, authorize_domain_write, require_version
from app.core.errors import ApiError
from app.core.policies import AuthContext
from app.modules.audit.models import AuditValue
from app.modules.audit.service import AuditWriter
from app.modules.feedback.models import AssignmentStatus, Feedback, FeedbackAssignment, Relationship
from app.modules.feedback.repository import FeedbackRepository
from app.modules.feedback.schemas import (
    AssignmentCancel,
    AssignmentCreate,
    AssignmentReplace,
    AssignmentUpdate,
    AssignmentVersions,
    AssignmentView,
    FeedbackCreate,
)
from app.modules.organization.repository import OrganizationRepository
from app.modules.review_cycles.models import CycleParticipant, CycleStatus, ReviewCycle
from app.modules.users.models import User, UserRole


def writable(participant: CycleParticipant, cycle: ReviewCycle) -> None:
    if cycle.status != CycleStatus.ACTIVE:
        raise ApiError(409, "cycle_not_active", "Feedback requires an ACTIVE cycle")
    if participant.finalized_at is not None:
        raise ApiError(409, "participant_finalized", "Finalized evidence cannot be changed")


def future_deadline(due_at: datetime | None) -> None:
    if due_at is not None and datetime.now(UTC) >= due_at:
        raise ApiError(409, "deadline_passed", "Choose a future deadline or clear the deadline")


class FeedbackService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = FeedbackRepository(session)

    def lock_participant(self, identifier: UUID) -> tuple[CycleParticipant, ReviewCycle]:
        cycle_id = self.session.scalar(
            select(CycleParticipant.cycle_id).where(CycleParticipant.id == identifier)
        )
        if cycle_id is None:
            raise ApiError(404, "participant_not_found", "Participant not found")
        cycle = self.session.get(
            ReviewCycle, cycle_id, with_for_update=True, populate_existing=True
        )
        participant = self.session.get(
            CycleParticipant, identifier, with_for_update=True, populate_existing=True
        )
        assert cycle is not None and participant is not None
        writable(participant, cycle)
        return participant, cycle

    def lock_assignments(self, participant_id: UUID) -> list[FeedbackAssignment]:
        return list(
            self.session.scalars(
                select(FeedbackAssignment)
                .where(FeedbackAssignment.participant_id == participant_id)
                .order_by(FeedbackAssignment.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def versions(
        self, row: FeedbackAssignment, participant: CycleParticipant, body: AssignmentVersions
    ) -> None:
        if row.version != body.expected_assignment_version:
            raise ApiError(
                409, "stale_assignment_version", "Assignment has changed; reload explicitly"
            )
        require_version(participant.evidence_version, body.expected_evidence_version, evidence=True)

    def audit(
        self,
        actor: User,
        action: str,
        row: FeedbackAssignment,
        participant: CycleParticipant,
        request_id: str,
        extra: dict[str, AuditValue] | None = None,
    ) -> None:
        AuditWriter().record(
            self.session,
            actor.id,
            action,
            "feedback_assignment",
            str(row.id),
            request_id,
            {
                "participant_id": str(participant.id),
                "reviewer_id": str(row.reviewer_id),
                "relationship": row.relationship.value,
                "required": row.required,
                "status": row.status.value,
                "version": row.version,
                "evidence_version": participant.evidence_version,
                **(extra or {}),
            },
        )

    def authorize_assignment(
        self,
        identifier: UUID,
        context: AuthContext,
        csrf: CsrfCheck,
        *,
        own: bool,
        additional_users: set[UUID] | None = None,
    ) -> tuple[User, FeedbackAssignment, CycleParticipant]:
        OrganizationRepository(self.session).lock_guard()
        # Resolve only through the actor's SQL scope, before exposing lifecycle/version errors.
        row = self.repository.assignment(identifier, context.user, own=own)
        actor = authorize_domain_write(
            self.session,
            context,
            csrf,
            tuple(UserRole) if own else (UserRole.HR,),
            {row.reviewer_id} | (additional_users or set()),
        )
        # Recheck the scope against the role revalidated under user locks.
        row = self.repository.assignment(identifier, actor, own=own)
        participant, _ = self.lock_participant(row.participant_id)
        rows = self.lock_assignments(participant.id)
        return actor, next(r for r in rows if r.id == identifier), participant

    def capacity(self, rows: list[FeedbackAssignment], *, replacing: bool = False) -> None:
        active = sum(r.status != AssignmentStatus.CANCELLED for r in rows)
        if active >= 100 and not replacing:
            raise ApiError(
                409, "assignment_limit_reached", "At most 100 active assignments are allowed"
            )

    def new_row(
        self,
        participant: CycleParticipant,
        reviewer_id: UUID,
        relationship: Relationship,
        required: bool,
        due_at: datetime | None,
        rows: list[FeedbackAssignment],
    ) -> FeedbackAssignment:
        if any(r.reviewer_id == reviewer_id for r in rows):
            raise ApiError(
                409, "assignment_already_exists", "Assignment exists; reopen if cancelled"
            )
        if relationship in (Relationship.SELF, Relationship.MANAGER) and any(
            r.relationship == relationship and r.status != AssignmentStatus.CANCELLED for r in rows
        ):
            raise ApiError(
                409, "required_relationship_exists", "Mandatory relationship already assigned"
            )
        employee, reviewer = self.repository.eligible(participant, reviewer_id, relationship)
        row = FeedbackAssignment(
            participant_id=participant.id,
            reviewer_id=reviewer.id,
            reviewer_employee_id=employee.id,
            relationship=relationship,
            required=required,
            due_at=due_at,
            status=AssignmentStatus.OPEN,
            version=1,
            eligibility_snapshot={
                "schema_version": 1,
                "rule_version": 1,
                "source": "ASSIGNMENT" if relationship == Relationship.PEER else "ACTIVATION",
                "reviewer_id": str(reviewer.id),
                "reviewer_employee_id": str(employee.id),
                "relationship": relationship.value,
                "participant_id": str(participant.id),
            },
        )
        self.session.add(row)
        return row

    def create(
        self, body: AssignmentCreate, context: AuthContext, *, csrf: CsrfCheck, request_id: str
    ) -> AssignmentView:
        with self.session.begin():
            actor = authorize_domain_write(
                self.session, context, csrf, (UserRole.HR,), {body.reviewer_id}
            )
            participant, _ = self.lock_participant(body.participant_id)
            require_version(
                participant.evidence_version, body.expected_evidence_version, evidence=True
            )
            future_deadline(body.due_at)
            rows = self.lock_assignments(participant.id)
            self.capacity(rows)
            row = self.new_row(
                participant, body.reviewer_id, body.relationship, body.required, body.due_at, rows
            )
            participant.evidence_version += 1
            self.session.flush()
            self.audit(actor, "assignment.created", row, participant, request_id)
            return self.repository.view(row, administration=True)

    def update(
        self,
        identifier: UUID,
        body: AssignmentUpdate,
        context: AuthContext,
        *,
        csrf: CsrfCheck,
        request_id: str,
    ) -> AssignmentView:
        with self.session.begin():
            actor, row, participant = self.authorize_assignment(
                identifier, context, csrf, own=False
            )
            if row.status == AssignmentStatus.SUBMITTED:
                raise ApiError(409, "assignment_not_open", "Submitted assignments are immutable")
            self.versions(row, participant, body)
            reopen = row.status == AssignmentStatus.CANCELLED
            if reopen and body.status != AssignmentStatus.OPEN:
                raise ApiError(
                    409, "assignment_not_open", "Reopen cancelled assignments explicitly"
                )
            if body.required is False and row.relationship in (
                Relationship.SELF,
                Relationship.MANAGER,
            ):
                raise ApiError(
                    409, "required_coverage_conflict", "SELF and MANAGER must remain required"
                )
            due = body.due_at if "due_at" in body.model_fields_set else row.due_at
            # An expired OPEN assignment may still have required changed; editing its
            # deadline or reopening always requires a future deadline or explicit null.
            if reopen or "due_at" in body.model_fields_set:
                future_deadline(due)
            if reopen:
                self.capacity(self.lock_assignments(participant.id))
                employee, _ = self.repository.eligible(
                    participant, row.reviewer_id, row.relationship
                )
                if employee.id != row.reviewer_employee_id:
                    raise ApiError(
                        409, "reviewer_ineligible", "Original reviewer identity has changed"
                    )
            required = row.required if body.required is None else body.required
            if reopen or row.required != required or row.due_at != due:
                row.required, row.due_at, row.status = required, due, AssignmentStatus.OPEN
                row.version += 1
                participant.evidence_version += 1
                self.session.flush()
                self.audit(
                    actor,
                    "assignment.reopened" if reopen else "assignment.updated",
                    row,
                    participant,
                    request_id,
                )
            return self.repository.view(row, administration=True)

    def cancel(
        self,
        identifier: UUID,
        body: AssignmentCancel,
        context: AuthContext,
        *,
        csrf: CsrfCheck,
        request_id: str,
    ) -> AssignmentView:
        with self.session.begin():
            actor, row, participant = self.authorize_assignment(
                identifier, context, csrf, own=False
            )
            if row.status != AssignmentStatus.OPEN:
                raise ApiError(409, "assignment_not_open", "Only open assignments can be cancelled")
            self.versions(row, participant, body)
            if row.required:
                raise ApiError(
                    409, "required_coverage_conflict", "Required assignments cannot be cancelled"
                )
            row.status = AssignmentStatus.CANCELLED
            row.version += 1
            participant.evidence_version += 1
            self.session.flush()
            self.audit(
                actor,
                "assignment.cancelled",
                row,
                participant,
                request_id,
                {"reason_code": body.reason_code.value},
            )
            return self.repository.view(row, administration=True)

    def replace(
        self,
        identifier: UUID,
        body: AssignmentReplace,
        context: AuthContext,
        *,
        csrf: CsrfCheck,
        request_id: str,
    ) -> AssignmentView:
        with self.session.begin():
            actor, old, participant = self.authorize_assignment(
                identifier, context, csrf, own=False, additional_users={body.reviewer_id}
            )
            if old.status != AssignmentStatus.OPEN:
                raise ApiError(409, "assignment_not_open", "Only open assignments can be replaced")
            self.versions(old, participant, body)
            if old.relationship in (Relationship.SELF, Relationship.MANAGER):
                raise ApiError(
                    409, "required_coverage_conflict", "Historical principals cannot be delegated"
                )
            future_deadline(body.due_at)
            rows = self.lock_assignments(participant.id)
            candidate = next((r for r in rows if r.reviewer_id == body.reviewer_id), None)
            if candidate is not None:
                if candidate.status != AssignmentStatus.CANCELLED:
                    raise ApiError(
                        409, "assignment_already_exists", "Replacement is already assigned"
                    )
                employee, _ = self.repository.eligible(
                    participant, body.reviewer_id, old.relationship
                )
                if (
                    candidate.relationship != old.relationship
                    or candidate.reviewer_employee_id != employee.id
                ):
                    raise ApiError(
                        409, "reviewer_ineligible", "Original cancelled identity must be preserved"
                    )
                candidate.status = AssignmentStatus.OPEN
                candidate.required, candidate.due_at = old.required, body.due_at
                candidate.version += 1
            else:
                candidate = self.new_row(
                    participant, body.reviewer_id, old.relationship, old.required, body.due_at, rows
                )
            old.status = AssignmentStatus.CANCELLED
            old.version += 1
            participant.evidence_version += 1
            self.session.flush()
            extra: dict[str, AuditValue] = {
                "reason_code": body.reason_code.value,
                "replacement_id": str(candidate.id),
            }
            self.audit(actor, "assignment.replaced", old, participant, request_id, extra)
            self.audit(
                actor,
                "assignment.reopened" if candidate in rows else "assignment.created",
                candidate,
                participant,
                request_id,
                {"previous_assignment_id": str(old.id)},
            )
            return self.repository.view(candidate, administration=True)

    def submit(
        self, body: FeedbackCreate, context: AuthContext, *, csrf: CsrfCheck, request_id: str
    ) -> AssignmentView:
        with self.session.begin():
            actor, row, participant = self.authorize_assignment(
                body.assignment_id, context, csrf, own=True
            )
            if row.status == AssignmentStatus.SUBMITTED:
                raise ApiError(
                    409, "feedback_already_submitted", "Feedback has already been received"
                )
            if row.status != AssignmentStatus.OPEN:
                raise ApiError(409, "assignment_not_open", "Assignment is not open")
            self.versions(row, participant, body)
            future_deadline(row.due_at)
            self.session.add(
                Feedback(assignment_id=row.id, rating=body.rating, comment=body.comment)
            )
            row.status = AssignmentStatus.SUBMITTED
            row.version += 1
            participant.evidence_version += 1
            self.session.flush()
            self.audit(actor, "feedback.submitted", row, participant, request_id)
            return self.repository.view(row, administration=False)
