import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.domain_writes import CsrfCheck, authorize_domain_write, require_version
from app.core.errors import ApiError
from app.core.policies import AuthContext
from app.modules.audit.service import AuditWriter
from app.modules.employees.models import Employee, EmploymentStatus
from app.modules.kpis.models import KPIDefinition
from app.modules.notifications.delivery import signal
from app.modules.notifications.models import Notification
from app.modules.organization.repository import OrganizationRepository
from app.modules.review_cycles.models import CycleParticipant, CycleStatus, ReviewCycle
from app.modules.users.models import User, UserRole
from app.modules.work_management.models import (
    EvidenceSubmission,
    PlanRevision,
    WorkEvent,
    WorkGoal,
    WorkItem,
    WorkPlan,
)
from app.modules.work_management.repository import WorkRepository, participant_query
from app.modules.work_management.schemas import (
    Command,
    PlanAction,
    PlanDraft,
    WorkAction,
    WorkCreate,
)


class WorkService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = WorkRepository(session)

    def authorize(self, context: AuthContext, csrf: CsrfCheck, identifier: UUID, kind: str) -> User:
        OrganizationRepository(self.session).lock_guard()
        # Discover recipients before locking users, using the established shared lock order.
        from sqlalchemy.orm import aliased

        manager = aliased(Employee)
        query = (
            select(Employee.user_id, manager.user_id)
            .join(CycleParticipant, CycleParticipant.employee_id == Employee.id)
            .outerjoin(manager, Employee.manager_id == manager.id)
        )
        if kind == "participant":
            query = query.where(CycleParticipant.id == identifier)
        else:
            query = query.join(WorkPlan, WorkPlan.participant_id == CycleParticipant.id)
            if kind == "work":
                query = query.join(WorkItem, WorkItem.plan_id == WorkPlan.id).where(
                    WorkItem.id == identifier
                )
            else:
                query = query.where(WorkPlan.id == identifier)
        related = {value for row in self.session.execute(query) for value in row if value}
        return authorize_domain_write(
            self.session, context, csrf, (UserRole.MANAGER, UserRole.EMPLOYEE), related
        )

    @staticmethod
    def digest(body: Command, target: UUID, operation: str) -> str:
        value = {
            "body": body.model_dump(mode="json"),
            "target": str(target),
            "operation": operation,
        }
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    def replay(self, actor: User, body: Command, target: UUID, operation: str) -> WorkEvent | None:
        event = self.session.scalar(
            select(WorkEvent).where(
                WorkEvent.actor_id == actor.id,
                WorkEvent.client_request_id == body.client_request_id,
            )
        )
        if event and event.request_hash != self.digest(body, target, operation):
            raise ApiError(
                409, "request_id_conflict", "Request ID was already used for other content"
            )
        return event

    def record(
        self,
        actor: User,
        plan: WorkPlan,
        employee: Employee,
        body: Command,
        target: UUID,
        kind: str,
        request_id: str,
        *,
        text: str = "",
        work: WorkItem | None = None,
        notify: bool = False,
    ) -> None:
        self.session.flush()
        self.session.add(
            WorkEvent(
                created_at=datetime.now(UTC),
                plan_id=plan.id,
                work_item_id=work.id if work else None,
                actor_id=actor.id,
                client_request_id=body.client_request_id,
                request_hash=self.digest(body, target, kind),
                kind=kind,
                body=text,
                revision=plan.revision,
            )
        )
        audit = AuditWriter().record(
            self.session,
            actor.id,
            f"work.{kind}",
            "work_item" if work else "work_plan",
            str(work.id if work else plan.id),
            request_id,
            {"version": work.version if work else plan.version},
        )
        recipients: set[UUID] = {actor.id}
        manager = self.repo.manager(employee)
        for identifier in (employee.user_id, manager.id if manager else None):
            if identifier:
                recipients.add(identifier)
        if notify:
            for recipient in self.session.scalars(
                select(User).where(
                    User.id.in_(recipients - {actor.id}),
                    User.is_active,
                    User.role.in_([UserRole.MANAGER, UserRole.EMPLOYEE]),
                )
            ):
                self.session.add(
                    Notification(
                        event_id=audit.id,
                        recipient_id=recipient.id,
                        recipient_role=recipient.role.value,
                        kind=f"work.{kind}",
                        work_plan_id=plan.id,
                        work_item_id=work.id if work else None,
                    )
                )
        if work is None:
            # HR coordinates readiness; SSE carries no private work/evidence content.
            recipients.update(
                self.session.scalars(
                    select(User.id).where(User.role == UserRole.HR, User.is_active)
                )
            )
        signal(self.session, recipients)
        self.session.flush()

    def participants(self, user: User, page: int, cycle_id: UUID | None) -> dict[str, Any]:
        with self.session.begin():
            query = participant_query(user)
            if cycle_id:
                query = query.where(ReviewCycle.id == cycle_id)
            total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
            rows = self.session.execute(
                query.order_by(ReviewCycle.created_at.desc(), CycleParticipant.id)
                .offset((page - 1) * 20)
                .limit(20)
            ).all()
            plans = {
                p.participant_id: p
                for p in self.session.scalars(
                    select(WorkPlan).where(WorkPlan.participant_id.in_([p.id for p, _, _ in rows]))
                )
            }
            items = []
            self.repo.prime([employee for _, employee, _ in rows])
            for p, employee, cycle in rows:
                plan = plans.get(p.id)
                manager = self.repo.manager(employee)
                items.append(
                    {
                        "participant_id": p.id,
                        "employee_name": employee.display_name,
                        "cycle_id": cycle.id,
                        "cycle_name": cycle.name,
                        "cycle_status": cycle.status,
                        "plan_id": plan.id if plan else None,
                        "plan_status": plan.status if plan else None,
                        "acknowledged": bool(plan and plan.acknowledged_revision == plan.revision),
                        "can_draft": bool(
                            cycle.status == CycleStatus.DRAFT and manager and manager.id == user.id
                        ),
                        "needs_hr": not self.repo.operational(employee),
                    }
                )
            return {"items": items, "total": total, "page": page, "page_size": 20}

    def plan_view(
        self, plan: WorkPlan, employee: Employee, cycle: ReviewCycle, user: User
    ) -> dict[str, Any]:
        revision = self.session.scalar(
            select(PlanRevision).where(
                PlanRevision.plan_id == plan.id, PlanRevision.number == plan.revision
            )
        )
        assert revision is not None
        goals = list(
            self.session.scalars(
                select(WorkGoal)
                .where(WorkGoal.plan_id == plan.id, WorkGoal.revision == plan.revision)
                .order_by(WorkGoal.id)
            )
        )
        manager = self.repo.manager(employee)
        is_manager = bool(manager and manager.id == user.id and employee.user_id != user.id)
        is_owner = employee.user_id == user.id
        operational = self.repo.operational(employee)
        draft = cycle.status == CycleStatus.DRAFT and operational
        actions = []
        if draft and is_manager:
            if plan.status in {"DRAFT", "CHANGES_REQUESTED"}:
                actions.append("edit")
            if plan.status == "DRAFT":
                actions.append("submit")
            if plan.status == "SUBMITTED":
                actions.append("approve")
        if draft and (is_owner or is_manager) and plan.status in {"SUBMITTED", "APPROVED"}:
            actions.append("clarify")
        if draft and is_owner and plan.status == "APPROVED" and plan.acknowledged_revision is None:
            actions.append("acknowledge")
        if is_owner or is_manager:
            actions.append("comment")
        return {
            "id": plan.id,
            "participant_id": plan.participant_id,
            "version": plan.version,
            "revision": plan.revision,
            "status": plan.status,
            "acknowledged_revision": plan.acknowledged_revision,
            "objective": revision.objective,
            "employee_name": employee.display_name,
            "cycle_id": cycle.id,
            "cycle_name": cycle.name,
            "cycle_status": cycle.status,
            "start_date": cycle.start_date,
            "end_date": cycle.end_date,
            "schedule": cycle.workflow_schedule,
            "goals": [{"id": goal.id, **goal.specification} for goal in goals],
            "actions": actions,
            "can_create_work": bool(
                cycle.status == CycleStatus.ACTIVE
                and (is_owner or is_manager)
                and manager
                and employee.employment_status == EmploymentStatus.ACTIVE
                and operational
            ),
            "is_manager": is_manager,
            "needs_hr": not operational,
        }

    def detail(self, user: User, identifier: UUID) -> dict[str, Any]:
        with self.session.begin():
            plan, _, employee, cycle = self.repo.plan(identifier, user)
            return self.plan_view(plan, employee, cycle, user)

    def revisions(self, user: User, identifier: UUID, page: int) -> dict[str, Any]:
        with self.session.begin():
            plan, _, _, _ = self.repo.plan(identifier, user)
            rows = list(
                self.session.scalars(
                    select(PlanRevision)
                    .where(PlanRevision.plan_id == plan.id)
                    .order_by(PlanRevision.number.desc())
                    .offset((page - 1) * 20)
                    .limit(20)
                )
            )
            goals: dict[int, list[dict[str, object]]] = {}
            for goal in self.session.scalars(
                select(WorkGoal)
                .where(WorkGoal.plan_id == plan.id, WorkGoal.revision.in_([r.number for r in rows]))
                .order_by(WorkGoal.id)
            ):
                goals.setdefault(goal.revision, []).append(goal.specification)
            return {
                "items": [
                    {
                        "number": r.number,
                        "objective": r.objective,
                        "created_at": r.created_at,
                        "goals": goals.get(r.number, []),
                    }
                    for r in rows
                ],
                "total": plan.revision,
                "page": page,
                "page_size": 20,
            }

    def save_plan(
        self,
        context: AuthContext,
        csrf: CsrfCheck,
        participant_id: UUID,
        data: PlanDraft,
        request_id: str,
    ) -> dict[str, Any]:
        with self.session.begin():
            actor = self.authorize(context, csrf, participant_id, "participant")
            _, employee, cycle = self.repo.participant(participant_id, actor, lock=True)
            self.repo.require_manager(employee, actor)
            plan = self.session.scalar(
                select(WorkPlan).where(WorkPlan.participant_id == participant_id).with_for_update()
            )
            replay = self.replay(actor, data, participant_id, "plan_saved")
            if replay and plan:
                return self.plan_view(plan, employee, cycle, actor)
            if cycle.status != CycleStatus.DRAFT:
                raise ApiError(
                    409, "baseline_frozen", "Baseline changes await a formal change process"
                )
            if plan:
                require_version(plan.version, data.expected_version)
                if plan.status not in {"DRAFT", "CHANGES_REQUESTED"}:
                    raise ApiError(
                        409, "plan_state_conflict", "Request clarification before revising"
                    )
                plan.revision += 1
                plan.version += 1
            else:
                require_version(1, data.expected_version)
                plan = WorkPlan(participant_id=participant_id)
                self.session.add(plan)
                self.session.flush()
            plan.status, plan.acknowledged_revision, plan.approved_by = "DRAFT", None, None
            self.session.add(
                PlanRevision(
                    created_at=datetime.now(UTC),
                    plan_id=plan.id,
                    number=plan.revision,
                    author_id=actor.id,
                    objective=data.objective,
                )
            )
            self.session.flush()
            for goal in data.goals:
                definition = self.session.get(KPIDefinition, goal.definition_id)
                if definition is None or not definition.is_active:
                    raise ApiError(
                        409, "kpi_definition_inactive", "Choose an active KPI definition"
                    )
                specification = goal.model_dump(mode="json")
                specification["definition"] = {
                    "description": definition.description,
                    "code": definition.code,
                    "name": definition.name,
                    "unit": definition.unit,
                    "direction": definition.direction,
                    "version": definition.version,
                }
                self.session.add(
                    WorkGoal(
                        plan_id=plan.id,
                        revision=plan.revision,
                        definition_id=definition.id,
                        specification=specification,
                    )
                )
            self.record(actor, plan, employee, data, participant_id, "plan_saved", request_id)
            return self.plan_view(plan, employee, cycle, actor)

    def plan_action(
        self,
        context: AuthContext,
        csrf: CsrfCheck,
        identifier: UUID,
        data: PlanAction,
        request_id: str,
    ) -> dict[str, Any]:
        with self.session.begin():
            actor = self.authorize(context, csrf, identifier, "plan")
            plan, _, employee, cycle = self.repo.plan(identifier, actor, lock=True, hr=False)
            kind = f"plan_{data.action}"
            if self.replay(actor, data, identifier, kind):
                return self.plan_view(plan, employee, cycle, actor)
            require_version(plan.version, data.expected_version)
            require_version(plan.revision, data.revision)
            permitted = self.plan_view(plan, employee, cycle, actor)["actions"]
            if data.action not in permitted:
                raise ApiError(409, "plan_state_conflict", "This plan step is unavailable")
            if data.action in {"clarify", "comment"} and not data.body:
                raise ApiError(422, "explanation_required", "Describe your question or proposal")
            if data.action == "submit":
                plan.status = "SUBMITTED"
            elif data.action == "approve":
                self.repo.require_manager(employee, actor)
                plan.status, plan.approved_by = "APPROVED", actor.id
            elif data.action == "clarify":
                plan.status, plan.acknowledged_revision, plan.approved_by = (
                    "CHANGES_REQUESTED",
                    None,
                    None,
                )
            elif data.action == "acknowledge":
                plan.acknowledged_revision = plan.revision
            plan.version += 1
            self.record(
                actor,
                plan,
                employee,
                data,
                identifier,
                kind,
                request_id,
                text=data.body or "",
                notify=True,
            )
            return self.plan_view(plan, employee, cycle, actor)

    def work_view(
        self, work: WorkItem, employee: Employee, cycle: ReviewCycle, user: User
    ) -> dict[str, Any]:
        manager = self.repo.manager(employee)
        owner = employee.user_id == user.id
        reviewer = bool(manager and manager.id == user.id and user.id == work.reviewer_id)
        operational = self.repo.operational(employee)
        actions = []
        if (
            cycle.status == CycleStatus.ACTIVE
            and manager
            and (employee.employment_status == EmploymentStatus.ACTIVE)
            and operational
        ):
            if owner and work.status in {"TODO", "IN_PROGRESS", "CHANGES_REQUESTED"}:
                actions += ["update", "unblock" if work.blocked else "block"]
                if work.status != "IN_PROGRESS":
                    actions.append("start")
                if work.status == "IN_PROGRESS" and not work.blocked:
                    actions.append("submit")
            if owner and work.status == "PROPOSED":
                actions.append("edit_proposal")
            if reviewer:
                if work.status == "PROPOSED":
                    actions.append("publish")
                if work.status == "SUBMITTED":
                    actions += ["accept", "return"]
                if work.status == "ACCEPTED":
                    actions.append("reopen")
                elif work.status != "CANCELLED":
                    actions.append("cancel")
            if (owner or reviewer) and work.status != "CANCELLED":
                actions += ["comment", "request_change"]
        return {
            "id": work.id,
            "plan_id": work.plan_id,
            "version": work.version,
            "title": work.title,
            "acceptance": work.acceptance,
            "priority": work.priority,
            "source_key": work.source_key,
            "due_at": work.due_at,
            "status": work.status,
            "goal_id": work.goal_id,
            "blocked": work.blocked,
            "blocked_reason": work.blocked_reason,
            "employee_name": employee.display_name,
            "cycle_name": cycle.name,
            "actions": actions,
            "needs_hr": not operational,
            "next_actor": "Quản lý hỗ trợ"
            if work.blocked
            else "Quản lý"
            if work.status in {"PROPOSED", "SUBMITTED"}
            else "Hoàn tất"
            if work.status in {"ACCEPTED", "CANCELLED"}
            else "Nhân viên",
        }

    def work_list(
        self, user: User, page: int, plan_id: UUID | None, status: str | None, blocked: bool | None
    ) -> dict[str, Any]:
        with self.session.begin():
            base = participant_query(user, hr=False).subquery()
            query = (
                select(WorkItem, Employee, ReviewCycle)
                .join(WorkPlan)
                .join(CycleParticipant)
                .join(Employee)
                .join(ReviewCycle)
                .where(CycleParticipant.id.in_(select(base.c.id)))
            )
            if plan_id:
                query = query.where(WorkItem.plan_id == plan_id)
            if status:
                query = query.where(WorkItem.status == status)
            if blocked is not None:
                query = query.where(WorkItem.blocked == blocked)
            total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
            rows = self.session.execute(
                query.order_by(WorkItem.created_at.desc(), WorkItem.id)
                .offset((page - 1) * 20)
                .limit(20)
            ).all()
            self.repo.prime([employee for _, employee, _ in rows])
            return {
                "items": [self.work_view(w, e, c, user) for w, e, c in rows],
                "total": total,
                "page": page,
                "page_size": 20,
            }

    def load_work(
        self, user: User, identifier: UUID, *, lock: bool = False
    ) -> tuple[WorkItem, WorkPlan, Employee, ReviewCycle]:
        work = self.session.get(WorkItem, identifier)
        if work is None:
            raise ApiError(404, "work_not_found", "Work record not found")
        plan, _, employee, cycle = self.repo.plan(work.plan_id, user, lock=lock, hr=False)
        if lock:
            self.session.refresh(work, with_for_update=True)
        return work, plan, employee, cycle

    def work_detail(self, user: User, identifier: UUID, page: int = 1) -> dict[str, Any]:
        with self.session.begin():
            work, _, employee, cycle = self.load_work(user, identifier)
            result = self.work_view(work, employee, cycle, user)
            query = select(EvidenceSubmission).where(EvidenceSubmission.work_item_id == work.id)
            result["submissions"] = [
                {
                    "id": row.id,
                    "number": row.number,
                    "body": row.body,
                    "url": row.url,
                    "created_at": row.created_at,
                }
                for row in self.session.scalars(
                    query.order_by(EvidenceSubmission.number.desc())
                    .offset((page - 1) * 20)
                    .limit(20)
                )
            ]
            result["submission_total"] = (
                self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
            )
            return result

    def create_work(
        self,
        context: AuthContext,
        csrf: CsrfCheck,
        identifier: UUID,
        data: WorkCreate,
        request_id: str,
    ) -> dict[str, Any]:
        with self.session.begin():
            actor = self.authorize(context, csrf, identifier, "plan")
            plan, _, employee, cycle = self.repo.plan(identifier, actor, lock=True, hr=False)
            replay = self.replay(actor, data, identifier, "created")
            if replay:
                assert replay.work_item_id is not None
                work = self.session.get(WorkItem, replay.work_item_id)
                assert work is not None
                return self.work_view(work, employee, cycle, actor)
            require_version(plan.version, data.expected_version)
            manager = self.repo.manager(employee)
            if (
                cycle.status != CycleStatus.ACTIVE
                or plan.status != "APPROVED"
                or not manager
                or plan.acknowledged_revision != plan.revision
                or employee.employment_status != EmploymentStatus.ACTIVE
                or not self.repo.operational(employee)
            ):
                raise ApiError(409, "work_not_ready", "Work requires an active, acknowledged plan")
            if actor.id not in {manager.id, employee.user_id}:
                raise ApiError(
                    403, "forbidden", "Only the owner or direct manager can propose work"
                )
            assert cycle.workflow_schedule is not None
            now = datetime.now(UTC)
            local_due = data.due_at.astimezone(ZoneInfo(str(cycle.workflow_schedule["timezone"])))
            if not cycle.start_date <= local_due.date() <= cycle.end_date or data.due_at < now:
                raise ApiError(
                    422, "invalid_work_deadline", "Deadline must be future and inside the cycle"
                )
            if data.goal_id:
                goal = self.session.get(WorkGoal, data.goal_id)
                if not goal or goal.plan_id != plan.id or goal.revision != plan.revision:
                    raise ApiError(
                        422, "invalid_goal", "Goal must belong to the approved plan revision"
                    )
            if self.session.scalar(
                select(WorkItem.id).where(
                    WorkItem.plan_id == plan.id, WorkItem.source_key == data.source_key
                )
            ):
                raise ApiError(409, "duplicate_work_source", "This source already has a work item")
            work = WorkItem(
                plan_id=plan.id,
                plan_revision=plan.revision,
                reviewer_id=manager.id,
                status="TODO" if actor.id == manager.id else "PROPOSED",
                **data.model_dump(exclude={"client_request_id", "expected_version"}),
            )
            self.session.add(work)
            self.session.flush()
            self.record(
                actor,
                plan,
                employee,
                data,
                identifier,
                "created",
                request_id,
                work=work,
                notify=True,
            )
            return self.work_view(work, employee, cycle, actor)

    def action(
        self,
        context: AuthContext,
        csrf: CsrfCheck,
        identifier: UUID,
        data: WorkAction,
        request_id: str,
    ) -> dict[str, Any]:
        with self.session.begin():
            actor = self.authorize(context, csrf, identifier, "work")
            work, plan, employee, cycle = self.load_work(actor, identifier, lock=True)
            if self.replay(actor, data, identifier, data.action):
                return self.work_view(work, employee, cycle, actor)
            require_version(work.version, data.expected_version)
            if data.action not in self.work_view(work, employee, cycle, actor)["actions"]:
                raise ApiError(409, "work_state_conflict", "This work step is unavailable")
            schedule = cycle.workflow_schedule
            assert schedule is not None
            cutoff = (
                "verification_due_at" if data.action in {"accept", "return"} else "input_cutoff_at"
            )
            if data.action not in {"comment", "request_change", "cancel"} and datetime.now(UTC) > (
                datetime.fromisoformat(str(schedule[cutoff]))
            ):
                raise ApiError(409, "workflow_cutoff", "The deadline for this step has passed")
            transitions = {
                "publish": "TODO",
                "start": "IN_PROGRESS",
                "submit": "SUBMITTED",
                "return": "CHANGES_REQUESTED",
                "accept": "ACCEPTED",
                "cancel": "CANCELLED",
                "reopen": "CHANGES_REQUESTED",
            }
            if data.action == "submit":
                number = (
                    self.session.scalar(
                        select(func.count())
                        .select_from(EvidenceSubmission)
                        .where(EvidenceSubmission.work_item_id == work.id)
                    )
                    or 0
                )
                self.session.add(
                    EvidenceSubmission(
                        created_at=datetime.now(UTC),
                        work_item_id=work.id,
                        number=number + 1,
                        author_id=actor.id,
                        body=data.body or "",
                        url=str(data.url) if data.url else None,
                    )
                )
            if data.action in transitions:
                work.status = transitions[data.action]
            if data.action == "block":
                work.blocked, work.blocked_reason = True, data.body or ""
            elif data.action == "unblock" or data.action in {"cancel", "reopen"}:
                work.blocked, work.blocked_reason = False, ""
            work.version += 1
            self.record(
                actor,
                plan,
                employee,
                data,
                identifier,
                data.action,
                request_id,
                text=data.body or "",
                work=work,
                notify=data.action
                in {
                    "publish",
                    "block",
                    "submit",
                    "return",
                    "accept",
                    "cancel",
                    "reopen",
                    "comment",
                    "request_change",
                },
            )
            return self.work_view(work, employee, cycle, actor)

    def edit_proposal(
        self,
        context: AuthContext,
        csrf: CsrfCheck,
        identifier: UUID,
        data: WorkCreate,
        request_id: str,
    ) -> dict[str, Any]:
        with self.session.begin():
            actor = self.authorize(context, csrf, identifier, "work")
            work, plan, employee, cycle = self.load_work(actor, identifier, lock=True)
            if self.replay(actor, data, identifier, "update"):
                return self.work_view(work, employee, cycle, actor)
            require_version(work.version, data.expected_version)
            if "edit_proposal" not in self.work_view(work, employee, cycle, actor)["actions"]:
                raise ApiError(
                    409, "work_state_conflict", "Only an unpublished own proposal is editable"
                )
            assert cycle.workflow_schedule is not None
            zone = ZoneInfo(str(cycle.workflow_schedule["timezone"]))
            if not cycle.start_date <= data.due_at.astimezone(zone).date() <= cycle.end_date or (
                data.due_at <= datetime.now(UTC)
            ):
                raise ApiError(
                    422, "invalid_work_deadline", "Use a future deadline within this cycle"
                )
            if data.goal_id:
                goal = self.session.get(WorkGoal, data.goal_id)
                if not goal or goal.plan_id != plan.id or goal.revision != work.plan_revision:
                    raise ApiError(422, "invalid_goal", "Choose a goal in the approved plan")
            if self.session.scalar(
                select(WorkItem.id).where(
                    WorkItem.plan_id == plan.id,
                    WorkItem.source_key == data.source_key,
                    WorkItem.id != work.id,
                )
            ):
                raise ApiError(409, "duplicate_work_source", "This source already has a work item")
            for key, value in data.model_dump(
                exclude={"client_request_id", "expected_version"}
            ).items():
                setattr(work, key, value)
            work.version += 1
            self.record(
                actor,
                plan,
                employee,
                data,
                identifier,
                "update",
                request_id,
                work=work,
                text="Chỉnh sửa đề xuất trước khi quản lý giao việc.",
            )
            return self.work_view(work, employee, cycle, actor)

    def history(
        self, user: User, identifier: UUID, work_id: UUID | None, page: int
    ) -> dict[str, Any]:
        with self.session.begin():
            self.repo.plan(identifier, user, hr=work_id is None)
            query = (
                select(WorkEvent, User.email)
                .join(User, WorkEvent.actor_id == User.id)
                .where(WorkEvent.plan_id == identifier)
            )
            query = query.where(
                WorkEvent.work_item_id == work_id if work_id else WorkEvent.work_item_id.is_(None)
            )
            total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
            rows = self.session.execute(
                query.order_by(WorkEvent.created_at.desc(), WorkEvent.id.desc())
                .offset((page - 1) * 20)
                .limit(20)
            ).all()
            return {
                "items": [
                    {
                        "id": e.id,
                        "kind": e.kind,
                        "body": e.body,
                        "actor": name,
                        "revision": e.revision,
                        "created_at": e.created_at,
                    }
                    for e, name in rows
                ],
                "total": total,
                "page": page,
                "page_size": 20,
            }
