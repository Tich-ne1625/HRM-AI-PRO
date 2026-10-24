"""A separately committed reservation shared by workers, before Argon2/user locks."""

import hashlib
import hmac
from datetime import datetime
from math import ceil

from sqlalchemy import CheckConstraint, DateTime, Integer, String, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.config import Settings
from app.core.database import Base
from app.core.errors import ApiError


class LoginLimit(Base):
    __tablename__ = "auth_login_limits"
    __table_args__ = (
        CheckConstraint("attempts >= 1", name="ck_login_limit_attempts"),
        CheckConstraint("bucket_key ~ '^[0-9a-f]{64}$'", name="ck_login_limit_key"),
    )
    bucket_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


def reserve_login(session: Session, settings: Settings, email: str) -> None:
    key = hmac.new(
        settings.access_signing_key.get_secret_value().encode(),
        ("login-limit:v1:" + email).encode(),
        hashlib.sha256,
    ).hexdigest()
    try:
        with session.begin():
            # A stable database statement time makes both CASE arms agree at expiry.
            row = session.execute(
                text("""
                INSERT INTO auth_login_limits (bucket_key, attempts, expires_at)
                VALUES (:key, 1, statement_timestamp() + make_interval(secs => :window))
                ON CONFLICT (bucket_key) DO UPDATE SET
                    attempts = CASE WHEN auth_login_limits.expires_at <= statement_timestamp()
                        THEN 1 ELSE LEAST(auth_login_limits.attempts + 1, :cap + 1) END,
                    expires_at = CASE WHEN auth_login_limits.expires_at <= statement_timestamp()
                        THEN statement_timestamp() + make_interval(secs => :window)
                        ELSE auth_login_limits.expires_at END
                RETURNING attempts, GREATEST(1, EXTRACT(EPOCH FROM
                    (expires_at - statement_timestamp()))) AS retry
            """),
                {
                    "key": key,
                    "window": settings.auth_login_window_seconds,
                    "cap": settings.auth_login_max_attempts,
                },
            ).one()
    except SQLAlchemyError:
        raise ApiError(
            503, "login_temporarily_unavailable", "Login is temporarily unavailable"
        ) from None
    if row.attempts > settings.auth_login_max_attempts:
        raise ApiError(
            429,
            "login_rate_limited",
            "Too many login attempts; try again later",
            headers={"Retry-After": str(ceil(row.retry))},
        )
