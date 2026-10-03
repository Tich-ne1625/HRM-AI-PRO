from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type
from pydantic import SecretStr

ACCESS_COOKIE_NAME = "insighthr_access"
REFRESH_COOKIE_NAME = "insighthr_refresh"
CSRF_COOKIE_NAME = "insighthr_csrf"


@dataclass(frozen=True)
class AccessClaims:
    user_id: UUID
    family_id: UUID
    issued_at: datetime
    expires_at: datetime


class InvalidAccessToken(ValueError):
    """One public error for malformed, invalid, and expired access tokens."""


class PasswordService:
    def __init__(self) -> None:
        self._hasher = PasswordHasher(
            time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16, type=Type.ID
        )

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, encoded_hash: str) -> bool:
        try:
            return self._hasher.verify(encoded_hash, password)
        except (VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, encoded_hash: str) -> bool:
        """Call after successful verification to detect obsolete hash parameters."""
        return self._hasher.check_needs_rehash(encoded_hash)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TokenService:
    def __init__(
        self,
        signing_key: SecretStr | str,
        *,
        access_token_minutes: int = 15,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._signing_key = (
            signing_key.get_secret_value() if isinstance(signing_key, SecretStr) else signing_key
        )
        self._access_lifetime = timedelta(minutes=access_token_minutes)
        self._clock = clock

    def create_access_token(self, user_id: UUID, family_id: UUID) -> str:
        now = self._clock()
        return jwt.encode(
            {
                "sub": str(user_id),
                "sid": str(family_id),
                "type": "access",
                "iat": int(now.timestamp()),
                "exp": int((now + self._access_lifetime).timestamp()),
            },
            self._signing_key,
            algorithm="HS256",
        )

    def decode_access_token(self, token: str) -> AccessClaims:
        try:
            payload = jwt.decode(
                token,
                self._signing_key,
                algorithms=["HS256"],
                options={
                    "require": ["sub", "sid", "type", "iat", "exp"],
                    # Validate dates with the same injected clock used for issuance.
                    "verify_exp": False,
                    "verify_iat": False,
                },
            )
            if (
                payload["type"] != "access"
                or not isinstance(payload["sub"], str)
                or not isinstance(payload["sid"], str)
                or type(payload["iat"]) is not int
                or type(payload["exp"]) is not int
            ):
                raise ValueError
            issued_at = datetime.fromtimestamp(payload["iat"], UTC)
            expires_at = datetime.fromtimestamp(payload["exp"], UTC)
            now = self._clock()
            if issued_at > now or expires_at <= now or expires_at <= issued_at:
                raise ValueError
            return AccessClaims(
                user_id=UUID(payload["sub"]),
                family_id=UUID(payload["sid"]),
                issued_at=issued_at,
                expires_at=expires_at,
            )
        except (jwt.InvalidTokenError, ValueError, TypeError, OverflowError, OSError):
            raise InvalidAccessToken("Invalid access token") from None


def new_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def hash_opaque_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
