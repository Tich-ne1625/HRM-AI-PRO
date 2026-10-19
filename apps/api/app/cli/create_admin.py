from __future__ import annotations

import argparse
import sys
import warnings
from collections.abc import Sequence
from getpass import GetPassWarning, getpass
from uuid import uuid4

from email_validator import EmailNotValidError, validate_email
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.config import get_settings
from app.core.database import get_engine, get_session_factory
from app.core.security import PasswordService
from app.models import User, UserRole
from app.modules.audit.service import AuditWriter
from app.modules.users.repository import UserRepository


class BootstrapInputError(ValueError):
    """A safe diagnostic containing no supplied credentials."""


def _normalized_email(email: str) -> str:
    try:
        normalized = validate_email(email, check_deliverability=False).normalized.casefold()
    except EmailNotValidError:
        raise BootstrapInputError("Enter a valid email address.") from None
    if len(normalized) > 254:
        raise BootstrapInputError("Email must be at most 254 characters.")
    return normalized


def _read_password(password_stdin: bool) -> str:
    if password_stdin:
        first, second = sys.stdin.readline(), sys.stdin.readline()
        if not first or not second:
            raise BootstrapInputError("Provide two matching password lines on stdin.")
        password = first.removesuffix("\n").removesuffix("\r")
        confirmation = second.removesuffix("\n").removesuffix("\r")
    else:
        # Do not permit getpass's fallback to echoing input when no TTY exists.
        with warnings.catch_warnings():
            warnings.simplefilter("error", GetPassWarning)
            password = getpass("Password: ")
            confirmation = getpass("Confirm password: ")
    if password != confirmation:
        raise BootstrapInputError("Passwords do not match.")
    if not 12 <= len(password) <= 128:
        raise BootstrapInputError("Password must contain 12 to 128 characters.")
    return password


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create an active InsightHR administrator.")
    parser.add_argument("--email", required=True)
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read two matching password lines from stdin without echo.",
    )
    arguments = parser.parse_args(argv)
    try:
        email = _normalized_email(arguments.email)
        password = _read_password(arguments.password_stdin)
        password_hash = PasswordService().hash(password)
        engine = get_engine(get_settings())
        try:
            with get_session_factory(engine).begin() as session:
                users = UserRepository(session)
                if users.get_by_normalized_email(email) is not None:
                    raise BootstrapInputError("An account with this email already exists.")
                user = users.add(
                    User(
                        email=email,
                        password_hash=password_hash,
                        role=UserRole.ADMIN,
                        is_active=True,
                    )
                )
                AuditWriter().record(
                    session,
                    user.id,
                    "user.bootstrap_created",
                    "user",
                    str(user.id),
                    str(uuid4()),
                    {"role": UserRole.ADMIN.value},
                )
        finally:
            engine.dispose()
    except BootstrapInputError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt, GetPassWarning):
        print(
            "Password input unavailable or cancelled. Use --password-stdin for automation.",
            file=sys.stderr,
        )
        return 1
    except IntegrityError as error:
        # A duplicate can win a race after the precheck. The transaction has rolled back.
        if getattr(error.orig, "sqlstate", None) == "23505":
            print("An account with this email already exists.", file=sys.stderr)
        else:
            print("Administrator creation failed; no changes were saved.", file=sys.stderr)
        return 1
    except (SQLAlchemyError, ValueError):
        print("Administrator creation failed; no changes were saved.", file=sys.stderr)
        return 1
    print("Administrator created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
