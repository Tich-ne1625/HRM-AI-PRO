from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.domain_writes import CsrfCheck, require_version
from app.core.policies import AuthContext
from app.modules.employees.models import Employee
from app.modules.progress.models import (
    Checkin,
    CheckinAction,
    CheckinPreparation,
    CheckinPublication,
    ProgressSnapshot,
)
from app.modules.progress.schemas import (
    CheckinCommand,
    CheckinCreate,
    FollowupCommand,
    FollowupCreate,
    PreparationDraft,
)
from app.modules.progress.service import ProgressService, fail
from app.modules.review_cycles.models import ReviewCycle
from app.modules.users.models import User


class CheckinService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.progress = ProgressService(session)

    def row(self, identifier: UUID) -> Checkin:
        row = self.session.get(Checkin, identifier)
        if row is None:
            fail("work_not_found", "Check-in not found", 404)
        assert row is not None
        return row

    def view(
        self, row: Checkin, actor: User, employee: Employee, cycle: ReviewCycle
    ) -> dict[str, Any]:
        manager = self.progress.repo.manager(employee)
        is_manager = bool(manager and manager.id == actor.id)
        assert cycle.workflow_schedule is not None
        actions_open = self.progress.repo.operational(employee) and datetime.now(
            UTC
        ) <= datetime.fromisoformat(str(cycle.workflow_schedule["verification_due_at"]))
        actions = []
        if actions_open:
            if is_manager and row.status in {"SCHEDULED", "OPEN"}:
                actions.extend(["reschedule", "cancel"])
                actions.append("open" if row.status == "SCHEDULED" else "publish")
            if is_manager and row.status == "PUBLISHED":
                actions.extend(["addendum", "create_followup"])
            if actor.id == employee.user_id and row.status == "PUBLISHED":
                if (
                    not row.clarification_pending
                    and row.acknowledged_publication != row.publication
                ):
                    actions.append("acknowledge")
                actions.append("clarify")
        assert cycle.workflow_schedule is not None
        return {
            "id": row.id,
            "plan_id": row.plan_id,
            "version": row.version,
            "title": row.title,
            "status": row.status,
            "scheduled_at": row.scheduled_at,
            "period_start": row.period_start,
            "period_end": row.period_end,
            "publication": row.publication,
            "acknowledged_publication": row.acknowledged_publication,
            "clarification_pending": row.clarification_pending,
            "snapshot_id": row.snapshot_id,
            "owner_id": employee.user_id,
            "manager_id": manager.id if manager else None,
            "verification_due_at": cycle.workflow_schedule["verification_due_at"],
            "actions": actions,
            "can_prepare": actions_open and row.status in {"SCHEDULED", "OPEN"},
            "actions_open": actions_open,
            "overdue": row.status in {"SCHEDULED", "OPEN"} and row.scheduled_at < datetime.now(UTC),
        }

    @staticmethod
    def validate_schedule(cycle: ReviewCycle, scheduled: datetime) -> None:
        assert cycle.workflow_schedule is not None
        if (
            not datetime.now(UTC)
            < scheduled
            <= datetime.fromisoformat(str(cycle.workflow_schedule["verification_due_at"]))
        ):
            fail(
                "invalid_checkin_schedule",
                "Schedule a future check-in before the verification deadline",
                422,
            )

    def create(
        self,
        context: AuthContext,
        csrf: CsrfCheck,
        plan_id: UUID,
        data: CheckinCreate,
        request_id: str,
    ) -> dict[str, Any]:
        with self.session.begin():
            actor, plan, employee, cycle = self.progress.writable(context, csrf, plan_id)
            self.progress.repo.require_manager(employee, actor)
            replay = self.progress.receipt(actor, data, plan_id, "checkin.create")
            if replay:
                return self.view(
                    self.row(UUID(str(replay.payload["target_id"]))), actor, employee, cycle
                )
            require_version(plan.version, data.expected_version)
            self.validate_schedule(cycle, data.scheduled_at)
            if not cycle.start_date <= data.period_start <= data.period_end <= cycle.end_date:
                fail("invalid_checkin_period", "The review period must be within the cycle", 422)
            row = Checkin(
                plan_id=plan.id,
                title=data.title,
                scheduled_at=data.scheduled_at,
                period_start=data.period_start,
                period_end=data.period_end,
                status="SCHEDULED",
                version=1,
                publication=0,
            )
            self.session.add(row)
            self.progress.record(
                actor, plan, employee, data, plan_id, "checkin.create", request_id, checkin=row
            )
            return self.view(row, actor, employee, cycle)

    def prepare(
        self,
        context: AuthContext,
        csrf: CsrfCheck,
        identifier: UUID,
        data: PreparationDraft,
        request_id: str,
    ) -> dict[str, Any]:
        with self.session.begin():
            row = self.row(identifier)
            actor, plan, employee, cycle = self.progress.writable(context, csrf, row.plan_id)
            self.session.refresh(row)
            replay = self.progress.receipt(actor, data, identifier, "checkin.prepare")
            if not replay:
                self.progress.deadline(cycle, verification=True)
                if row.status not in {"SCHEDULED", "OPEN"}:
                    fail("checkin_state_conflict", "The preparation is closed")
                preparation = self.session.scalar(
                    select(CheckinPreparation).where(
                        CheckinPreparation.checkin_id == row.id,
                        CheckinPreparation.author_id == actor.id,
                    )
                )
                require_version(preparation.version if preparation else 1, data.expected_version)
                if preparation:
                    preparation.body, preparation.shared = data.body, data.shared
                    preparation.version += 1
                else:
                    preparation = CheckinPreparation(
                        checkin_id=row.id,
                        author_id=actor.id,
                        body=data.body,
                        shared=data.shared,
                        version=1,
                    )
                    self.session.add(preparation)
                self.progress.record(
                    actor,
                    plan,
                    employee,
                    data,
                    identifier,
                    "checkin.prepare",
                    request_id,
                    checkin=row,
                    notify=False,
                    private=not data.shared,
                )
            return self.detail_view(row, actor, employee, cycle, 1)

    def command(
        self,
        context: AuthContext,
        csrf: CsrfCheck,
        identifier: UUID,
        data: CheckinCommand,
        request_id: str,
    ) -> dict[str, Any]:
        with self.session.begin():
            row = self.row(identifier)
            actor, plan, employee, cycle = self.progress.writable(context, csrf, row.plan_id)
            self.session.refresh(row)
            kind = f"checkin.{data.action}"
            if self.progress.receipt(actor, data, identifier, kind):
                return self.detail_view(row, actor, employee, cycle, 1)
            require_version(row.version, data.expected_version)
            if data.action not in self.view(row, actor, employee, cycle)["actions"]:
                fail("checkin_state_conflict", "This check-in step is unavailable")
            self.progress.deadline(cycle, verification=True)
            if (
                data.action in {"publish", "cancel", "clarify", "addendum", "reschedule"}
                and not data.body
            ):
                fail("explanation_required", "Describe the decision or question", 422)
            if data.action in {"acknowledge", "clarify", "addendum"}:
                require_version(row.publication, data.publication)
            if data.action == "reschedule":
                if data.scheduled_at is None:
                    fail("invalid_checkin_schedule", "Select a new schedule", 422)
                assert data.scheduled_at is not None
                self.validate_schedule(cycle, data.scheduled_at)
                previous_schedule = row.scheduled_at.isoformat()
                row.scheduled_at = data.scheduled_at
            else:
                previous_schedule = None
            if data.action == "open":
                row.status = "OPEN"
            elif data.action == "cancel":
                row.status = "CANCELLED"
            elif data.action in {"publish", "addendum"}:
                if data.action == "publish":
                    row.snapshot_id = self.progress.snapshot(plan).id
                row.status = "PUBLISHED"
                row.publication += 1
                row.acknowledged_publication, row.clarification_pending = None, False
                shared = self.session.scalars(
                    select(CheckinPreparation)
                    .where(CheckinPreparation.checkin_id == row.id, CheckinPreparation.shared)
                    .order_by(CheckinPreparation.author_id)
                )
                self.session.add(
                    CheckinPublication(
                        checkin_id=row.id,
                        number=row.publication,
                        author_id=actor.id,
                        body=data.body or "",
                        shared_preparations=[
                            {"author_id": str(p.author_id), "body": p.body} for p in shared
                        ],
                    )
                )
            elif data.action == "acknowledge":
                row.acknowledged_publication = row.publication
            elif data.action == "clarify":
                row.clarification_pending = True
            row.version += 1
            self.progress.record(
                actor,
                plan,
                employee,
                data,
                identifier,
                kind,
                request_id,
                checkin=row,
                body=data.body or "",
                payload={"publication": row.publication, "previous_schedule": previous_schedule},
            )
            return self.detail_view(row, actor, employee, cycle, 1)

    def listing(self, actor: User, plan_id: UUID, page: int) -> dict[str, Any]:
        with self.session.begin():
            _, employee, cycle = self.progress.load(actor, plan_id)
            query = select(Checkin).where(Checkin.plan_id == plan_id)
            total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
            return {
                "items": [
                    self.view(row, actor, employee, cycle)
                    for row in self.session.scalars(
                        query.order_by(Checkin.scheduled_at.desc(), Checkin.id)
                        .offset((page - 1) * 20)
                        .limit(20)
                    )
                ],
                "total": total,
                "page": page,
                "page_size": 20,
            }

    def detail_view(
        self, row: Checkin, actor: User, employee: Employee, cycle: ReviewCycle, page: int
    ) -> dict[str, Any]:
        header = self.view(row, actor, employee, cycle)
        preparations = self.session.scalars(
            select(CheckinPreparation)
            .where(
                CheckinPreparation.checkin_id == row.id,
                or_(CheckinPreparation.author_id == actor.id, CheckinPreparation.shared),
            )
            .order_by(CheckinPreparation.author_id)
        )
        publications = self.session.scalars(
            select(CheckinPublication)
            .where(CheckinPublication.checkin_id == row.id)
            .order_by(CheckinPublication.number.desc())
            .offset((page - 1) * 20)
            .limit(20)
        )
        snapshot = self.session.get(ProgressSnapshot, row.snapshot_id) if row.snapshot_id else None
        query = select(CheckinAction).where(CheckinAction.checkin_id == row.id)
        total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        return {
            **header,
            "preparations": [
                {"author_id": p.author_id, "body": p.body, "shared": p.shared, "version": p.version}
                for p in preparations
            ],
            "publications": [
                {
                    "number": p.number,
                    "body": p.body,
                    "created_at": p.created_at,
                    "preparations": p.shared_preparations,
                }
                for p in publications
            ],
            "snapshot": {
                "id": snapshot.id,
                "version": snapshot.version,
                "known_at": snapshot.data["known_at"],
                "goals": [
                    {k: v for k, v in g.items() if k != "sources"} for g in snapshot.data["goals"]
                ],
            }
            if snapshot
            else None,
            "followups": {
                "items": [
                    {
                        **self.action_view(a, actor),
                        "actions": self.action_view(a, actor)["actions"]
                        if header["actions_open"]
                        else [],
                    }
                    for a in self.session.scalars(
                        query.order_by(CheckinAction.due_at, CheckinAction.id)
                        .offset((page - 1) * 20)
                        .limit(20)
                    )
                ],
                "total": total,
                "page": page,
                "page_size": 20,
            },
            "history": self.progress.history(row.plan_id, checkin_id=row.id, page=page),
        }

    def detail(self, actor: User, identifier: UUID, page: int) -> dict[str, Any]:
        with self.session.begin():
            row = self.row(identifier)
            _, employee, cycle = self.progress.load(actor, row.plan_id)
            return self.detail_view(row, actor, employee, cycle, page)

    @staticmethod
    def action_view(row: CheckinAction, actor: User) -> dict[str, Any]:
        actions = []
        if actor.id == row.owner_id:
            if row.status in {"OPEN", "CHANGES_REQUESTED"}:
                actions.append("start")
            if row.status == "IN_PROGRESS":
                actions.append("submit")
        if actor.id == row.reviewer_id and row.status == "SUBMITTED":
            actions.extend(["complete", "return"])
        return {
            "id": row.id,
            "checkin_id": row.checkin_id,
            "plan_id": row.plan_id,
            "body": row.body,
            "owner_id": row.owner_id,
            "reviewer_id": row.reviewer_id,
            "due_at": row.due_at,
            "version": row.version,
            "status": row.status,
            "actions": actions,
            "replaces_id": row.replaces_id,
            "overdue": row.status not in {"DONE", "CANCELLED"} and row.due_at < datetime.now(UTC),
        }

    def followup(
        self,
        context: AuthContext,
        csrf: CsrfCheck,
        identifier: UUID,
        data: FollowupCreate,
        request_id: str,
    ) -> dict[str, Any]:
        with self.session.begin():
            checkin = self.row(identifier)
            actor, plan, employee, cycle = self.progress.writable(context, csrf, checkin.plan_id)
            self.session.refresh(checkin)
            self.progress.repo.require_manager(employee, actor)
            replay = self.progress.receipt(actor, data, identifier, "action.create")
            if replay:
                replay_row = self.session.get(CheckinAction, UUID(str(replay.payload["target_id"])))
                assert replay_row is not None
                return self.action_view(replay_row, actor)
            require_version(checkin.version, data.expected_version)
            self.progress.deadline(cycle, verification=True)
            if checkin.status != "PUBLISHED":
                fail("checkin_state_conflict", "Publish the check-in before assigning actions")
            if data.owner_id not in {actor.id, employee.user_id}:
                fail(
                    "invalid_action_owner",
                    "Action owners must be a participant in this check-in",
                    422,
                )
            assert cycle.workflow_schedule is not None
            if (
                not datetime.now(UTC)
                < data.due_at
                <= datetime.fromisoformat(str(cycle.workflow_schedule["verification_due_at"]))
            ):
                fail(
                    "invalid_action_deadline",
                    "Select a future deadline within the verification window",
                    422,
                )
            if data.replaces_id:
                replaced = self.session.get(CheckinAction, data.replaces_id)
                if (
                    replaced is None
                    or replaced.checkin_id != checkin.id
                    or replaced.status != "CANCELLED"
                ):
                    fail(
                        "invalid_action_replacement",
                        "Only a cancelled action from this check-in may be replaced",
                        422,
                    )
            row = CheckinAction(
                plan_id=plan.id,
                checkin_id=checkin.id,
                owner_id=data.owner_id,
                reviewer_id=employee.user_id if data.owner_id == actor.id else actor.id,
                body=data.body,
                due_at=data.due_at,
                status="OPEN",
                version=1,
                replaces_id=data.replaces_id,
            )
            self.session.add(row)
            checkin.version += 1
            self.progress.record(
                actor,
                plan,
                employee,
                data,
                identifier,
                "action.create",
                request_id,
                checkin=checkin,
                action=row,
            )
            return self.action_view(row, actor)

    def action_command(
        self,
        context: AuthContext,
        csrf: CsrfCheck,
        identifier: UUID,
        data: FollowupCommand,
        request_id: str,
    ) -> dict[str, Any]:
        with self.session.begin():
            row = self.session.get(CheckinAction, identifier)
            if row is None:
                fail("work_not_found", "Action not found", 404)
            assert row is not None
            actor, plan, employee, cycle = self.progress.writable(context, csrf, row.plan_id)
            self.session.refresh(row)
            checkin = self.row(row.checkin_id)
            kind = f"action.{data.action}"
            if self.progress.receipt(actor, data, identifier, kind):
                return self.action_view(row, actor)
            require_version(row.version, data.expected_version)
            self.progress.deadline(cycle, verification=True)
            permitted = self.action_view(row, actor)["actions"]
            if data.action == "cancel":
                self.progress.repo.require_manager(employee, actor)
                if row.status not in {"DONE", "CANCELLED"}:
                    permitted.append("cancel")
            if data.action not in permitted:
                fail("action_state_conflict", "This action step is unavailable")
            row.status = {
                "start": "IN_PROGRESS",
                "submit": "SUBMITTED",
                "return": "CHANGES_REQUESTED",
                "complete": "DONE",
                "cancel": "CANCELLED",
            }[data.action]
            row.version += 1
            self.progress.record(
                actor,
                plan,
                employee,
                data,
                identifier,
                kind,
                request_id,
                checkin=checkin,
                action=row,
                body=data.body,
            )
            return self.action_view(row, actor)
