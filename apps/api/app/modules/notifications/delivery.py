"""Business event -> durable, audience-scoped inbox entries in the SAME transaction."""

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session, aliased

from app.modules.audit.models import AuditLog
from app.modules.employees.models import Employee
from app.modules.feedback.models import FeedbackAssignment
from app.modules.notifications.models import Notification
from app.modules.review_cycles.models import CycleParticipant
from app.modules.users.models import User, UserRole

EVENTS = frozenset(
    {
        "review_cycle.activated",
        "review_cycle.closed",
        "kpi_allocation.replaced",
        "employee_kpi.actual_updated",
        "assignment.created",
        "assignment.updated",
        "assignment.reopened",
        "assignment.cancelled",
        "assignment.replaced",
        "feedback.submitted",
        "performance.calculated",
        "performance.finalized",
        "ai_analysis.succeeded",
        "ai_analysis.failed",
    }
)


def identifier(value: object) -> UUID | None:
    try:
        return UUID(str(value)) if value else None
    except ValueError:
        return None


def signal(session: Session, recipients: set[UUID]) -> None:
    if recipients:
        session.execute(
            text(
                "SELECT pg_notify('insighthr_notifications', recipient) "
                "FROM unnest(CAST(:recipients AS text[])) AS recipient"
            ),
            {"recipients": sorted(str(value) for value in recipients)},
        )


def deliver(session: Session, event: AuditLog) -> None:
    if event.action in {"user.role_changed", "user.status_changed"}:
        target = identifier(event.entity_id)
        signal(session, {target} if target else set())
        return
    if event.action in {"employee.created", "employee.updated"}:
        employee = session.get(Employee, identifier(event.entity_id))
        if employee:
            manager_ids = {
                value
                for value in (
                    employee.manager_id,
                    identifier(event.metadata_.get("previous_manager_id")),
                )
                if value
            }
            changed_recipients = {
                value
                for value in session.scalars(
                    select(Employee.user_id).where(Employee.id.in_(manager_ids))
                )
                if value
            }
            changed_recipients.update(
                session.scalars(select(User.id).where(User.role == UserRole.HR, User.is_active))
            )
            changed_recipients.update(
                value
                for value in (
                    employee.user_id,
                    identifier(event.metadata_.get("previous_user_id")),
                    event.actor_id,
                )
                if value
            )
            signal(session, changed_recipients)
        return
    if event.action not in EVENTS:
        return
    metadata = event.metadata_
    cycle_id = identifier(metadata.get("cycle_id"))
    participant_id = identifier(metadata.get("participant_id"))
    if event.action == "kpi_allocation.replaced":
        participant_id = identifier(event.entity_id)
    if event.action.startswith("review_cycle."):
        cycle_id = identifier(event.entity_id)
    assignment = None
    if event.entity_type == "feedback_assignment":
        assignment = session.get(FeedbackAssignment, identifier(event.entity_id))
        if assignment:
            participant_id = assignment.participant_id
    if event.action.startswith("ai_analysis."):
        from app.modules.performance.models import PerformanceReview

        review = session.get(PerformanceReview, identifier(metadata.get("review_id")))
        if review:
            participant_id = review.participant_id
    query = select(CycleParticipant, Employee).join(Employee)
    if participant_id:
        query = query.where(CycleParticipant.id == participant_id)
    elif cycle_id:
        query = query.where(CycleParticipant.cycle_id == cycle_id)
    else:
        return
    participants = list(session.execute(query))
    if not participants:
        return
    # One event per recipient, even if a manager owns multiple participating employees.
    targets: dict[UUID, tuple[UUID, UUID, UUID | None]] = {}
    refresh_targets: set[UUID] = set()
    hrs = list(session.scalars(select(User).where(User.role == UserRole.HR, User.is_active)))
    managers = aliased(Employee)
    manager_users = dict(
        session.execute(
            select(Employee.id, managers.user_id)
            .outerjoin(managers, Employee.manager_id == managers.id)
            .where(Employee.id.in_([employee.id for _, employee in participants]))
        ).all()
    )
    assignment_event = event.action.startswith("assignment.")
    private_ai = metadata.get("audience") == "HR_PRIVATE"
    for participant, employee in participants:
        cycle_id = participant.cycle_id
        if assignment_event and assignment:
            targets[assignment.reviewer_id] = (employee.id, cycle_id, assignment.id)
            refresh_targets.update(hr.id for hr in hrs)
            manager_user = manager_users.get(employee.id)
            if manager_user:
                refresh_targets.add(manager_user)
            continue
        if event.action in {
            "feedback.submitted",
            "performance.calculated",
            "kpi_allocation.replaced",
            "employee_kpi.actual_updated",
        } or event.action.startswith("ai_analysis."):
            for hr in hrs:
                targets[hr.id] = (employee.id, cycle_id, None)
        if private_ai:
            continue
        manager_id = manager_users.get(employee.id)
        if manager_id:
            targets[manager_id] = (employee.id, cycle_id, None)
        if employee.user_id and event.action != "feedback.submitted":
            targets[employee.user_id] = (employee.id, cycle_id, None)
    recipients = session.scalars(select(User).where(User.id.in_(targets), User.is_active))
    signals = {event.actor_id} if event.actor_id else set()
    signals.update(refresh_targets)
    for recipient in recipients:
        if recipient.id == event.actor_id:
            continue
        # ADMIN can receive an assigned feedback task, never HR/employee records.
        if recipient.role == UserRole.ADMIN and not assignment_event:
            continue
        employee_id, cycle_id, assignment_id = targets[recipient.id]
        session.add(
            Notification(
                event_id=event.id,
                recipient_id=recipient.id,
                recipient_role=recipient.role.value,
                kind=event.action,
                employee_id=employee_id,
                cycle_id=cycle_id,
                assignment_id=assignment_id,
            )
        )
        signals.add(recipient.id)
    signal(session, signals)
    session.flush()
