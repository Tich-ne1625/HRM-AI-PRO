from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.orm import Session

from app.core.domain_writes import CsrfCheck, require_version
from app.core.errors import ApiError
from app.core.policies import AuthContext
from app.modules.audit.service import AuditWriter
from app.modules.employees.models import Employee
from app.modules.notifications.delivery import signal
from app.modules.notifications.models import Notification
from app.modules.progress.aggregation import (
    ALGORITHM,
    aggregate,
    canonical_source,
    digest,
    validate_rule,
)
from app.modules.progress.models import (
    Checkin,
    CheckinAction,
    Measurement,
    MeasurementRevision,
    MetricRule,
    ProgressEvent,
    ProgressSnapshot,
)
from app.modules.progress.schemas import MeasurementCommand, MeasurementDraft
from app.modules.review_cycles.models import CycleParticipant, CycleStatus, ReviewCycle
from app.modules.users.models import User, UserRole
from app.modules.work_management.models import (
    EvidenceSubmission,
    WorkEvent,
    WorkGoal,
    WorkItem,
    WorkPlan,
)
from app.modules.work_management.repository import WorkRepository
from app.modules.work_management.schemas import Command
from app.modules.work_management.service import WorkService


def fail(code: str, message: str, status: int = 409) -> None:
    raise ApiError(status, code, message)


class ProgressService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.work = WorkService(session)
        self.repo = WorkRepository(session)
        self._revisions: dict[tuple[UUID, int], MeasurementRevision] = {}
        self._rules: dict[UUID, MetricRule] = {}

    def load(
        self, user: User, identifier: UUID, *, lock: bool = False
    ) -> tuple[WorkPlan, Employee, ReviewCycle]:
        plan, _, employee, cycle = self.repo.plan(identifier, user, lock=lock, hr=False)
        self.repo.prime([employee])
        return plan, employee, cycle

    def writable(
        self, context: AuthContext, csrf: CsrfCheck, identifier: UUID
    ) -> tuple[User, WorkPlan, Employee, ReviewCycle]:
        actor = self.work.authorize(context, csrf, identifier, "plan")
        plan, employee, cycle = self.load(actor, identifier, lock=True)
        if (
            cycle.status != CycleStatus.ACTIVE
            or plan.status != "APPROVED"
            or plan.acknowledged_revision != plan.revision
        ):
            fail("work_not_ready", "An active, approved and acknowledged plan is required")
        if not self.repo.operational(employee):
            fail("work_accounts_required", "HR must check the active work accounts")
        return actor, plan, employee, cycle

    @staticmethod
    def deadline(cycle: ReviewCycle, *, verification: bool = False) -> None:
        assert cycle.workflow_schedule
        key = "verification_due_at" if verification else "input_cutoff_at"
        if datetime.now(UTC) > datetime.fromisoformat(str(cycle.workflow_schedule[key])):
            fail("workflow_cutoff", "The deadline for this step has passed")

    def owner(self, actor: User, employee: Employee) -> None:
        if employee.user_id != actor.id:
            fail("forbidden", "Only the employee may submit their measurements", 403)

    def receipt(self, actor: User, data: Command, target: UUID, kind: str) -> ProgressEvent | None:
        row = self.session.scalar(
            select(ProgressEvent).where(
                ProgressEvent.actor_id == actor.id,
                ProgressEvent.client_request_id == data.client_request_id,
            )
        )
        if row and row.request_hash != self.work.digest(data, target, kind):
            fail("request_id_conflict", "Request ID was used for other content")
        return row

    def record(
        self,
        actor: User,
        plan: WorkPlan,
        employee: Employee,
        data: Command,
        target: UUID,
        kind: str,
        request_id: str,
        *,
        measurement: Measurement | None = None,
        checkin: Checkin | None = None,
        action: CheckinAction | None = None,
        body: str = "",
        payload: dict[str, Any] | None = None,
        notify: bool = True,
        private: bool = False,
    ) -> None:
        self.session.flush()
        entity = measurement or action or checkin
        values = dict(payload or {})
        values["target_id"] = str(entity.id if entity else target)
        values["private"] = private
        event = ProgressEvent(
            plan_id=plan.id,
            actor_id=actor.id,
            client_request_id=data.client_request_id,
            request_hash=self.work.digest(data, target, kind),
            kind=kind,
            body=body,
            payload=values,
            measurement_id=measurement.id if measurement else None,
            checkin_id=checkin.id if checkin else None,
            action_id=action.id if action else None,
            created_at=datetime.now(UTC),
        )
        self.session.add(event)
        audit = AuditWriter().record(
            self.session,
            actor.id,
            f"progress.{kind}",
            "progress",
            str(entity.id if entity else target),
            request_id,
            {"version": entity.version if entity else plan.measurement_version},
        )
        manager = self.repo.manager(employee)
        recipients = {u for u in (employee.user_id, manager.id if manager else None) if u}
        if notify and not private:
            for recipient in self.session.scalars(
                select(User).where(User.id.in_(recipients - {actor.id}), User.is_active)
            ):
                self.session.add(
                    Notification(
                        event_id=audit.id,
                        recipient_id=recipient.id,
                        recipient_role=recipient.role.value,
                        kind=f"progress.{kind}",
                        work_plan_id=plan.id,
                        measurement_id=measurement.id if measurement else None,
                        checkin_id=checkin.id if checkin else None,
                        checkin_action_id=action.id if action else None,
                    )
                )
        if not private:
            recipients.update(
                self.session.scalars(
                    select(User.id).where(User.role == UserRole.HR, User.is_active)
                )
            )
        signal(self.session, {actor.id} if private else recipients)
        self.session.flush()

    def goal(self, identifier: UUID) -> WorkGoal:
        goal = self.session.get(WorkGoal, identifier)
        if goal is None:
            fail("work_not_found", "Goal not found", 404)
        assert goal is not None
        return goal

    def rule(self, goal: WorkGoal, plan: WorkPlan) -> MetricRule:
        if goal.plan_id != plan.id or goal.revision != plan.revision:
            fail("invalid_goal", "Choose a goal of the approved plan", 422)
        try:
            validate_rule(goal.specification)
        except ValueError as exc:
            raise ApiError(409, "measurement_rule_incompatible", str(exc)) from exc
        rule = self.session.scalar(select(MetricRule).where(MetricRule.goal_id == goal.id))
        if rule is None:
            rule = MetricRule(
                goal_id=goal.id,
                plan_id=plan.id,
                plan_revision=plan.revision,
                algorithm=ALGORITHM,
                specification=goal.specification,
            )
            self.session.add(rule)
            self.session.flush()
        return rule

    def revision(self, row: Measurement, number: int | None = None) -> MeasurementRevision:
        key = (row.id, number or row.number)
        if key in self._revisions:
            return self._revisions[key]
        revision = self.session.scalar(
            select(MeasurementRevision).where(
                MeasurementRevision.measurement_id == row.id,
                MeasurementRevision.number == (number or row.number),
            )
        )
        assert revision is not None
        self._revisions[key] = revision
        return revision

    def source_work(self, row: Measurement, *, accepted: bool) -> dict[str, Any]:
        if row.work_item_id is None:
            return {}
        work = self.session.scalar(
            select(WorkItem).where(WorkItem.id == row.work_item_id).with_for_update()
        )
        if work is None or work.plan_id != row.plan_id:
            fail("invalid_source", "Work source does not belong to this plan", 422)
        assert work is not None
        if accepted and work.status != "ACCEPTED":
            fail(
                "source_not_accepted",
                "Work must be accepted before submitting or verifying a measurement",
            )
        if work.status != "ACCEPTED":
            return {}
        event = self.session.scalar(
            select(WorkEvent)
            .where(WorkEvent.work_item_id == work.id, WorkEvent.kind == "accept")
            .order_by(WorkEvent.created_at.desc(), WorkEvent.id.desc())
            .limit(1)
        )
        submission = self.session.scalar(
            select(EvidenceSubmission)
            .where(EvidenceSubmission.work_item_id == work.id)
            .order_by(EvidenceSubmission.number.desc())
            .limit(1)
        )
        assert event is not None and submission is not None
        return {
            "accept_event_id": str(event.id),
            "submission_id": str(submission.id),
            "work_version": work.version,
        }

    def payload(self, data: MeasurementDraft, spec: dict[str, Any]) -> dict[str, Any]:
        method = spec["method"]
        if data.kind == "VALUE":
            if method in {"SUM", "LAST"}:
                valid = (
                    data.value is not None
                    and data.numerator is None
                    and data.denominator is None
                    and data.milestone is None
                )
            elif method == "RATIO":
                valid = (
                    data.value is None
                    and data.numerator is not None
                    and data.denominator is not None
                    and data.numerator <= data.denominator
                    and data.milestone is None
                )
            else:
                valid = (
                    data.value is None
                    and data.numerator is None
                    and data.denominator is None
                    and data.milestone is not None
                    and data.milestone < len(spec["milestones"])
                )
            if not valid:
                fail(
                    "invalid_measurement",
                    "The numeric fields must match the measurement method",
                    422,
                )
        return {
            k: (str(v) if v is not None else None)
            for k, v in {
                "value": data.value,
                "numerator": data.numerator,
                "denominator": data.denominator,
                "body": data.body,
                "url": data.url,
            }.items()
        }

    def _row(self, identifier: UUID) -> Measurement:
        row = self.session.get(Measurement, identifier)
        if row is None:
            fail("work_not_found", "Measurement not found", 404)
        assert row is not None
        return row

    def view(
        self, row: Measurement, actor: User, employee: Employee, cycle: ReviewCycle
    ) -> dict[str, Any]:
        revision = self.revision(row)
        effective = self.revision(row, row.effective_number) if row.effective_number else None
        rule = self._rules.get(row.rule_id) or self.session.get(MetricRule, row.rule_id)
        assert rule is not None
        operational = self.repo.operational(employee) and cycle.status == CycleStatus.ACTIVE
        actions = []
        if operational:
            assert cycle.workflow_schedule is not None
            can_input = datetime.now(UTC) <= datetime.fromisoformat(
                str(cycle.workflow_schedule["input_cutoff_at"])
            )
            can_verify = datetime.now(UTC) <= datetime.fromisoformat(
                str(cycle.workflow_schedule["verification_due_at"])
            )
            if can_input and actor.id == employee.user_id and row.status != "SUBMITTED":
                actions.append("draft")
            if can_input and actor.id == employee.user_id and row.status == "DRAFT":
                actions.append("submit")
            manager = self.repo.manager(employee)
            if can_verify and manager and actor.id == manager.id and row.status == "SUBMITTED":
                actions.extend(["verify", "return", "reject"])
        return {
            "id": row.id,
            "plan_id": row.plan_id,
            "goal_id": rule.goal_id,
            "version": row.version,
            "number": row.number,
            "status": row.status,
            "source_key": row.source_label,
            "source_kind": row.source_kind,
            "work_item_id": row.work_item_id,
            "occurred_at": row.occurred_at,
            "milestone": row.milestone,
            "suspended": row.suspended,
            "input_closed": datetime.now(UTC)
            > datetime.fromisoformat(str(cycle.workflow_schedule["input_cutoff_at"])),  # type: ignore[index]
            "next_actor": "Nhân viên bổ sung công việc và nộp lại số"
            if row.suspended
            else "Quản lý xác minh"
            if row.status == "SUBMITTED"
            else "Nhân viên bổ sung / nộp số"
            if row.status in {"DRAFT", "RETURNED"}
            else "Không có bước chờ",
            "kind": revision.kind,
            "payload": revision.payload,
            "effective": {
                "number": effective.number,
                "kind": effective.kind,
                "payload": effective.payload,
            }
            if effective
            else None,
            "method": rule.specification["method"],
            "actions": actions,
            "is_correction": row.effective_number is not None
            and row.number != row.effective_number,
            "needs_hr": not self.repo.operational(employee),
        }

    def save(
        self,
        context: AuthContext,
        csrf: CsrfCheck,
        goal_id: UUID,
        data: MeasurementDraft,
        request_id: str,
        identifier: UUID | None = None,
    ) -> dict[str, Any]:
        with self.session.begin():
            goal = self.goal(goal_id)
            actor, plan, employee, cycle = self.writable(context, csrf, goal.plan_id)
            self.owner(actor, employee)
            target = identifier or goal_id
            kind = "measurement.draft" if identifier else "measurement.create"
            replay = self.receipt(actor, data, target, kind)
            if replay:
                return self.view(
                    self._row(UUID(str(replay.payload["target_id"]))), actor, employee, cycle
                )
            self.deadline(cycle)
            rule = self.rule(goal, plan)
            try:
                key = canonical_source(data.source_key)
            except ValueError as exc:
                raise ApiError(422, "invalid_source", str(exc)) from exc
            zone = ZoneInfo(str(cycle.workflow_schedule["timezone"]))  # type: ignore[index]
            occurred = data.occurred_at.astimezone(UTC)
            if not (
                datetime.combine(cycle.start_date, time.min, zone)
                <= occurred
                < datetime.combine(cycle.end_date + timedelta(days=1), time.min, zone)
            ) or occurred > datetime.now(UTC):
                fail(
                    "invalid_measurement_time", "The event must have occurred within the cycle", 422
                )
            values = self.payload(data, rule.specification)
            if identifier:
                row = self._row(identifier)
                if row.plan_id != plan.id or row.rule_id != rule.id:
                    fail("work_not_found", "Measurement not found", 404)
                require_version(row.version, data.expected_version)
                if row.status == "SUBMITTED":
                    fail("measurement_pending", "A submitted revision cannot be edited")
                if (key, data.source_kind, data.work_item_id, occurred, data.milestone) != (
                    row.source_key,
                    row.source_kind,
                    row.work_item_id,
                    row.occurred_at,
                    row.milestone,
                ):
                    fail(
                        "measurement_source_frozen",
                        "Submit a void request before replacing an incorrect source",
                    )
                row.number += 1
                row.version += 1
                row.status = "DRAFT"
            else:
                require_version(plan.version, data.expected_version)
                if data.kind == "VOID":
                    fail(
                        "invalid_measurement", "Only an existing verified source can be voided", 422
                    )
                duplicate = self.session.scalar(
                    select(Measurement.id).where(
                        Measurement.rule_id == rule.id,
                        (Measurement.source_key == key)
                        | (
                            and_(~Measurement.retired, Measurement.milestone == data.milestone)
                            if data.milestone is not None
                            else False
                        )
                        | (
                            and_(~Measurement.retired, Measurement.snapshot_at == occurred)
                            if rule.specification["method"] == "LAST"
                            else False
                        ),
                    )
                )
                if duplicate:
                    fail(
                        "duplicate_measurement_source",
                        "This source, snapshot or milestone already has a measurement",
                    )
                row = Measurement(
                    plan_id=plan.id,
                    rule_id=rule.id,
                    source_key=key,
                    source_label=data.source_key.strip(),
                    source_kind=data.source_kind,
                    work_item_id=data.work_item_id,
                    occurred_at=occurred,
                    snapshot_at=occurred if rule.specification["method"] == "LAST" else None,
                    milestone=data.milestone,
                    version=1,
                    number=1,
                    status="DRAFT",
                )
                self.session.add(row)
                self.session.flush()
            if data.kind == "VOID" and row.effective_number is None:
                fail("invalid_measurement", "Only a verified source can be voided", 422)
            if row.work_item_id:
                work = self.session.get(WorkItem, row.work_item_id)
                if (
                    work is None
                    or work.plan_id != plan.id
                    or work.goal_id != goal.id
                    or canonical_source(work.source_key) != key
                ):
                    fail(
                        "invalid_source",
                        "Choose an accepted work item of this goal and its original source key",
                        422,
                    )
                values.update(self.source_work(row, accepted=False))
            self.session.add(
                MeasurementRevision(
                    measurement_id=row.id,
                    number=row.number,
                    kind=data.kind,
                    author_id=actor.id,
                    payload=values,
                )
            )
            self.record(
                actor,
                plan,
                employee,
                data,
                target,
                kind,
                request_id,
                measurement=row,
                payload={"number": row.number},
                notify=False,
            )
            return self.view(row, actor, employee, cycle)

    def command(
        self,
        context: AuthContext,
        csrf: CsrfCheck,
        identifier: UUID,
        data: MeasurementCommand,
        request_id: str,
    ) -> dict[str, Any]:
        with self.session.begin():
            row = self._row(identifier)
            actor, plan, employee, cycle = self.writable(context, csrf, row.plan_id)
            # The shared plan lock serializes all mutations, including work reopening.
            self.session.refresh(row)
            kind = f"measurement.{data.action}"
            if self.receipt(actor, data, identifier, kind):
                return self.view(row, actor, employee, cycle)
            require_version(row.version, data.expected_version)
            self.deadline(cycle, verification=data.action != "submit")
            if data.action not in self.view(row, actor, employee, cycle)["actions"]:
                fail("measurement_state_conflict", "This measurement step is unavailable")
            revision = self.revision(row)
            if data.action in {"submit", "verify"} and revision.kind != "VOID":
                refs = self.source_work(row, accepted=True)
                if refs and data.action == "submit" and not revision.payload.get("accept_event_id"):
                    row.number += 1
                    revision = MeasurementRevision(
                        measurement_id=row.id,
                        number=row.number,
                        author_id=actor.id,
                        kind=revision.kind,
                        payload={**revision.payload, **refs},
                    )
                    self.session.add(revision)
                elif refs and refs.get("accept_event_id") != revision.payload.get(
                    "accept_event_id"
                ):
                    fail(
                        "source_revision_changed",
                        "Save a new revision for the current work acceptance",
                    )
            row.status = {
                "submit": "SUBMITTED",
                "verify": "VERIFIED",
                "return": "RETURNED",
                "reject": "REJECTED",
            }[data.action]
            row.version += 1
            snapshot = None
            if data.action == "verify":
                self.repo.require_manager(employee, actor)
                if revision.kind == "VALUE" and row.retired:
                    occupied = self.session.scalar(
                        select(Measurement.id).where(
                            Measurement.rule_id == row.rule_id,
                            Measurement.id != row.id,
                            ~Measurement.retired,
                            or_(
                                Measurement.milestone == row.milestone
                                if row.milestone is not None
                                else false(),
                                Measurement.snapshot_at == row.snapshot_at
                                if row.snapshot_at is not None
                                else false(),
                            ),
                        )
                    )
                    if occupied:
                        fail(
                            "duplicate_measurement_source",
                            "A replacement already occupies this milestone or snapshot",
                        )
                row.retired = revision.kind == "VOID"
                row.effective_number, row.suspended = row.number, False
                snapshot = self.snapshot(plan, changed=True)
            self.record(
                actor,
                plan,
                employee,
                data,
                identifier,
                kind,
                request_id,
                measurement=row,
                body=data.body or "",
                payload={
                    "number": row.number,
                    "snapshot_id": str(snapshot.id) if snapshot else None,
                },
            )
            return self.view(row, actor, employee, cycle)

    def snapshot_data(self, plan: WorkPlan) -> dict[str, Any]:
        cycle = self.session.scalar(
            select(ReviewCycle)
            .join(CycleParticipant)
            .where(CycleParticipant.id == plan.participant_id)
        )
        assert cycle is not None and cycle.workflow_schedule is not None
        rules = {
            r.goal_id: str(r.id)
            for r in self.session.scalars(select(MetricRule).where(MetricRule.plan_id == plan.id))
        }
        goals = list(
            self.session.scalars(
                select(WorkGoal)
                .where(WorkGoal.plan_id == plan.id, WorkGoal.revision == plan.revision)
                .order_by(WorkGoal.id)
            )
        )
        sources: dict[UUID, list[dict[str, Any]]] = {}
        for row, revision, rule in self.session.execute(
            select(Measurement, MeasurementRevision, MetricRule)
            .join(
                MeasurementRevision,
                and_(
                    MeasurementRevision.measurement_id == Measurement.id,
                    MeasurementRevision.number == Measurement.effective_number,
                ),
            )
            .join(MetricRule, Measurement.rule_id == MetricRule.id)
            .where(
                Measurement.plan_id == plan.id,
                ~Measurement.suspended,
                MeasurementRevision.kind == "VALUE",
            )
            .order_by(Measurement.id)
        ):
            sources.setdefault(rule.goal_id, []).append(
                {
                    "measurement_id": str(row.id),
                    "revision_id": str(revision.id),
                    "number": revision.number,
                    "source_key": row.source_label,
                    "source_kind": row.source_kind,
                    "work_item_id": str(row.work_item_id) if row.work_item_id else None,
                    "occurred_at": row.occurred_at.astimezone(UTC).isoformat(),
                    "milestone": row.milestone,
                    "revision_hash": digest(revision.payload),
                    "payload": {
                        k: v for k, v in revision.payload.items() if k not in {"body", "url"}
                    },
                }
            )
        values = []
        for goal in goals:
            spec: dict[str, Any] = goal.specification
            lines = sources.get(goal.id, [])
            try:
                validate_rule(spec)
                result = aggregate(spec, lines)
            except ValueError as exc:
                if lines:
                    raise ApiError(409, "measurement_aggregate_invalid", str(exc)) from exc
                result = {"actual": None, "data_status": "RULE_INCOMPATIBLE", "source_count": 0}
            values.append(
                {
                    "goal_id": str(goal.id),
                    "rule_revision_id": rules.get(goal.id),
                    "name": spec["definition"]["name"],
                    "unit": spec["definition"]["unit"],
                    "method": spec["method"],
                    "target": spec["target"],
                    "rule_hash": digest(spec),
                    "sources": lines,
                    **result,
                }
            )
        return {
            "algorithm": ALGORITHM,
            "plan_id": str(plan.id),
            "event_window": {
                "start_date": str(cycle.start_date),
                "end_date": str(cycle.end_date),
                "timezone": cycle.workflow_schedule["timezone"],
            },
            "plan_revision": plan.revision,
            "version": plan.measurement_version,
            "known_at": datetime.now(UTC).isoformat(),
            "goals": values,
        }

    def snapshot(self, plan: WorkPlan, *, changed: bool = False) -> ProgressSnapshot:
        if changed:
            plan.measurement_version += 1
        self.session.flush()
        row = self.session.scalar(
            select(ProgressSnapshot).where(
                ProgressSnapshot.plan_id == plan.id,
                ProgressSnapshot.version == plan.measurement_version,
            )
        )
        if row is None:
            data = self.snapshot_data(plan)
            row = ProgressSnapshot(
                plan_id=plan.id,
                version=plan.measurement_version,
                data=data,
                content_hash=digest(data),
            )
            self.session.add(row)
            self.session.flush()
        return row

    def goals(
        self,
        actor: User,
        identifier: UUID,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> dict[str, Any]:
        with self.session.begin():
            plan, employee, cycle = self.load(actor, identifier)
            snapshot = self.session.scalar(
                select(ProgressSnapshot).where(
                    ProgressSnapshot.plan_id == plan.id,
                    ProgressSnapshot.version == plan.measurement_version,
                )
            )
            data = snapshot.data if snapshot else self.snapshot_data(plan)
            if from_date is not None or to_date is not None:
                if (
                    from_date is None
                    or to_date is None
                    or not cycle.start_date <= from_date <= to_date <= cycle.end_date
                ):
                    fail(
                        "invalid_measurement_window",
                        "Choose a complete date range within the cycle",
                        422,
                    )
                assert (
                    from_date is not None
                    and to_date is not None
                    and cycle.workflow_schedule is not None
                )
                zone = ZoneInfo(str(cycle.workflow_schedule["timezone"]))
                first = datetime.combine(from_date, time.min, zone)
                last = datetime.combine(to_date + timedelta(days=1), time.min, zone)
                specs_by_id = {
                    str(g.id): g.specification
                    for g in self.session.scalars(
                        select(WorkGoal).where(
                            WorkGoal.plan_id == plan.id, WorkGoal.revision == plan.revision
                        )
                    )
                }
                filtered = []
                for g in data["goals"]:
                    if g["data_status"] == "RULE_INCOMPATIBLE":
                        filtered.append(g)
                        continue
                    lines = [
                        s
                        for s in g["sources"]
                        if datetime.fromisoformat(s["occurred_at"]) < last
                        and (
                            g["method"] in {"LAST", "MILESTONE"}
                            or datetime.fromisoformat(s["occurred_at"]) >= first
                        )
                    ]
                    result = aggregate(specs_by_id[str(g["goal_id"])], lines)
                    filtered.append({**g, **result, "sources": lines})
                data = {**data, "goals": filtered}
            counts = {
                rule.goal_id: count
                for rule, count in self.session.execute(
                    select(MetricRule, func.count(Measurement.id))
                    .join(Measurement, Measurement.rule_id == MetricRule.id)
                    .where(
                        Measurement.plan_id == plan.id,
                        Measurement.status.in_(["DRAFT", "SUBMITTED", "RETURNED"]),
                    )
                    .group_by(MetricRule.id)
                )
            }
            specs = {
                str(g.id): g.specification
                for g in self.session.scalars(
                    select(WorkGoal).where(
                        WorkGoal.plan_id == plan.id, WorkGoal.revision == plan.revision
                    )
                )
            }
            manager = self.repo.manager(employee)
            return {
                "plan_id": plan.id,
                "plan_version": plan.version,
                "measurement_version": plan.measurement_version,
                "employee_name": employee.display_name,
                "owner_id": employee.user_id,
                "manager_id": manager.id if manager else None,
                "can_submit": actor.id == employee.user_id
                and cycle.status == CycleStatus.ACTIVE
                and self.repo.operational(employee)
                and datetime.now(UTC)
                <= datetime.fromisoformat(str(cycle.workflow_schedule["input_cutoff_at"])),  # type: ignore[index]
                "start_date": cycle.start_date,
                "end_date": cycle.end_date,
                "can_schedule": actor.id == (manager.id if manager else None)
                and cycle.status == CycleStatus.ACTIVE
                and self.repo.operational(employee)
                and datetime.now(UTC)
                <= datetime.fromisoformat(str(cycle.workflow_schedule["verification_due_at"])),  # type: ignore[index]
                "from_date": from_date,
                "to_date": to_date,
                "goals": [
                    {
                        **{k: v for k, v in g.items() if k != "sources"},
                        "specification": specs[str(g["goal_id"])],
                        "pending_count": counts.get(UUID(str(g["goal_id"])), 0),
                    }
                    for g in data["goals"]
                ],
            }

    def listing(self, actor: User, goal_id: UUID, page: int) -> dict[str, Any]:
        with self.session.begin():
            goal = self.goal(goal_id)
            _, employee, cycle = self.load(actor, goal.plan_id)
            query = (
                select(Measurement)
                .join(MetricRule, MetricRule.id == Measurement.rule_id)
                .where(MetricRule.goal_id == goal.id)
            )
            total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
            rows = list(
                self.session.scalars(
                    query.order_by(Measurement.created_at.desc(), Measurement.id)
                    .offset((page - 1) * 20)
                    .limit(20)
                )
            )
            identifiers = [row.id for row in rows]
            self._revisions.update(
                {
                    (r.measurement_id, r.number): r
                    for r in self.session.scalars(
                        select(MeasurementRevision)
                        .join(Measurement, Measurement.id == MeasurementRevision.measurement_id)
                        .where(
                            Measurement.id.in_(identifiers),
                            or_(
                                MeasurementRevision.number == Measurement.number,
                                MeasurementRevision.number == Measurement.effective_number,
                            ),
                        )
                    )
                }
            )
            self._rules.update(
                {
                    r.id: r
                    for r in self.session.scalars(
                        select(MetricRule).where(MetricRule.id.in_({row.rule_id for row in rows}))
                    )
                }
            )
            return {
                "items": [self.view(row, actor, employee, cycle) for row in rows],
                "total": total,
                "page": page,
                "page_size": 20,
            }

    def detail(
        self, actor: User, identifier: UUID, page: int, revision_number: int | None = None
    ) -> dict[str, Any]:
        with self.session.begin():
            row = self._row(identifier)
            _, employee, cycle = self.load(actor, row.plan_id)
            selected = None
            if revision_number is not None:
                selected = self.session.scalar(
                    select(MeasurementRevision).where(
                        MeasurementRevision.measurement_id == row.id,
                        MeasurementRevision.number == revision_number,
                    )
                )
                if selected is None:
                    fail("work_not_found", "Measurement revision not found", 404)
            revisions = self.session.scalars(
                select(MeasurementRevision)
                .where(MeasurementRevision.measurement_id == row.id)
                .order_by(MeasurementRevision.number.desc())
                .offset((page - 1) * 20)
                .limit(20)
            )
            return {
                **self.view(row, actor, employee, cycle),
                "selected_revision": {
                    "number": selected.number,
                    "kind": selected.kind,
                    "payload": selected.payload,
                    "created_at": selected.created_at,
                }
                if selected
                else None,
                "revisions": [
                    {
                        "id": r.id,
                        "number": r.number,
                        "kind": r.kind,
                        "payload": r.payload,
                        "created_at": r.created_at,
                    }
                    for r in revisions
                ],
                "history": self.history(row.plan_id, measurement_id=row.id, page=page),
            }

    def history(
        self,
        plan_id: UUID,
        *,
        measurement_id: UUID | None = None,
        checkin_id: UUID | None = None,
        action_id: UUID | None = None,
        page: int = 1,
    ) -> dict[str, Any]:
        query = select(ProgressEvent).where(
            ProgressEvent.plan_id == plan_id,
            ProgressEvent.payload["private"].as_boolean().is_(False),
        )
        for column, value in (
            (ProgressEvent.measurement_id, measurement_id),
            (ProgressEvent.checkin_id, checkin_id),
            (ProgressEvent.action_id, action_id),
        ):
            if value:
                query = query.where(column == value)
        total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = self.session.scalars(
            query.order_by(ProgressEvent.created_at.desc(), ProgressEvent.id)
            .offset((page - 1) * 20)
            .limit(20)
        )
        return {
            "items": [
                {
                    "id": e.id,
                    "kind": e.kind,
                    "body": e.body,
                    "created_at": e.created_at,
                    "actor_id": e.actor_id,
                    "payload": e.payload,
                }
                for e in rows
            ],
            "total": total,
            "page": page,
            "page_size": 20,
        }

    def snapshots(self, actor: User, plan_id: UUID, page: int) -> dict[str, Any]:
        with self.session.begin():
            self.load(actor, plan_id)
            query = select(ProgressSnapshot).where(ProgressSnapshot.plan_id == plan_id)
            total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
            return {
                "items": [
                    {
                        "id": s.id,
                        "version": s.version,
                        "created_at": s.created_at,
                        "content_hash": s.content_hash,
                    }
                    for s in self.session.scalars(
                        query.order_by(ProgressSnapshot.version.desc())
                        .offset((page - 1) * 20)
                        .limit(20)
                    )
                ],
                "total": total,
                "page": page,
                "page_size": 20,
            }

    def snapshot_detail(
        self, actor: User, identifier: UUID, page: int, goal_id: UUID | None = None
    ) -> dict[str, Any]:
        with self.session.begin():
            row = self.session.get(ProgressSnapshot, identifier)
            if row is None:
                fail("work_not_found", "Snapshot not found", 404)
            assert row is not None
            self.load(actor, row.plan_id)
            lines = [
                dict(source, goal_id=g["goal_id"])
                for g in row.data["goals"]
                for source in g["sources"]
                if goal_id is None or str(goal_id) == g["goal_id"]
            ]
            return {
                "id": row.id,
                "version": row.version,
                "known_at": row.data["known_at"],
                "content_hash": row.content_hash,
                "goals": [
                    {k: v for k, v in g.items() if k != "sources"} for g in row.data["goals"]
                ],
                "sources": {
                    "items": lines[(page - 1) * 20 : page * 20],
                    "page": page,
                    "page_size": 20,
                    "total": len(lines),
                },
            }


def suspend_work_source(
    session: Session,
    plan: WorkPlan,
    work: WorkItem,
    actor: User,
    employee: Employee,
    data: Command,
    request_id: str,
) -> None:
    """Called under the existing cycle/participant/plan/work locks in the same transaction."""
    rows = session.scalars(
        select(Measurement)
        .where(
            Measurement.work_item_id == work.id,
            Measurement.effective_number.is_not(None),
            ~Measurement.suspended,
            ~Measurement.retired,
        )
        .order_by(Measurement.id)
        .with_for_update()
    ).all()
    if rows:
        for row in rows:
            row.suspended = True
            row.version += 1
        service = ProgressService(session)
        snapshot = service.snapshot(plan, changed=True)
        # Phase 11 permits one goal per work item, hence at most one source stream.
        service.record(
            actor,
            plan,
            employee,
            # Root work replay is already enforced by WorkEvent. Give the internal
            # effect its own server key instead of reusing a public progress UUID.
            Command(client_request_id=uuid4(), expected_version=data.expected_version),
            work.id,
            "measurement.suspended",
            request_id,
            measurement=rows[0],
            payload={"snapshot_id": str(snapshot.id), "work_item_id": str(work.id)},
        )
