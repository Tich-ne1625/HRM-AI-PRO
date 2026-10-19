from collections.abc import Mapping
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog, AuditValue

# Services construct these small metadata objects explicitly; never pass request bodies.
ALLOWED_METADATA_KEYS = frozenset({"role", "previous_role", "is_active", "previous_is_active"})


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
        if metadata.keys() - ALLOWED_METADATA_KEYS:
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
