import hashlib
import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.employees.models import Employee
from app.modules.feedback.models import AssignmentStatus, Feedback, FeedbackAssignment
from app.modules.feedback.summary import coverage
from app.modules.kpis.allocation_schemas import DefinitionSnapshot
from app.modules.kpis.models import EmployeeKPI
from app.modules.performance.engine import ENGINE_VERSION, compute
from app.modules.performance.schemas import HRReadiness, Issue
from app.modules.review_cycles.models import CycleParticipant, ReviewCycle
from app.modules.review_cycles.schemas import ParticipantSnapshot
from app.modules.settings.schemas import ScoringPolicy


@dataclass
class Evidence:
    snapshot: dict[str, Any]
    policy: dict[str, Any]
    readiness: HRReadiness

    @property
    def digest(self) -> str:
        return self.digest_for(ENGINE_VERSION)

    def digest_for(self, engine_version: str) -> str:
        snapshot = {
            **self.snapshot,
            "items": sorted(self.snapshot["items"], key=lambda item: item["id"]),
            "assignments": sorted(self.snapshot["assignments"], key=lambda item: item["id"]),
        }
        payload = {"snapshot": snapshot, "policy": self.policy, "engine": engine_version}
        return hashlib.sha256(
            json.dumps(
                payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
            ).encode()
        ).hexdigest()

    @property
    def ratings(self) -> list[int]:
        return [a["rating"] for a in self.snapshot["assignments"] if a["status"] == "SUBMITTED"]


def collect(
    session: Session, participant: CycleParticipant, employee: Employee, cycle: ReviewCycle
) -> Evidence:
    issues: list[Issue] = []
    subject = {
        "employee_id": str(employee.id),
        "employee_code": employee.employee_code,
        "display_name": employee.display_name,
    }
    if participant.snapshot is None:
        issues.append(Issue(code="cycle_not_active"))
    else:
        try:
            frozen = ParticipantSnapshot.model_validate(participant.snapshot)
            subject = {
                "employee_id": str(frozen.employee_id),
                "employee_code": frozen.employee_code,
                "display_name": frozen.display_name,
            }
        except ValidationError:
            issues.append(Issue(code="evidence_inconsistent"))
    policy: dict[str, Any] = {}
    try:
        policy = ScoringPolicy.model_validate(cycle.scoring_policy_snapshot).model_dump(mode="json")
    except ValidationError:
        issues.append(Issue(code="scoring_policy_incompatible"))
    kpis = list(
        session.scalars(
            select(EmployeeKPI)
            .where(EmployeeKPI.participant_id == participant.id)
            .order_by(EmployeeKPI.id)
        )
    )
    items: list[dict[str, Any]] = []
    if not kpis:
        issues.append(Issue(code="kpi_allocation_required"))
    for row in kpis:
        if row.actual is None:
            issues.append(Issue(code="kpi_actual_required", kpi_id=row.id))
        try:
            definition = DefinitionSnapshot.model_validate(row.definition_snapshot)
            items.append(
                {
                    "id": str(row.id),
                    "definition_id": str(row.definition_id),
                    "code": definition.code,
                    "name": definition.name,
                    "unit": definition.unit,
                    "direction": definition.direction.value,
                    "target": format(row.target, ".4f"),
                    "actual": None if row.actual is None else format(row.actual, ".4f"),
                    "weight": format(row.weight, ".2f"),
                    "definition_version": definition.version,
                }
            )
        except ValidationError:
            issues.append(Issue(code="evidence_inconsistent", kpi_id=row.id))
    if items and all(r["actual"] is not None for r in items) and policy:
        try:
            compute(items, [1], policy)
        except ValueError:
            issues.append(Issue(code="allocation_or_policy_invalid"))
    rows = session.execute(
        select(FeedbackAssignment, Feedback)
        .outerjoin(Feedback, Feedback.assignment_id == FeedbackAssignment.id)
        .where(FeedbackAssignment.participant_id == participant.id)
        .order_by(FeedbackAssignment.id)
    ).all()
    assignments = []
    for assignment, feedback in rows:
        submitted = assignment.status == AssignmentStatus.SUBMITTED
        if submitted != (feedback is not None) or (feedback and not 1 <= feedback.rating <= 5):
            issues.append(Issue(code="evidence_inconsistent"))
        assignments.append(
            {
                "id": str(assignment.id),
                "reviewer_id": str(assignment.reviewer_id),
                "relationship": assignment.relationship.value,
                "required": assignment.required,
                "status": assignment.status.value,
                "rating": feedback.rating if feedback else None,
            }
        )
    required = coverage(session, participant.id)
    if not required.ready:
        issues.append(Issue(code="required_feedback_incomplete"))
    return Evidence(
        snapshot={
            "schema_version": 1,
            "subject": subject,
            "participant_id": str(participant.id),
            "evidence_version": participant.evidence_version,
            "policy_source_version": cycle.policy_source_version,
            "items": items,
            "assignments": assignments,
        },
        policy=policy,
        readiness=HRReadiness(
            ready=not issues,
            issue_count=len(issues),
            issues=issues[:100],
            pending_assignment_ids=required.pending_assignment_ids,
            blocked_assignment_ids=required.blocked_assignment_ids,
        ),
    )
