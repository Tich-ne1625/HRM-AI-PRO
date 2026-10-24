"""Bounded read baseline on an explicitly isolated phase9_benchmark_test database.

Run with the API virtualenv and TEST_DATABASE_URL; never reads .env. Setup is not timed.
The API runs in-process via TestClient, PostgreSQL is real; proxy/network costs are excluded.
"""

import argparse
import contextvars
import json
import os
import platform
import statistics
import subprocess
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "apps/api"))


def seed(engine):
    from app.core.database import Base
    from app.core.security import PasswordService
    from app.models import (
        AIAnalysis,
        AnalysisStatus,
        AssignmentStatus,
        AuditLog,
        CycleParticipant,
        CycleStatus,
        Department,
        Employee,
        EmployeeKPI,
        Feedback,
        FeedbackAssignment,
        KPIDefinition,
        KPIDirection,
        PerformanceReview,
        PerformanceReviewRevision,
        Position,
        Relationship,
        ReviewCycle,
        User,
        UserRole,
    )
    from app.modules.ai.schemas import Audience
    from app.modules.performance.engine import ENGINE_VERSION, compute
    from app.modules.performance.evidence import collect
    from app.modules.review_cycles.schemas import ParticipantSnapshot
    from sqlalchemy import inspect
    from sqlalchemy.orm import Session

    assert not inspect(engine).get_table_names(), (
        "Benchmark seed requires an empty dedicated DB"
    )
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    password_hash = PasswordService().hash("phase9-benchmark-fictional-password")
    with Session(engine) as session, session.begin():
        admin = User(
            id=uuid4(),
            email="admin@benchmark.example.com",
            role=UserRole.ADMIN,
            password_hash=password_hash,
        )
        hr = User(
            id=uuid4(),
            email="hr@benchmark.example.com",
            role=UserRole.HR,
            password_hash=password_hash,
        )
        staff_users = [
            User(
                id=uuid4(),
                email=f"person{i}@benchmark.example.com",
                role=UserRole.MANAGER if i < 2 else UserRole.EMPLOYEE,
                password_hash=password_hash,
            )
            for i in range(1000)
        ]
        departments = [
            Department(
                id=uuid4(), code=f"BENCH-{i:02}", name=f"Fictional department {i:02}"
            )
            for i in range(20)
        ]
        position = Position(id=uuid4(), code="BENCH-STAFF", title="Fictional staff")
        session.add_all([admin, hr, position, *staff_users, *departments])
        session.flush()
        employees = [
            Employee(
                id=uuid4(),
                employee_code=f"BENCH-{i:04}",
                display_name=f"Fictional employee {i:04}",
                user_id=user.id,
                department_id=departments[i % 20].id,
                position_id=position.id,
            )
            for i, user in enumerate(staff_users)
        ]
        session.add_all(employees)
        session.flush()
        for i, employee in enumerate(employees[1:], 1):
            employee.manager_id = employees[0 if i <= 500 else 1].id
        policy = {
            "schema_version": 1,
            "kpi_weight": "70.00",
            "feedback_weight": "30.00",
            "kpi_cap": "100.00",
        }
        cycles = [
            ReviewCycle(
                id=uuid4(),
                name=f"Fictional benchmark {year}",
                start_date=date(year, 1, 1),
                end_date=date(year, 12, 31),
                status=status,
                version=2,
                scoring_policy_snapshot=policy,
                policy_source_version=1,
                activated_at=now,
            )
            for year, status in ((2025, CycleStatus.CLOSED), (2026, CycleStatus.ACTIVE))
        ]
        definitions = [
            KPIDefinition(
                id=uuid4(),
                code=f"BENCH-KPI-{i}",
                name=f"Fictional target {i}",
                description="Benchmark only",
                unit="units",
                direction=KPIDirection.HIGHER_IS_BETTER,
                version=1,
            )
            for i in range(5)
        ]
        session.add_all([*cycles, *definitions])
        session.flush()
        by_id = {e.id: e for e in employees}
        peers = defaultdict(list)
        for e in employees[1:]:
            peers[e.manager_id].append(e)
        participants = []
        for cycle in cycles:
            for employee in employees[1:]:
                manager = by_id[employee.manager_id]
                dept = departments[employees.index(employee) % 20]
                snapshot = ParticipantSnapshot(
                    employee_id=employee.id,
                    user_id=employee.user_id,
                    employee_code=employee.employee_code,
                    display_name=employee.display_name,
                    department_id=dept.id,
                    department_code=dept.code,
                    department_name=dept.name,
                    position_id=position.id,
                    position_code=position.code,
                    position_title=position.title,
                    manager_id=manager.id,
                    manager_user_id=manager.user_id,
                    manager_display_name=manager.display_name,
                    direct_reports=[
                        {
                            "employee_id": e.id,
                            "user_id": e.user_id,
                            "employment_status": "ACTIVE",
                        }
                        for e in employees
                        if e.manager_id == employee.id
                    ],
                )
                p = CycleParticipant(
                    id=uuid4(),
                    cycle_id=cycle.id,
                    employee_id=employee.id,
                    evidence_version=1,
                    snapshot=snapshot.model_dump(mode="json"),
                    finalized_at=now if cycle.status == CycleStatus.CLOSED else None,
                )
                participants.append((p, employee, cycle))
                session.add(p)
        session.flush()
        for p, employee, _ in participants:
            for d in definitions:
                snapshot = {
                    "schema_version": 1,
                    "version": 1,
                    "code": d.code,
                    "name": d.name,
                    "description": d.description,
                    "unit": d.unit,
                    "direction": d.direction.value,
                }
                session.add(
                    EmployeeKPI(
                        id=uuid4(),
                        participant_id=p.id,
                        definition_id=d.id,
                        definition_snapshot=snapshot,
                        target=Decimal("100.0000"),
                        actual=Decimal("90.0000"),
                        weight=Decimal("20.00"),
                    )
                )
            group = peers[employee.manager_id]
            peer = group[(group.index(employee) + 1) % len(group)]
            for relationship, reviewer in (
                (Relationship.SELF, employee),
                (Relationship.MANAGER, by_id[employee.manager_id]),
                (Relationship.PEER, peer),
            ):
                assignment = FeedbackAssignment(
                    id=uuid4(),
                    participant_id=p.id,
                    reviewer_id=reviewer.user_id,
                    reviewer_employee_id=reviewer.id,
                    relationship=relationship,
                    required=relationship != Relationship.PEER,
                    status=AssignmentStatus.SUBMITTED,
                    version=1,
                    eligibility_snapshot={
                        "schema_version": 1,
                        "rule_version": 1,
                        "source": "BENCHMARK",
                    },
                )
                session.add(assignment)
                session.flush()
                session.add(
                    Feedback(
                        id=uuid4(),
                        assignment_id=assignment.id,
                        rating=4,
                        comment="Fictional benchmark feedback",
                        submitted_at=now,
                    )
                )
        session.flush()
        reviews = []
        revisions = []
        for index, (p, employee, cycle) in enumerate(participants):
            evidence = collect(session, p, employee, cycle)
            assert evidence.readiness.ready, str(evidence.readiness)
            scores = compute(
                evidence.snapshot["items"], evidence.ratings, evidence.policy
            )
            values = dict(
                calculation_version=1,
                evidence_version=1,
                engine_version=ENGINE_VERSION,
                evidence_hash=evidence.digest,
                calculated_at=now,
                policy_snapshot=evidence.policy,
                evidence_snapshot={**evidence.snapshot, "results": scores["items"]},
                **{
                    key: Decimal(scores[key])
                    for key in ("kpi_score", "feedback_score", "final_score")
                },
            )
            review = PerformanceReview(
                id=uuid4(), participant_id=p.id, finalized_at=p.finalized_at, **values
            )
            reviews.append(review)
            revisions.append(
                PerformanceReviewRevision(id=uuid4(), review_id=review.id, **values)
            )
            if index % 500 == 0:
                print(json.dumps({"prepared_reviews": index}), flush=True)
        session.add_all(reviews)
        session.flush()
        session.add_all(revisions)
        session.flush()
        for review in reviews:
            session.add(
                AuditLog(
                    action="performance.calculated",
                    entity_type="performance_review",
                    entity_id=str(review.id),
                    request_id="benchmark-fixture",
                    metadata_={},
                )
            )
            for audience in (Audience.PUBLIC, Audience.HR_PRIVATE):
                session.add(
                    AIAnalysis(
                        id=uuid4(),
                        review_id=review.id,
                        audience=audience,
                        status=AnalysisStatus.SUCCEEDED,
                        generation_version=1,
                        calculation_version=1,
                        evidence_version=1,
                        engine_version=ENGINE_VERSION,
                        evidence_hash=review.evidence_hash,
                        input_hash="b" * 64,
                        prompt_version="1",
                        redaction_version="1",
                        schema_version="1",
                        model="OFFLINE-BENCHMARK",
                        actual_model="OFFLINE-BENCHMARK",
                        requested_by=hr.id,
                        client_request_id=uuid4(),
                        request_fingerprint="c" * 64,
                        reserved_at=now,
                        lease_until=now + timedelta(seconds=60),
                        fencing_token=uuid4(),
                        completed_at=now + timedelta(seconds=1),
                        generated_at=now + timedelta(seconds=1),
                        input_sampled=False,
                        output={
                            "summary": "OFFLINE BENCHMARK, not live Gemini",
                            "strengths": [],
                            "improvement_areas": [],
                            "feedback_themes": [],
                            "recommended_actions": [],
                            "caveats": ["Fictional fixture"],
                        },
                    )
                )
        for user in [admin, hr, *staff_users]:
            session.add(
                AuditLog(
                    action="user.created",
                    entity_type="user",
                    entity_id=str(user.id),
                    request_id="benchmark-fixture",
                    metadata_={},
                )
            )
    print("Fictional benchmark dataset committed", flush=True)


def main():
    os.chdir(ROOT / "apps/api")
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    os.environ["APP_ENV"] = "test"
    os.environ["GEMINI_ENABLED"] = "false"
    os.environ["AUTH_ACCESS_SECRET"] = "phase9-benchmark-only-signing-key-32-chars"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--clients", type=int, default=5)
    parser.add_argument("--seed-only", action="store_true")
    args = parser.parse_args()
    assert 1 <= args.seconds <= 120 and 1 <= args.clients <= 5
    from app.core.config import Settings
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, event, func, select
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session
    from starlette.datastructures import MutableHeaders

    Settings.model_config["env_file"] = (
        None  # Test process only; never load a user's .env.
    )
    from app.core.database import get_session_factory
    from app.main import create_app
    from app.models import (
        AIAnalysis,
        AuditLog,
        CycleParticipant,
        Department,
        Employee,
        EmployeeKPI,
        Feedback,
        ReviewCycle,
    )

    url = os.environ["TEST_DATABASE_URL"]
    assert make_url(url).database == "phase9_benchmark_test", (
        "Only the dedicated benchmark DB is allowed"
    )
    engine = create_engine(url, pool_pre_ping=True)
    if args.seed:
        seed(engine)
    if args.seed_only:
        engine.dispose()
        return
    settings = Settings(
        _env_file=None,
        database_url=url,
        app_env="test",
        web_origin="http://testserver",
        access_signing_key="phase9-benchmark-only-signing-key-32-chars",
        gemini_enabled=False,
    )
    app = create_app(settings)
    app.state.engine.dispose()
    app.state.engine = engine
    app.state.session_factory = get_session_factory(engine)
    statements = contextvars.ContextVar("benchmark_queries", default=None)

    def count(*_):
        current = statements.get()
        if current is not None:
            current.append(1)

    event.listen(engine, "before_cursor_execute", count)

    class CountedApp:
        async def __call__(self, scope, receive, send):
            queries = []
            token = statements.set(queries)

            async def counted(message):
                if message["type"] == "http.response.start":
                    MutableHeaders(scope=message)["X-Benchmark-SQL-Count"] = str(
                        len(queries)
                    )
                await send(message)

            try:
                await app(scope, receive, counted)
            finally:
                statements.reset(token)

    wrapped = CountedApp()
    cookies = {}
    for role, email in (
        ("ADMIN", "admin"),
        ("HR", "hr"),
        ("MANAGER", "person0"),
        ("EMPLOYEE", "person2"),
    ):
        client = TestClient(wrapped, headers={"Origin": "http://testserver"})
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": email + "@benchmark.example.com",
                "password": "phase9-benchmark-fictional-password",
            },
        )
        assert response.status_code == 200, response.status_code
        cookies[role] = dict(client.cookies)
    with Session(engine) as session:
        active = session.scalar(
            select(ReviewCycle.id).where(ReviewCycle.status == "ACTIVE")
        )
        closed = session.scalar(
            select(ReviewCycle.id).where(ReviewCycle.status == "CLOSED")
        )
        counts = {
            model.__tablename__: session.scalar(select(func.count()).select_from(model))
            for model in (
                Employee,
                Department,
                ReviewCycle,
                CycleParticipant,
                EmployeeKPI,
                Feedback,
                AIAnalysis,
                AuditLog,
            )
        }
    scenarios = [
        ("hr-dashboard", "HR", f"/api/v1/dashboard?cycle_id={active}"),
        ("hr-closed", "HR", f"/api/v1/dashboard?cycle_id={closed}"),
        ("manager-dashboard", "MANAGER", f"/api/v1/dashboard?cycle_id={active}"),
        ("employee-dashboard", "EMPLOYEE", f"/api/v1/dashboard?cycle_id={active}"),
        ("hr-ai-first", "HR", "/api/v1/ai-reports"),
        ("hr-ai-page10", "HR", "/api/v1/ai-reports?page=10"),
        ("hr-private", "HR", "/api/v1/ai-reports?audience=HR_PRIVATE"),
        ("manager-ai", "MANAGER", "/api/v1/ai-reports"),
        ("employee-ai", "EMPLOYEE", "/api/v1/ai-reports"),
        ("admin-audit", "ADMIN", "/api/v1/audit-logs"),
        ("hr-audit-page10", "HR", "/api/v1/audit-logs?page=10"),
    ]

    def read(client, scenario):
        name, role, path = scenario
        client.cookies.clear()
        client.cookies.update(cookies[role])
        started = time.perf_counter()
        response = client.get(path)
        elapsed = (time.perf_counter() - started) * 1000
        assert response.status_code == 200, (name, response.status_code)
        data = response.json()
        sql = int(response.headers["X-Benchmark-SQL-Count"])
        assert sql <= 15, (name, sql)
        if "dashboard" in name or name == "hr-closed":
            assert data["average"] == "87.00" and data["sample_size"] > 0
            if role == "EMPLOYEE":
                assert data["sample_size"] == 1
            if role == "HR":
                assert data["sample_size"] == 999
        else:
            assert len(data["items"]) <= 20
            assert "output" not in str(data)
            if role == "EMPLOYEE":
                assert data["total"] == 2
            if "audit" not in name:
                assert all(
                    r["audience"] == ("HR_PRIVATE" if "private" in name else "PUBLIC")
                    for r in data["items"]
                )
        return name, elapsed, sql

    warm = TestClient(wrapped)
    for scenario in scenarios:
        read(warm, scenario)
    deadline = time.monotonic() + args.seconds

    def worker(number):
        client = TestClient(wrapped)
        rows = []
        i = number
        while time.monotonic() < deadline:
            rows.append(read(client, scenarios[i % len(scenarios)]))
            i += 1
        return rows

    with ThreadPoolExecutor(max_workers=args.clients) as pool:
        rows = [row for batch in pool.map(worker, range(args.clients)) for row in batch]
    grouped = defaultdict(list)
    for name, elapsed, sql in rows:
        grouped[name].append((elapsed, sql))
    report = {
        "fixture": "fictional, exact scoring/evidence collected before measurement; no Gemini",
        "scope": "in-process TestClient API + real PostgreSQL; excludes proxy/network/browser",
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "logical_cpus": os.cpu_count(),
        "seconds": args.seconds,
        "clients": args.clients,
        "errors": 0,
        "counts": counts,
        "requests": len(rows),
        "scenarios": {},
    }
    for name, values in grouped.items():
        latency = sorted(v[0] for v in values)
        report["scenarios"][name] = {
            "requests": len(values),
            "p50_ms": round(statistics.median(latency), 2),
            "p95_ms": round(
                latency[min(len(latency) - 1, int(len(latency) * 0.95))], 2
            ),
            "max_ms": round(max(latency), 2),
            "max_sql_queries": max(v[1] for v in values),
        }
    out = ROOT / ".superpowers/sdd/phase-9"
    out.mkdir(parents=True, exist_ok=True)
    (out / "benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report), flush=True)
    engine.dispose()


if __name__ == "__main__":
    main()
