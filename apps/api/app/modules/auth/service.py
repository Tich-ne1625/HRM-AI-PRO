from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from email_validator import EmailNotValidError, validate_email
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApiError
from app.core.security import (
    InvalidAccessToken,
    PasswordService,
    TokenService,
    hash_opaque_token,
    new_opaque_token,
)
from app.modules.audit.service import AuditWriter
from app.modules.auth.models import AuthSession
from app.modules.auth.repository import AuthSessionRepository
from app.modules.auth.schemas import ChangePasswordRequest, CurrentUser, LoginCommand
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

# Fixed, valid Argon2id hash with the same work parameters as account passwords.
# Unknown accounts still perform the expensive verification without per-request hashing.
DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$VizlzOWja7czIUu62NBEMQ$"
    "Z4o/pYfsQnV1ucdy5TdcL/h4r+YIfrDcSTtznRQ181U"
)


@dataclass(frozen=True)
class AuthResult:
    user: CurrentUser
    access_token: SecretStr
    refresh_token: SecretStr
    csrf_token: SecretStr
    expires_at: datetime


class AuthService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.passwords = PasswordService()
        self.tokens = TokenService(
            settings.access_signing_key, access_token_minutes=settings.access_token_minutes
        )
        self.audit = AuditWriter()

    def login(self, command: LoginCommand) -> AuthResult:
        try:
            email = validate_email(command.email, check_deliverability=False).normalized.casefold()
        except EmailNotValidError:
            email = ""

        result = None
        with self.session.begin():
            # Share the mutation lock before verifying credentials: an in-flight
            # old-password login must not outlive password-change revocation.
            user = UserRepository(self.session).get_by_normalized_email(email, for_update=True)
            valid_password = self.passwords.verify(
                command.password.get_secret_value(),
                user.password_hash if user is not None else DUMMY_PASSWORD_HASH,
            )
            if user is None or not valid_password or not user.is_active:
                self.audit.record(
                    self.session,
                    user.id if user is not None else None,
                    "auth.login_failed",
                    "user",
                    str(user.id) if user is not None else "unknown",
                    command.request_id,
                    {},
                )
            else:
                family_id = uuid4()
                refresh_token, csrf_token = new_opaque_token(), new_opaque_token()
                expires_at = datetime.now(UTC) + timedelta(days=self.settings.refresh_session_days)
                AuthSessionRepository(self.session).add(
                    AuthSession(
                        user_id=user.id,
                        family_id=family_id,
                        token_hash=hash_opaque_token(refresh_token),
                        csrf_hash=hash_opaque_token(csrf_token),
                        expires_at=expires_at,
                    )
                )
                result = AuthResult(
                    user=CurrentUser.model_validate(user),
                    access_token=SecretStr(self.tokens.create_access_token(user.id, family_id)),
                    refresh_token=SecretStr(refresh_token),
                    csrf_token=SecretStr(csrf_token),
                    expires_at=expires_at,
                )
                self.audit.record(
                    self.session,
                    user.id,
                    "auth.login_succeeded",
                    "auth_session",
                    str(family_id),
                    command.request_id,
                    {},
                )

        # Failed attempts commit their sanitized audit before returning the generic error.
        if result is None:
            raise ApiError(401, "invalid_credentials", "Invalid email or password")
        return result

    def rotate_refresh(
        self,
        refresh_token: str | None,
        *,
        csrf_token: str | None,
        require_csrf: Callable[[AuthSession], None],
        request_id: str,
    ) -> AuthResult:
        if not refresh_token:
            raise self._invalid_session()
        result = None
        reuse = False
        with self.session.begin():
            sessions = AuthSessionRepository(self.session)
            row = sessions.get_by_token_hash_for_update(hash_opaque_token(refresh_token))
            now = datetime.now(UTC)
            if row is None:
                raise self._invalid_session()
            user = UserRepository(self.session).get_by_id(row.user_id)
            if row.revoked_at is not None or row.expires_at <= now:
                raise self._invalid_session()
            if user is None or not user.is_active:
                raise self._invalid_session()
            # Check family binding before even the replay branch can revoke it.
            require_csrf(row)
            if row.consumed_at is not None:
                sessions.revoke_family(row.family_id, revoked_at=now)
                self.audit.record(
                    self.session,
                    user.id,
                    "auth.refresh_reuse_detected",
                    "auth_session",
                    str(row.family_id),
                    request_id,
                    {},
                )
                reuse = True
            else:
                refresh = new_opaque_token()
                sessions.add_successor(
                    row,
                    token_hash=hash_opaque_token(refresh),
                    csrf_hash=row.csrf_hash,
                    consumed_at=now,
                )
                result = AuthResult(
                    user=CurrentUser.model_validate(user),
                    access_token=SecretStr(self.tokens.create_access_token(user.id, row.family_id)),
                    refresh_token=SecretStr(refresh),
                    csrf_token=SecretStr(csrf_token or ""),
                    expires_at=row.expires_at,
                )
                self.audit.record(
                    self.session,
                    user.id,
                    "auth.refresh_succeeded",
                    "auth_session",
                    str(row.family_id),
                    request_id,
                    {},
                )
        # Replay revocation and audit must commit before the public error is raised.
        if reuse:
            raise ApiError(401, "refresh_reuse_detected", "Refresh token reuse detected")
        assert result is not None
        return result

    @staticmethod
    def _invalid_session() -> ApiError:
        return ApiError(401, "invalid_session", "Invalid session")

    def _mutation_session(self, access_token: str | None) -> tuple[User, AuthSession]:
        # This helper is only for these two mutations; request policies follow in Task 5.
        if not access_token:
            raise self._invalid_session()
        try:
            claims = self.tokens.decode_access_token(access_token)
        except InvalidAccessToken:
            raise self._invalid_session() from None
        user = UserRepository(self.session).get_by_id_for_update(claims.user_id)
        if user is None or not user.is_active:
            raise self._invalid_session()
        rows = AuthSessionRepository(self.session).get_active_family_for_update(
            claims.family_id, now=datetime.now(UTC)
        )
        if not rows or rows[0].user_id != user.id:
            raise self._invalid_session()
        return user, rows[0]

    def revoke_family(
        self,
        access_token: str | None,
        *,
        require_csrf: Callable[[AuthSession], None],
        request_id: str,
    ) -> None:
        with self.session.begin():
            user, row = self._mutation_session(access_token)
            require_csrf(row)
            AuthSessionRepository(self.session).revoke_family(
                row.family_id, revoked_at=datetime.now(UTC)
            )
            self.audit.record(
                self.session,
                user.id,
                "auth.logout",
                "auth_session",
                str(row.family_id),
                request_id,
                {},
            )

    def change_password(
        self,
        access_token: str | None,
        body: ChangePasswordRequest,
        *,
        require_csrf: Callable[[AuthSession], None],
        request_id: str,
    ) -> None:
        with self.session.begin():
            user, row = self._mutation_session(access_token)
            require_csrf(row)
            old, new = body.old_password.get_secret_value(), body.new_password.get_secret_value()
            if not self.passwords.verify(old, user.password_hash):
                raise ApiError(401, "invalid_credentials", "Invalid credentials")
            if not 12 <= len(new) <= 128 or new == old:
                raise ApiError(422, "invalid_password", "Password does not meet policy")
            user.password_hash = self.passwords.hash(new)
            AuthSessionRepository(self.session).revoke_other_families(
                user.id, row.family_id, revoked_at=datetime.now(UTC)
            )
            self.audit.record(
                self.session,
                user.id,
                "user.password_changed",
                "user",
                str(user.id),
                request_id,
                {},
            )
