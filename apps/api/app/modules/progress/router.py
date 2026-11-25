from datetime import UTC, date, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.core.policies import AuthContext
from app.modules.auth.router import require_csrf, require_same_origin
from app.modules.progress.checkins import CheckinService
from app.modules.progress.schemas import (
    CheckinCommand,
    CheckinCreate,
    FollowupCommand,
    FollowupCreate,
    MeasurementCommand,
    MeasurementDraft,
    PreparationDraft,
)
from app.modules.progress.service import ProgressService
from app.modules.users.models import UserRole
from app.modules.work_management.router import Actor, Database, Page

router = APIRouter(prefix="/api/v1", tags=["progress"])


def writer_context(context: Actor) -> AuthContext:
    # Deny unsupported roles before resolving a target, including on draft routes.
    # Services still re-authorize the active account/family under the write locks.
    if context.user.role not in {UserRole.MANAGER, UserRole.EMPLOYEE}:
        from app.modules.progress.service import fail

        fail("forbidden", "Only work participants may write progress records", 403)
    return context


Writer = Annotated[AuthContext, Depends(writer_context)]


@router.get("/progress/plans/{identifier}/goals")
def goals(
    identifier: UUID,
    context: Actor,
    session: Database,
    from_date: date | None = None,
    to_date: date | None = None,
) -> dict[str, Any]:
    return ProgressService(session).goals(context.user, identifier, from_date, to_date)


@router.get("/progress/goals/{identifier}/measurements")
def measurements(
    identifier: UUID, context: Actor, session: Database, page: Page = 1
) -> dict[str, Any]:
    return ProgressService(session).listing(context.user, identifier, page)


@router.post(
    "/progress/goals/{identifier}/measurements", dependencies=[Depends(require_same_origin)]
)
def create_measurement(
    identifier: UUID, data: MeasurementDraft, context: Writer, session: Database, request: Request
) -> dict[str, Any]:
    return ProgressService(session).save(
        context, lambda row: require_csrf(request, row), identifier, data, request.state.request_id
    )


@router.get("/progress/measurements/{identifier}")
def measurement(
    identifier: UUID,
    context: Actor,
    session: Database,
    page: Page = 1,
    revision_number: int | None = None,
) -> dict[str, Any]:
    return ProgressService(session).detail(context.user, identifier, page, revision_number)


@router.post(
    "/progress/measurements/{identifier}/draft", dependencies=[Depends(require_same_origin)]
)
def draft_measurement(
    identifier: UUID, data: MeasurementDraft, context: Writer, session: Database, request: Request
) -> dict[str, Any]:
    from app.modules.progress.models import Measurement, MetricRule
    from app.modules.progress.service import fail

    # Resolve the immutable parent without opening an implicit session transaction.
    with session.begin():
        row = session.get(Measurement, identifier)
        rule = session.get(MetricRule, row.rule_id) if row else None
        if rule is None:
            fail("work_not_found", "Measurement not found", 404)
        assert rule is not None
        goal_id = rule.goal_id
    return ProgressService(session).save(
        context,
        lambda row: require_csrf(request, row),
        goal_id,
        data,
        request.state.request_id,
        identifier,
    )


@router.post(
    "/progress/measurements/{identifier}/actions", dependencies=[Depends(require_same_origin)]
)
def measurement_action(
    identifier: UUID, data: MeasurementCommand, context: Writer, session: Database, request: Request
) -> dict[str, Any]:
    return ProgressService(session).command(
        context, lambda row: require_csrf(request, row), identifier, data, request.state.request_id
    )


@router.get("/progress/plans/{identifier}/snapshots")
def snapshots(
    identifier: UUID, context: Actor, session: Database, page: Page = 1
) -> dict[str, Any]:
    return ProgressService(session).snapshots(context.user, identifier, page)


@router.get("/progress/snapshots/{identifier}")
def snapshot(
    identifier: UUID, context: Actor, session: Database, page: Page = 1, goal_id: UUID | None = None
) -> dict[str, Any]:
    return ProgressService(session).snapshot_detail(context.user, identifier, page, goal_id)


@router.get("/checkins")
def checkins(plan_id: UUID, context: Actor, session: Database, page: Page = 1) -> dict[str, Any]:
    return CheckinService(session).listing(context.user, plan_id, page)


@router.post("/progress/plans/{identifier}/checkins", dependencies=[Depends(require_same_origin)])
def create_checkin(
    identifier: UUID, data: CheckinCreate, context: Writer, session: Database, request: Request
) -> dict[str, Any]:
    return CheckinService(session).create(
        context, lambda row: require_csrf(request, row), identifier, data, request.state.request_id
    )


@router.get("/checkins/{identifier}")
def checkin(identifier: UUID, context: Actor, session: Database, page: Page = 1) -> dict[str, Any]:
    return CheckinService(session).detail(context.user, identifier, page)


@router.post("/checkins/{identifier}/preparation", dependencies=[Depends(require_same_origin)])
def prepare(
    identifier: UUID, data: PreparationDraft, context: Writer, session: Database, request: Request
) -> dict[str, Any]:
    return CheckinService(session).prepare(
        context, lambda row: require_csrf(request, row), identifier, data, request.state.request_id
    )


@router.post("/checkins/{identifier}/actions", dependencies=[Depends(require_same_origin)])
def checkin_action(
    identifier: UUID, data: CheckinCommand, context: Writer, session: Database, request: Request
) -> dict[str, Any]:
    return CheckinService(session).command(
        context, lambda row: require_csrf(request, row), identifier, data, request.state.request_id
    )


@router.post("/checkins/{identifier}/follow-ups", dependencies=[Depends(require_same_origin)])
def followup(
    identifier: UUID, data: FollowupCreate, context: Writer, session: Database, request: Request
) -> dict[str, Any]:
    return CheckinService(session).followup(
        context, lambda row: require_csrf(request, row), identifier, data, request.state.request_id
    )


@router.post("/checkin-actions/{identifier}/actions", dependencies=[Depends(require_same_origin)])
def action_command(
    identifier: UUID, data: FollowupCommand, context: Writer, session: Database, request: Request
) -> dict[str, Any]:
    return CheckinService(session).action_command(
        context, lambda row: require_csrf(request, row), identifier, data, request.state.request_id
    )


@router.get("/progress/plans/{identifier}/coordination")
def coordination(identifier: UUID, context: Actor, session: Database) -> dict[str, Any]:
    from sqlalchemy import func, select

    from app.modules.progress.models import Checkin, CheckinAction, Measurement
    from app.modules.progress.service import fail
    from app.modules.users.models import UserRole
    from app.modules.work_management.repository import WorkRepository

    if context.user.role != UserRole.HR:
        fail("forbidden", "This view is for HR coordination", 403)
    with session.begin():
        repository = WorkRepository(session)
        plan, _, employee, cycle = repository.plan(identifier, context.user)

        def counts(model: Any) -> dict[str, int]:
            return dict(
                session.execute(
                    select(model.status, func.count())
                    .where(model.plan_id == plan.id)
                    .group_by(model.status)
                ).all()
            )

        now = datetime.now(UTC)
        assert cycle.workflow_schedule is not None
        measurement_counts = counts(Measurement)
        late_checkins = (
            session.scalar(
                select(func.count())
                .select_from(Checkin)
                .where(
                    Checkin.plan_id == plan.id,
                    Checkin.status.in_(["SCHEDULED", "OPEN"]),
                    Checkin.scheduled_at < now,
                )
            )
            or 0
        )
        late_actions = (
            session.scalar(
                select(func.count())
                .select_from(CheckinAction)
                .where(
                    CheckinAction.plan_id == plan.id,
                    CheckinAction.status.notin_(["DONE", "CANCELLED"]),
                    CheckinAction.due_at < now,
                )
            )
            or 0
        )
        return {
            "employee_name": employee.display_name,
            "measurements": measurement_counts,
            "checkins": counts(Checkin),
            "actions": counts(CheckinAction),
            "needs_hr": not repository.operational(employee),
            "overdue": {
                "checkins": late_checkins,
                "actions": late_actions,
                "measurements": measurement_counts.get("SUBMITTED", 0)
                if now > datetime.fromisoformat(str(cycle.workflow_schedule["verification_due_at"]))
                else 0,
            },
        }
