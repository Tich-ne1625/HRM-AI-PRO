from sqlalchemy.orm import Session

from app.core.domain_writes import CsrfCheck, authorize_domain_write, require_version
from app.core.policies import AuthContext
from app.modules.audit.service import AuditWriter
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.schemas import ScoringPolicy, ScoringUpdate, ScoringView
from app.modules.users.models import UserRole


class SettingsService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = SettingsRepository(session)

    def read(self) -> ScoringView:
        with self.session.begin():
            row = self.repository.get()
            return ScoringView(
                version=row.version,
                policy=ScoringPolicy.model_validate(
                    row.scoring_policy,
                ),
            )

    def update(
        self, body: ScoringUpdate, context: AuthContext, *, csrf: CsrfCheck, request_id: str
    ) -> ScoringView:
        with self.session.begin():
            authorize_domain_write(self.session, context, csrf, (UserRole.ADMIN,))
            row = self.repository.get(lock=True)
            require_version(row.version, body.expected_version)
            policy = body.policy.model_dump(mode="json")
            if policy != row.scoring_policy:
                previous = row.version
                row.scoring_policy = policy
                row.version += 1
                AuditWriter().record(
                    self.session,
                    context.user.id,
                    "scoring_defaults.updated",
                    "system_config",
                    "1",
                    request_id,
                    {"previous_version": previous, "version": row.version},
                )
                self.session.flush()
            return ScoringView(version=row.version, policy=body.policy)
