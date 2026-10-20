from uuid import UUID

from sqlalchemy import Select, false, func, select, true
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.modules.employees.models import Employee, EmploymentStatus
from app.modules.feedback.eligibility import historical_candidates, relationship_for
from app.modules.feedback.models import AssignmentStatus, Feedback, FeedbackAssignment, Relationship
from app.modules.feedback.schemas import (
    AdministrationView,
    AssignmentView,
    ReviewerOption,
    SubmissionView,
)
from app.modules.organization.schemas import Page
from app.modules.review_cycles.models import CycleParticipant, ReviewCycle
from app.modules.review_cycles.schemas import ParticipantSnapshot
from app.modules.users.models import User, UserRole


class FeedbackRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def assignment(self, identifier: UUID, user: User, *, own: bool = False) -> FeedbackAssignment:
        scope = FeedbackAssignment.reviewer_id == user.id
        if user.role == UserRole.HR and not own:
            scope = true()
        row = self.session.scalar(
            select(FeedbackAssignment).where(FeedbackAssignment.id == identifier, scope)
        )
        if row is None:
            raise ApiError(404, "assignment_not_found", "Assignment not found")
        return row

    def participant(self, identifier: UUID) -> CycleParticipant:
        row = self.session.get(CycleParticipant, identifier)
        if row is None:
            raise ApiError(404, "participant_not_found", "Participant not found")
        return row

    def view(self, row: FeedbackAssignment, *, administration: bool) -> AssignmentView:
        result = self.session.execute(
            self.view_query().where(FeedbackAssignment.id == row.id)
        ).one()
        return self.present(*result, administration=administration)

    @staticmethod
    def view_query() -> Select[
        FeedbackAssignment, CycleParticipant, ReviewCycle, Feedback, Employee, User
    ]:
        return (
            select(FeedbackAssignment, CycleParticipant, ReviewCycle, Feedback, Employee, User)
            .join(CycleParticipant, FeedbackAssignment.participant_id == CycleParticipant.id)
            .join(ReviewCycle, CycleParticipant.cycle_id == ReviewCycle.id)
            .outerjoin(Feedback, Feedback.assignment_id == FeedbackAssignment.id)
            .join(Employee, FeedbackAssignment.reviewer_employee_id == Employee.id)
            .join(User, FeedbackAssignment.reviewer_id == User.id)
        )

    @staticmethod
    def present(
        row: FeedbackAssignment,
        participant: CycleParticipant,
        cycle: ReviewCycle,
        feedback: Feedback | None,
        employee: Employee,
        reviewer: User,
        *,
        administration: bool,
    ) -> AssignmentView:
        snapshot = ParticipantSnapshot.model_validate(participant.snapshot)
        submission = (
            SubmissionView(
                rating=feedback.rating, comment=feedback.comment, submitted_at=feedback.submitted_at
            )
            if feedback
            else None
        )
        common = AssignmentView(
            id=row.id,
            participant_id=participant.id,
            cycle_id=cycle.id,
            cycle_name=cycle.name,
            cycle_status=cycle.status,
            start_date=cycle.start_date.isoformat(),
            end_date=cycle.end_date.isoformat(),
            employee_id=snapshot.employee_id,
            employee_code=snapshot.employee_code,
            display_name=snapshot.display_name,
            relationship=row.relationship,
            required=row.required,
            status=row.status,
            due_at=row.due_at,
            version=row.version,
            evidence_version=participant.evidence_version,
            finalized=participant.finalized_at is not None,
            submission=submission,
        )
        if not administration:
            return common
        return AdministrationView(
            **common.model_dump(),
            reviewer_id=row.reviewer_id,
            reviewer_employee_id=row.reviewer_employee_id,
            reviewer_name=employee.display_name,
            reviewer_active=reviewer.is_active,
        )

    def listing(
        self,
        user: User,
        *,
        administration: bool,
        cycle_id: UUID | None,
        participant_id: UUID | None,
        status: AssignmentStatus | None,
        relationship: Relationship | None,
        page: int,
        page_size: int,
        sort: str = "due_at",
    ) -> Page[AssignmentView | AdministrationView]:
        if administration and user.role != UserRole.HR:
            raise ApiError(403, "forbidden", "Access is forbidden")
        query = self.view_query().where(
            true() if administration else FeedbackAssignment.reviewer_id == user.id
        )
        if cycle_id:
            query = query.where(CycleParticipant.cycle_id == cycle_id)
        if participant_id:
            query = query.where(FeedbackAssignment.participant_id == participant_id)
        if status:
            query = query.where(FeedbackAssignment.status == status)
        if relationship:
            query = query.where(FeedbackAssignment.relationship == relationship)
        total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = self.session.execute(
            query.order_by(
                (
                    FeedbackAssignment.due_at.asc().nulls_last()
                    if sort == "due_at"
                    else FeedbackAssignment.created_at.asc()
                ),
                FeedbackAssignment.created_at,
                FeedbackAssignment.id,
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return Page(
            items=[self.present(*r, administration=administration) for r in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    def eligible_query(
        self, participant: CycleParticipant, relationship: Relationship
    ) -> Select[Employee, User]:
        snapshot = ParticipantSnapshot.model_validate(participant.snapshot).model_dump(mode="json")
        if relationship != Relationship.PEER:
            candidates = historical_candidates(snapshot, relationship)
            pairs = [(UUID(uid), UUID(eid)) for uid, eid in candidates.items()]
            # Historical account ownership survives unlinking or employment/role changes.
            from sqlalchemy import or_

            return (
                select(Employee, User)
                .join(
                    User,
                    or_(*((Employee.id == eid) & (User.id == uid) for uid, eid in pairs))
                    if pairs
                    else false(),
                )
                .where(Employee.id.in_([p[1] for p in pairs]))
            )
        excluded_users = {snapshot["user_id"], snapshot["manager_user_id"]} | {
            str(r["user_id"]) for r in snapshot["direct_reports"] if r["user_id"]
        }
        excluded_employees = {snapshot["employee_id"], snapshot["manager_id"]} | {
            str(r["employee_id"]) for r in snapshot["direct_reports"]
        }
        return (
            select(Employee, User)
            .join(User, Employee.user_id == User.id)
            .where(
                Employee.employment_status == EmploymentStatus.ACTIVE,
                User.is_active.is_(True),
                Employee.id.not_in([UUID(v) for v in excluded_employees]),
                User.id.not_in([UUID(v) for v in excluded_users]),
            )
        )

    def eligible(
        self, participant: CycleParticipant, reviewer_id: UUID, relationship: Relationship
    ) -> tuple[Employee, User]:
        pair = self.session.execute(
            self.eligible_query(participant, relationship).where(User.id == reviewer_id)
        ).one_or_none()
        if pair is None:
            raise ApiError(409, "reviewer_ineligible", "Reviewer does not match the relationship")
        employee, user = pair
        if not user.is_active:
            raise ApiError(409, "reviewer_inactive", "The historical reviewer account is inactive")
        snapshot = ParticipantSnapshot.model_validate(participant.snapshot).model_dump(mode="json")
        if relationship_for(snapshot, str(user.id), str(employee.id)) != relationship:
            raise ApiError(409, "reviewer_ineligible", "Reviewer does not match the relationship")
        return employee, user

    def options(
        self,
        participant: CycleParticipant,
        relationship: Relationship,
        *,
        page: int,
        page_size: int,
        q: str | None,
    ) -> Page[ReviewerOption]:
        query = self.eligible_query(participant, relationship)
        if q:
            from sqlalchemy import or_

            query = query.where(
                or_(
                    Employee.employee_code.icontains(q, autoescape=True),
                    Employee.display_name.icontains(q, autoescape=True),
                )
            )
        total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = self.session.execute(
            query.order_by(Employee.employee_code, Employee.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        existing = {
            r.reviewer_id: r
            for r in self.session.scalars(
                select(FeedbackAssignment).where(
                    FeedbackAssignment.participant_id == participant.id,
                    FeedbackAssignment.reviewer_id.in_([u.id for _, u in rows]),
                )
            )
        }
        return Page(
            items=[
                ReviewerOption(
                    reviewer_id=u.id,
                    employee_id=e.id,
                    employee_code=e.employee_code,
                    display_name=e.display_name,
                    is_active=u.is_active,
                    existing_assignment_id=existing[u.id].id if u.id in existing else None,
                    existing_status=existing[u.id].status if u.id in existing else None,
                )
                for e, u in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
        )
