from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.auth.models import AuthSession


class AuthSessionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, auth_session: AuthSession) -> AuthSession:
        self.session.add(auth_session)
        self.session.flush()
        return auth_session

    def get_by_token_hash_for_update(self, token_hash: str) -> AuthSession | None:
        # Include consumed/revoked rows so the caller can detect token replay.
        return self.session.scalar(
            select(AuthSession)
            .where(AuthSession.token_hash == token_hash)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def get_active_family(self, family_id: UUID, *, now: datetime) -> list[AuthSession]:
        return list(
            self.session.scalars(
                select(AuthSession)
                .where(
                    AuthSession.family_id == family_id,
                    AuthSession.consumed_at.is_(None),
                    AuthSession.revoked_at.is_(None),
                    AuthSession.expires_at > now,
                )
                .order_by(AuthSession.id)
            )
        )

    def revoke_family(self, family_id: UUID, *, revoked_at: datetime) -> int:
        changed = self.session.scalars(
            update(AuthSession)
            .where(AuthSession.family_id == family_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
            .returning(AuthSession)
            .execution_options(populate_existing=True)
        ).all()
        self.session.flush()
        return len(changed)

    def revoke_other_families(
        self, user_id: UUID, current_family_id: UUID, *, revoked_at: datetime
    ) -> int:
        changed = self.session.scalars(
            update(AuthSession)
            .where(
                AuthSession.user_id == user_id,
                AuthSession.family_id != current_family_id,
                AuthSession.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
            .returning(AuthSession)
            .execution_options(populate_existing=True)
        ).all()
        self.session.flush()
        return len(changed)

    def add_successor(
        self, predecessor: AuthSession, *, token_hash: str, csrf_hash: str, consumed_at: datetime
    ) -> AuthSession:
        """Caller locks and validates the predecessor before rotating it."""
        successor = self.add(
            AuthSession(
                user_id=predecessor.user_id,
                family_id=predecessor.family_id,
                expires_at=predecessor.expires_at,
                token_hash=token_hash,
                csrf_hash=csrf_hash,
            )
        )
        predecessor.consumed_at = consumed_at
        predecessor.replacement_id = successor.id
        self.session.flush()
        return successor
