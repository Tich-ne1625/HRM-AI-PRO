"""Explicit public projections; private evidence JSON never leaves the service."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.feedback.models import Feedback, FeedbackAssignment, Relationship
from app.modules.feedback.schemas import SubmissionView
from app.modules.feedback.summary import rating_group, rating_mean
from app.modules.performance.models import PerformanceReview, PerformanceReviewRevision
from app.modules.performance.schemas import CalculationView, FeedbackAggregate, ScoreLine
from app.modules.users.models import User


def calculation(
    session: Session, row: PerformanceReview | PerformanceReviewRevision, user: User
) -> CalculationView:
    snapshot: dict[str, Any] = row.evidence_snapshot
    submitted = [a for a in snapshot["assignments"] if a["status"] == "SUBMITTED"]
    own_id = next((a["id"] for a in submitted if a["reviewer_id"] == str(user.id)), None)
    own = (
        session.scalar(
            select(Feedback)
            .join(FeedbackAssignment, Feedback.assignment_id == FeedbackAssignment.id)
            .where(FeedbackAssignment.id == own_id, FeedbackAssignment.reviewer_id == user.id)
        )
        if own_id
        else None
    )
    return CalculationView(
        calculation_version=row.calculation_version,
        evidence_version=row.evidence_version,
        engine_version=row.engine_version,
        calculated_at=row.calculated_at,
        kpi_score=format(row.kpi_score, ".2f"),
        feedback_score=format(row.feedback_score, ".2f"),
        final_score=format(row.final_score, ".2f"),
        policy=row.policy_snapshot,
        items=[ScoreLine.model_validate(item) for item in snapshot["results"]],
        feedback=FeedbackAggregate(
            count=len(submitted),
            mean=rating_mean([a["rating"] for a in submitted]),
            groups=[
                rating_group(
                    rel, [a["rating"] for a in submitted if a["relationship"] == rel.value]
                )
                for rel in Relationship
            ],
            own_submission=SubmissionView(
                rating=own.rating, comment=own.comment, submitted_at=own.submitted_at
            )
            if own
            else None,
        ),
    )
