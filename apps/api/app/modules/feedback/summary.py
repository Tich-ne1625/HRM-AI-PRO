from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.feedback.models import AssignmentStatus, Feedback, FeedbackAssignment, Relationship
from app.modules.feedback.schemas import CoverageView, RatingGroup, SubmissionView, SummaryView
from app.modules.review_cycles.repository import CycleRepository
from app.modules.users.models import User


def rating_mean(ratings: Sequence[int]) -> str | None:
    if not ratings:
        return None
    return str(
        (Decimal(sum(ratings)) / len(ratings)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )


def rating_group(relationship: Relationship, ratings: Sequence[int]) -> RatingGroup:
    suppressed = relationship in (Relationship.PEER, Relationship.SUBORDINATE) and len(ratings) < 3
    return RatingGroup(
        relationship=relationship,
        suppressed=suppressed,
        count=None if suppressed else len(ratings),
        mean=None if suppressed else rating_mean(ratings),
    )


def coverage(session: Session, participant_id: UUID) -> CoverageView:
    rows = session.execute(
        select(FeedbackAssignment, User.is_active)
        .join(User, FeedbackAssignment.reviewer_id == User.id)
        .where(
            FeedbackAssignment.participant_id == participant_id,
            FeedbackAssignment.status != AssignmentStatus.CANCELLED,
        )
    ).all()
    missing = [
        rel
        for rel in (Relationship.SELF, Relationship.MANAGER)
        if not any(
            r.relationship == rel and r.status == AssignmentStatus.SUBMITTED for r, _ in rows
        )
    ]
    pending = sum(r.required and r.status != AssignmentStatus.SUBMITTED for r, _ in rows)
    blocked = sum(
        r.required and r.status == AssignmentStatus.OPEN and not active for r, active in rows
    )
    return CoverageView(
        ready=not missing and pending == 0,
        missing_relationships=missing,
        pending_required=pending,
        blocked_required=blocked,
    )


def employee_summary(
    session: Session, employee_id: UUID, cycle_id: UUID, user: User
) -> SummaryView:
    with session.begin():
        participant, _, _ = CycleRepository(session).participant_for_employee(
            employee_id, cycle_id, user
        )
        rows = session.execute(
            select(FeedbackAssignment, Feedback)
            .join(Feedback, Feedback.assignment_id == FeedbackAssignment.id)
            .where(
                FeedbackAssignment.participant_id == participant.id,
                FeedbackAssignment.status == AssignmentStatus.SUBMITTED,
            )
        ).all()
        own = next(
            (feedback for assignment, feedback in rows if assignment.reviewer_id == user.id), None
        )
        return SummaryView(
            participant_id=participant.id,
            employee_id=employee_id,
            cycle_id=cycle_id,
            evidence_version=participant.evidence_version,
            ready=coverage(session, participant.id).ready,
            count=len(rows),
            mean=rating_mean([f.rating for _, f in rows]),
            groups=[
                rating_group(rel, [f.rating for a, f in rows if a.relationship == rel])
                for rel in Relationship
            ],
            own_submission=SubmissionView(
                rating=own.rating, comment=own.comment, submitted_at=own.submitted_at
            )
            if own
            else None,
        )
