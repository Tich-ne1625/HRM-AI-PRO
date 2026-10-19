import io
import os
import subprocess
import sys
from collections.abc import Callable
from getpass import GetPassWarning
from uuid import UUID

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import PasswordService
from app.models import AuditLog, User, UserRole

pytestmark = pytest.mark.integration


def assert_empty(engine: Engine) -> None:
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(User)) == 0
        assert session.scalar(select(func.count()).select_from(AuditLog)) == 0


@pytest.mark.parametrize("password", ["a" * 12, "z" * 128, " é" * 6])
def test_stdin_creates_normalized_admin_and_audit_without_echo(
    auth_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    password: str,
) -> None:
    from app.cli.create_admin import main

    stream = io.StringIO(f"{password}\n{password}\nuntouched\n")
    monkeypatch.setattr(sys, "stdin", stream)
    assert main(["--email", "Straße@EXAMPLE.com", "--password-stdin"]) == 0
    assert stream.read() == "untouched\n"
    with Session(auth_engine) as session:
        account = session.scalars(select(User)).one()
        assert account.email == "strasse@example.com"
        assert account.role is UserRole.ADMIN and account.is_active is True
        assert account.password_hash.startswith("$argon2id$")
        assert PasswordService().verify(password, account.password_hash)
        audit = session.scalars(select(AuditLog)).one()
        assert audit.action == "user.bootstrap_created"
        assert audit.actor_id == account.id and audit.entity_type == "user"
        assert audit.entity_id == str(account.id)
        assert UUID(audit.request_id)
        assert audit.metadata_ == {"role": "ADMIN"}
        encoded = account.password_hash
    output = capsys.readouterr()
    assert password not in output.out + output.err
    assert encoded not in output.out + output.err


@pytest.mark.parametrize("confirmed", [True, False])
def test_interactive_password_requires_hidden_confirmation(
    auth_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    confirmed: bool,
) -> None:
    from app.cli import create_admin

    password = "interactive-secret"
    responses = iter([password, password if confirmed else "different-secret"])
    prompts: list[str] = []

    def prompt(message: str) -> str:
        prompts.append(message)
        return next(responses)

    monkeypatch.setattr(create_admin, "getpass", prompt)
    monkeypatch.setattr(sys, "stdin", io.StringIO("do not read this"))
    assert (create_admin.main(["--email", "admin@example.com"]) == 0) is confirmed
    assert len(prompts) == 2
    assert sys.stdin.read() == "do not read this"
    if confirmed:
        with Session(auth_engine) as session:
            account = session.scalars(select(User)).one()
            assert PasswordService().verify(password, account.password_hash)
    else:
        assert_empty(auth_engine)
    output = capsys.readouterr()
    assert password not in output.out + output.err


@pytest.mark.parametrize(
    "input_text",
    [
        "a" * 11 + "\n" + "a" * 11 + "\n",
        "a" * 129 + "\n" + "a" * 129 + "\n",
        "valid-password\ndifferent-password\n",
        "valid-password\n",
        "",
        "\n\n",
    ],
)
def test_invalid_stdin_passwords_exit_nonzero_without_writes(
    auth_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    input_text: str,
) -> None:
    from app.cli.create_admin import main

    monkeypatch.setattr(sys, "stdin", io.StringIO(input_text))
    assert main(["--email", "admin@example.com", "--password-stdin"]) != 0
    assert_empty(auth_engine)


@pytest.mark.parametrize("email", ["not-an-email", "a" * 64 + "@" + "b" * 190 + ".com"])
def test_invalid_email_exits_nonzero_without_writes(
    auth_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    email: str,
) -> None:
    from app.cli.create_admin import main

    monkeypatch.setattr(sys, "stdin", io.StringIO("valid-password\nvalid-password\n"))
    assert main(["--email", email, "--password-stdin"]) != 0
    assert_empty(auth_engine)


@pytest.mark.parametrize("simulate_race", [False, True])
def test_duplicate_email_preserves_original_user_and_audit(
    auth_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    simulate_race: bool,
) -> None:
    from app.cli.create_admin import main
    from app.modules.users.repository import UserRepository

    monkeypatch.setattr(sys, "stdin", io.StringIO("first-password\nfirst-password\n"))
    assert main(["--email", "Admin@EXAMPLE.com", "--password-stdin"]) == 0
    with Session(auth_engine) as session:
        original = session.scalars(select(User)).one()
        original_id, original_hash = original.id, original.password_hash
    if simulate_race:
        monkeypatch.setattr(UserRepository, "get_by_normalized_email", lambda *_: None)
    monkeypatch.setattr(sys, "stdin", io.StringIO("second-password\nsecond-password\n"))
    assert main(["--email", "ADMIN@example.com", "--password-stdin"]) != 0
    with Session(auth_engine) as session:
        account = session.scalars(select(User)).one()
        assert (account.id, account.password_hash) == (original_id, original_hash)
        assert session.scalar(select(func.count()).select_from(AuditLog)) == 1


def test_audit_failure_rolls_back_user_and_hides_internal_error(
    auth_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from app.cli.create_admin import main
    from app.modules.audit.service import AuditWriter

    def fail(*args: object, **kwargs: object) -> None:
        # The user has been flushed in this transaction when the audit fails.
        raise SQLAlchemyError("secret database details")

    monkeypatch.setattr(AuditWriter, "record", fail)
    monkeypatch.setattr(sys, "stdin", io.StringIO("valid-password\nvalid-password\n"))
    assert main(["--email", "admin@example.com", "--password-stdin"]) != 0
    assert_empty(auth_engine)
    output = capsys.readouterr()
    assert "secret database details" not in output.out + output.err


@pytest.mark.parametrize("error_type", [EOFError, KeyboardInterrupt, GetPassWarning])
def test_interactive_unavailable_or_cancelled_fails_without_writes(
    auth_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    error_type: Callable[[], BaseException],
) -> None:
    from app.cli import create_admin

    def fail(prompt: str) -> str:
        raise error_type()

    monkeypatch.setattr(create_admin, "getpass", fail)
    assert create_admin.main(["--email", "admin@example.com"]) != 0
    assert_empty(auth_engine)


def test_module_entrypoint_accepts_stdin_and_propagates_exit_status(auth_engine: Engine) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = auth_engine.url.render_as_string(hide_password=False)
    arguments = [
        sys.executable,
        "-m",
        "app.cli.create_admin",
        "--email",
        "cli@example.com",
        "--password-stdin",
    ]
    for expected_success in (True, False):
        result = subprocess.run(
            arguments,
            input="subprocess-password\nsubprocess-password\n",
            text=True,
            capture_output=True,
            env=environment,
            timeout=30,
        )
        assert (result.returncode == 0) is expected_success
        assert "subprocess-password" not in result.stdout + result.stderr
    with Session(auth_engine) as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1
        assert session.scalar(select(func.count()).select_from(AuditLog)) == 1
