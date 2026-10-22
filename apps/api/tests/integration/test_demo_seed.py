from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cli.seed_demo import ACCOUNTS, DemoBuilder, DemoConflict, email, seed_demo
from app.models import (
    AIAnalysis,
    AuditLog,
    AuthSession,
    CycleParticipant,
    CycleStatus,
    Department,
    Employee,
    Feedback,
    PerformanceReview,
    PerformanceReviewRevision,
    ReviewCycle,
    User,
)

PASSWORD = "fictional-demo-test-password"


def test_demo_preserves_existing_data_real_logins_roles_and_practice_states(world, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("The demo must never invoke Gemini")

    monkeypatch.setattr("app.modules.ai.provider.GeminiProvider.generate", forbidden)
    with Session(world.engine) as session:
        before = {u.id: (u.email, u.password_hash, u.role) for u in session.scalars(select(User))}
    assert seed_demo(world.engine, PASSWORD)
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(User)) == len(before) + 10
        assert all(
            (
                session.get(User, identifier).email,
                session.get(User, identifier).password_hash,
                session.get(User, identifier).role,
            )
            == original
            for identifier, original in before.items()
        )
        current = session.scalars(
            select(ReviewCycle).where(ReviewCycle.status == CycleStatus.ACTIVE)
        ).one()
        cycle_id = str(current.id)
        employees = {e.employee_code: str(e.id) for e in session.scalars(select(Employee))}
        assert session.scalar(select(func.count()).select_from(AIAnalysis)) == 0
        assert session.scalar(select(func.count()).select_from(PerformanceReview)) == 5
        assert session.scalar(select(func.count()).select_from(PerformanceReviewRevision)) == 6
        seeded = select(User.id).where(User.email.in_([email(n) for n in ACCOUNTS]))
        sessions = session.scalars(select(AuthSession).where(AuthSession.user_id.in_(seeded))).all()
        assert len(sessions) == 10 and all(row.revoked_at for row in sessions)
    clients = {}
    from fastapi.testclient import TestClient

    for name, (_, role) in ACCOUNTS.items():
        client = TestClient(world.app, headers={"Origin": "http://testserver"})
        response = client.post(
            "/api/v1/auth/login", json={"email": email(name), "password": PASSWORD}
        )
        assert response.status_code == 200, response.text
        assert response.json()["role"] == role
        client.headers["X-CSRF-Token"] = client.cookies["insighthr_csrf"]
        clients[name] = client
    for person, state in {
        "an": "CURRENT",
        "binh": "NOT_CALCULATED",
        "dung": "NOT_CALCULATED",
        "ha": "FINALIZED",
        "linh": "STALE",
    }.items():
        path = f"/api/v1/performance/{employees['DEMO-' + person.upper()]}?cycle_id={cycle_id}"
        response = clients[person].get(path)
        assert response.status_code == 200, response.text
        assert response.json()["state"] == state
        if person == "dung":
            assert response.json()["readiness"]["ready"]
            calculated = clients["manager"].post(
                path.split("?")[0] + "/calculate",
                json={
                    "cycle_id": cycle_id,
                    "expected_evidence_version": response.json()["evidence_version"],
                },
            )
            assert calculated.status_code == 201, calculated.text
    an = employees["DEMO-AN"]
    assert clients["manager"].get(f"/api/v1/employees/{an}").status_code == 200
    assert clients["sales.manager"].get(f"/api/v1/employees/{an}").status_code == 404
    assert clients["admin"].get("/api/v1/employees").status_code == 403
    assert clients["admin"].get("/api/v1/users").status_code == 200
    assert clients["hr"].get("/api/v1/users").status_code == 403
    assert clients["binh"].get("/api/v1/feedback-assignments").json()["total"] >= 1
    with Session(world.engine) as session:
        hashes = list(session.scalars(select(User.password_hash).order_by(User.id)))
        feedback_count = session.scalar(select(func.count()).select_from(Feedback))
    assert not seed_demo(world.engine, "a-different-password-must-not-reset")
    with Session(world.engine) as session:
        assert list(session.scalars(select(User.password_hash).order_by(User.id))) == hashes
        assert session.scalar(select(func.count()).select_from(Feedback)) == feedback_count


def test_demo_rolls_back_all_savepoints_after_late_failure(auth_engine, monkeypatch):
    original = DemoBuilder.cycle
    calls = 0

    def fail(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("Simulated failure after creating and closing historical evidence")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(DemoBuilder, "cycle", fail)
    with pytest.raises(RuntimeError, match="Simulated failure"):
        seed_demo(auth_engine, PASSWORD)
    with Session(auth_engine) as session:
        for model in (
            User,
            AuthSession,
            Department,
            Employee,
            ReviewCycle,
            CycleParticipant,
            Feedback,
            PerformanceReview,
            PerformanceReviewRevision,
            AuditLog,
        ):
            assert session.scalar(select(func.count()).select_from(model)) == 0


def test_demo_refuses_reserved_accounts_without_resetting_them(world):
    from app.models import UserRole

    identifier = UUID(world.users["hr"])
    with Session(world.engine) as session, session.begin():
        row = session.get(User, identifier)
        row.email = email("admin")
        row.role = UserRole.HR
        original_hash = row.password_hash
    with pytest.raises(DemoConflict, match="identifiers"):
        seed_demo(world.engine, PASSWORD)
    with Session(world.engine) as session:
        assert session.get(User, identifier).password_hash == original_hash
        assert session.scalar(select(func.count()).select_from(ReviewCycle)) == 0


def test_demo_does_not_replace_an_existing_active_cycle(world):
    from .test_feedback_workflows import feedback_world

    cycle, _ = feedback_world(world)
    with Session(world.engine) as session:
        count = session.scalar(select(func.count()).select_from(User))
    with pytest.raises(DemoConflict, match="ACTIVE cycle"):
        seed_demo(world.engine, PASSWORD)
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(User)) == count
        assert session.get(ReviewCycle, UUID(cycle["id"])).status == CycleStatus.ACTIVE
        assert session.scalar(select(func.count()).select_from(ReviewCycle)) == 1
