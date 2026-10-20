from collections.abc import Mapping
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog, AuditValue

# Services construct these small metadata objects explicitly; never pass request bodies.
ALLOWED_METADATA_KEYS = frozenset({"role", "previous_role", "is_active", "previous_is_active"})
ORGANIZATION_METADATA_KEYS = frozenset(
    {
        "changed_fields",
        "code",
        "is_active",
        "employee_code",
        "department_id",
        "position_id",
        "manager_id",
        "user_id",
        "employment_status",
        "previous_user_id",
        "previous_manager_id",
    }
)
REVIEW_METADATA_KEYS = frozenset(
    {
        "changed_fields",
        "code",
        "is_active",
        "previous_version",
        "version",
        "cycle_id",
        "participant_id",
        "employee_id",
        "definition_id",
        "count",
        "status",
        "previous_evidence_version",
        "evidence_version",
        "policy_source_version",
    }
)
FEEDBACK_METADATA_KEYS = frozenset(
    {
        "participant_id",
        "reviewer_id",
        "relationship",
        "required",
        "status",
        "version",
        "evidence_version",
        "reason_code",
        "replacement_id",
        "previous_assignment_id",
    }
)


class AuditWriter:
    def record(
        self,
        session: Session,
        actor_id: UUID | None,
        action: str,
        entity_type: str,
        entity_id: str,
        request_id: str,
        metadata: Mapping[str, AuditValue],
    ) -> AuditLog:
        allowed = (
            ORGANIZATION_METADATA_KEYS
            if action.startswith(("department.", "position.", "employee."))
            else ALLOWED_METADATA_KEYS
        )
        if action.startswith(
            (
                "scoring_defaults.",
                "review_cycle.",
                "cycle_participant.",
                "kpi_definition.",
                "kpi_allocation.",
                "employee_kpi.",
            )
        ):
            allowed = REVIEW_METADATA_KEYS
        if action.startswith(("assignment.", "feedback.")):
            allowed = FEEDBACK_METADATA_KEYS
        if metadata.keys() - allowed:
            raise ValueError("Audit metadata contains an unsupported field")
        record = AuditLog(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            request_id=request_id,
            metadata_=dict(metadata),
        )
        session.add(record)
        session.flush()
        return record
