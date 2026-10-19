from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from email_validator import EmailNotValidError, validate_email
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApiError
from app.core.security import PasswordService, TokenService, hash_opaque_token, new_opaque_token
from app.modules.audit.service import AuditWriter
from app.modules.auth.models import AuthSession
from app.modules.auth.repository import AuthSessionRepository
from app.modules.auth.schemas import CurrentUser, LoginCommand
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
            user = UserRepository(self.session).get_by_normalized_email(email)
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
