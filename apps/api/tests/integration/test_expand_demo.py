import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cli.expand_demo import CYCLE_NAME, Expansion, expand_demo, main
from app.cli.expanded_demo_data import DEPARTMENTS, roster
from app.cli.seed_demo import DemoConflict, seed_demo
from app.core.database import Base
from app.core.security import PasswordService
from app.main import create_app
from app.models import (
    AIAnalysis,
    AuthSession,
    ChatMessage,
    CycleParticipant,
    CycleStatus,
    Department,
    Employee,
    InternalPost,
    KPIDefinition,
    Position,
    ReviewCycle,
    User,
    UserRole,
)


@pytest.fixture
def seeded(auth_engine):
    assert seed_demo(auth_engine, "1")
    return auth_engine


def snapshot(engine):
    with engine.connect() as connection:
        return {
            table.name: {
                str(row["id"]): hashlib.sha256(
                    json.dumps(dict(row), sort_keys=True, default=str).encode()
                ).hexdigest()
                for row in connection.execute(select(table)).mappings()
            }
            for table in Base.metadata.sorted_tables
        }


def test_expansion_builds_realistic_company_and_preserves_every_existing_row(seeded, monkeypatch):
    def no_ai(*args, **kwargs):
        pytest.fail("Expansion must never invoke an AI provider")

    monkeypatch.setattr("app.modules.ai.provider.GeminiProvider.generate", no_ai)
    before = snapshot(seeded)
    assert expand_demo(seeded)
    after = snapshot(seeded)
    for table, rows in before.items():
        assert rows.items() <= after[table].items(), table
    with Session(seeded) as session:
        for model, expected in (
            (User, 62),
            (Employee, 60),
            (Department, 8),
            (Position, 13),
            (KPIDefinition, 14),
            (ReviewCycle, 4),
            (AIAnalysis, 0),
        ):
            assert session.scalar(select(func.count()).select_from(model)) == expected
        for spec in DEPARTMENTS:
            department = session.scalar(
                select(Department).where(Department.code == "DEMO-" + spec.code)
            )
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(Employee)
                    .where(Employee.department_id == department.id)
                )
                == spec.target
            )
        cycle = session.scalar(select(ReviewCycle).where(ReviewCycle.name == CYCLE_NAME))
        assert cycle.status == CycleStatus.DRAFT
        assert (
            session.scalar(
                select(func.count())
                .select_from(CycleParticipant)
                .where(CycleParticipant.cycle_id == cycle.id)
            )
            == 51
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(ReviewCycle)
                .where(ReviewCycle.status == CycleStatus.ACTIVE)
            )
            == 1
        )
        assert session.scalar(select(func.count()).select_from(InternalPost)) == 9
        assert session.scalar(select(func.count()).select_from(ChatMessage)) == 16
        users = {user.email: user for user in session.scalars(select(User))}
        for account, _, _, _, manager in roster():
            user = users[account + ".demo@example.com"]
            assert user.role == (UserRole.EMPLOYEE if manager else UserRole.MANAGER)
            assert PasswordService().verify("1", user.password_hash)
        employee_users = set(session.scalars(select(Employee.user_id)))
        assert users["hr.demo@example.com"].id not in employee_users
        assert users["admin.demo@example.com"].id not in employee_users
        assert all(row.revoked_at for row in session.scalars(select(AuthSession)))
    first = snapshot(seeded)
    assert expand_demo(seeded, password="must-not-reset-existing-passwords") is False
    assert snapshot(seeded) == first


def test_new_manager_scope_department_feed_and_staff_login_work(seeded):
    assert expand_demo(seeded)
    app = create_app()

    def client(account):
        result = TestClient(app, headers={"Origin": "http://testserver"})
        login = result.post(
            "/api/v1/auth/login", json={"email": account + ".demo@example.com", "password": "1"}
        )
        assert login.status_code == 200, login.text
        return result

    manager = client("product.manager")
    staff = client("product01")
    finance = client("finance.manager")
    employees = manager.get("/api/v1/employees").json()["items"]
    assert employees and all(row["employee_code"].startswith("DEMO-PRODUCT") for row in employees)
    posts = staff.get("/api/v1/collaboration/posts").json()["items"]
    assert len(posts) == 2
    department_post = next(row for row in posts if row["department_id"])
    assert finance.get(f"/api/v1/collaboration/posts/{department_post['id']}").status_code == 404
    assert staff.get("/api/v1/collaboration/conversations").json()["unread_count"] == 1
    assert staff.get("/api/v1/notifications").json()["unread_count"] > 0


def test_late_failure_rolls_back_whole_expansion_including_notices_and_sessions(
    seeded, monkeypatch
):
    before = snapshot(seeded)

    def fail(self):
        raise RuntimeError("late failure")

    monkeypatch.setattr(Expansion, "finish", fail)
    with pytest.raises(RuntimeError, match="late failure"):
        expand_demo(seeded)
    assert snapshot(seeded) == before


def test_concurrent_expansion_is_idempotent(seeded):
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: expand_demo(seeded), range(2)))
    assert sorted(results) == [False, True]
    with Session(seeded) as session:
        assert session.scalar(select(func.count()).select_from(Employee)) == 60
        assert session.scalar(select(func.count()).select_from(InternalPost)) == 9


def test_requires_completed_original_demo(auth_engine):
    before = snapshot(auth_engine)
    with pytest.raises(DemoConflict, match="original office demo"):
        expand_demo(auth_engine)
    assert snapshot(auth_engine) == before


def test_reserved_identifier_collision_leaves_existing_data_untouched(seeded):
    with Session(seeded) as session, session.begin():
        session.add(Department(code="DEMO-PRODUCT", name="Existing department"))
    before = snapshot(seeded)
    with pytest.raises(DemoConflict, match="identifiers"):
        expand_demo(seeded)
    assert snapshot(seeded) == before


def test_changed_original_account_is_not_repaired_or_overwritten(seeded):
    with Session(seeded) as session, session.begin():
        user = session.scalar(select(User).where(User.email == "hr.demo@example.com"))
        user.is_active = False
    before = snapshot(seeded)
    with pytest.raises(DemoConflict, match="accounts changed"):
        expand_demo(seeded)
    assert snapshot(seeded) == before


def test_command_rejects_production_without_opening_database(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(
        "app.cli.expand_demo.get_settings", lambda: SimpleNamespace(app_env="production")
    )
    monkeypatch.setattr(
        "app.cli.expand_demo.get_engine", lambda *_: pytest.fail("No database in production")
    )
    assert main() == 1
