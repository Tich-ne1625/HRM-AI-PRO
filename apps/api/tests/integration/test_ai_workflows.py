from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.ai.models import AIAnalysis
from app.modules.ai.provider import ProviderError, ProviderResult
from app.modules.ai.schemas import AnalysisOutput
from app.modules.audit.models import AuditLog

from .test_performance import calculate, ready_world


class FakeProvider:
    def __init__(self):
        self.calls = []
        self.error = None
        self.hook = None

    def generate(self, payload):
        self.calls.append(payload)
        if self.hook:
            self.hook()
        if self.error:
            raise ProviderError(self.error)
        return ProviderResult(
            AnalysisOutput(
                summary="Private sentinel" if payload["audience"] == "HR_PRIVATE" else "Advice",
                strengths=["Strength"],
                improvement_areas=[],
                feedback_themes=[],
                recommended_actions=["Discuss goals"],
                caveats=["Advisory only"],
            ),
            "test-model",
        )


@pytest.fixture
def ai_world(world, monkeypatch):
    monkeypatch.setattr("app.modules.ai.service.COOLDOWN_SECONDS", 0)
    settings = world.app.state.settings
    settings.gemini_enabled = True
    settings.gemini_api_key = SecretStr("offline-test-key")
    settings.gemini_model = "test-model"
    provider = FakeProvider()
    world.app.state.ai_provider = provider
    cycle, participant, item, base = ready_world(world)
    response = calculate(world, cycle, participant, base)
    assert response.status_code == 201, response.text
    report = response.json()
    path = f"/api/v1/performance/{report['review_id']}/ai-analysis"
    body = {
        "client_request_id": str(uuid4()),
        "expected_calculation_version": report["current_result"]["calculation_version"],
        "expected_evidence_version": report["evidence_version"],
    }
    return world, provider, report, path, body, item


def test_public_private_scope_replay_and_read_only_gets(ai_world):
    world, provider, report, path, body, _ = ai_world
    assert world.client().get(path).json()["state"] == "NOT_GENERATED"
    assert not provider.calls
    first = world.client().post(path, json=body)
    assert first.status_code == 201, first.text
    public = first.json()
    assert world.client().post(path, json=body).json()["id"] == public["id"]
    assert (
        world.client().post(path, json={**body, "client_request_id": str(uuid4())}).status_code
        == 200
    )
    assert len(provider.calls) == 1
    private = world.client().post(
        path,
        json={
            **body,
            "client_request_id": str(uuid4()),
            "audience": "HR_PRIVATE",
        },
    )
    assert private.status_code == 201, private.text
    history = f"/api/v1/reviews/{report['review_id']}/ai-analyses"
    for role in ("alice", "manager"):
        assert world.client(role).get(path).json()["current_analysis"]["id"] == public["id"]
        assert "Private sentinel" not in world.client(role).get(history).text
        assert world.client(role).get(history + "/" + private.json()["id"]).status_code == 404
        assert world.client(role).get(path + "?audience=HR_PRIVATE").status_code == 403
        assert world.client(role).post(path, json=body).status_code == 403
    assert world.client("other").get(path).status_code == 404
    assert world.client("admin").get(path).status_code == 403
    assert world.client().get(history + "?audience=HR_PRIVATE").json()["total"] == 1
    assert len(provider.calls) == 2
    assert "comments" not in str(provider.calls[0])
    assert "@example.com" not in str(provider.calls)
    assert "requested_by" not in first.text and "input_hash" not in first.text


def test_failed_regeneration_preserves_success_and_sanitizes_errors(ai_world):
    world, provider, _, path, body, _ = ai_world
    first = world.client().post(path, json=body)
    assert first.status_code == 201, first.text
    provider.error = "provider_timeout"
    regen = {
        **body,
        "client_request_id": str(uuid4()),
        "regenerate": True,
        "expected_latest_generation": 1,
    }
    failed = world.client().post(path, json=regen)
    assert failed.status_code == 504, failed.text
    state = world.client().get(path).json()
    assert state["current_analysis"]["id"] == first.json()["id"]
    assert state["latest_attempt"]["status"] == "FAILED"
    replay = world.client().post(path, json=regen)
    assert replay.status_code == 200 and replay.json()["status"] == "FAILED"
    assert len(provider.calls) == 2
    with Session(world.engine) as session:
        logs = session.scalars(select(AuditLog).where(AuditLog.action.like("ai_analysis.%"))).all()
        assert len(logs) == 4
        assert "Advice" not in str([log.metadata_ for log in logs])


def test_conflicts_keyless_and_csrf_make_no_provider_calls(ai_world):
    world, provider, _, path, body, _ = ai_world
    client = world.client()
    client.headers["X-CSRF-Token"] = "wrong"
    assert client.post(path, json=body).status_code == 403
    assert (
        world.client().post(path, json={**body, "expected_evidence_version": 999}).status_code
        == 409
    )
    world.app.state.settings.gemini_enabled = False
    assert world.client().post(path, json=body).status_code == 503
    assert not provider.calls
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(AIAnalysis)) == 0


def test_provider_runs_without_database_locks_and_stale_output_is_discarded(ai_world):
    world, provider, _, path, body, item = ai_world

    def mutate():
        assert world.engine.pool.checkedout() == 0
        # A real competing domain write must finish during the provider call.
        changed = world.client().patch(
            f"/api/v1/employee-kpis/{item['id']}",
            json={
                "expected_evidence_version": body["expected_evidence_version"],
                "actual": "70.0000",
            },
        )
        assert changed.status_code == 200, changed.text

    provider.hook = mutate
    response = world.client().post(path, json=body)
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "analysis_stale"
    with Session(world.engine) as session:
        row = session.scalars(select(AIAnalysis)).one()
        assert row.status == "FAILED" and row.output is None


def test_completion_rechecks_account_authority(ai_world):
    from app.modules.users.models import User

    world, provider, _, path, body, _ = ai_world

    def revoke():
        with Session(world.engine) as session, session.begin():
            session.get(User, UUID(world.users["hr"])).is_active = False

    provider.hook = revoke
    response = world.client().post(path, json=body)
    assert response.status_code in (401, 403), response.text
    assert "Advice" not in response.text
    with Session(world.engine) as session:
        row = session.scalars(select(AIAnalysis)).one()
        assert row.status == "FAILED" and row.output is None


def test_inflight_replay_global_lease_and_fenced_recovery(ai_world):
    from concurrent.futures import ThreadPoolExecutor
    from datetime import timedelta
    from threading import Event

    world, provider, _, path, body, _ = ai_world
    started, release = Event(), Event()

    def wait():
        started.set()
        assert release.wait(15)

    provider.hook = wait
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(lambda: world.client().post(path, json=body))
        try:
            assert started.wait(10)
            assert world.client().post(path, json=body).status_code == 202
            other = {**body, "client_request_id": str(uuid4()), "audience": "HR_PRIVATE"}
            blocked = world.client().post(path, json=other)
            assert blocked.status_code == 409, blocked.text
            assert len(provider.calls) == 1
            with Session(world.engine) as session, session.begin():
                row = session.scalars(select(AIAnalysis)).one()
                row.reserved_at -= timedelta(seconds=120)
                row.lease_until -= timedelta(seconds=120)
            expired = world.client().get(path).json()["latest_attempt"]
            assert expired["error_code"] == "generation_expired"
            # GET only derives expiry and never mutates the attempt.
            with Session(world.engine) as session:
                assert session.scalars(select(AIAnalysis)).one().status == "RUNNING"
            provider.hook = None
            replacement = world.client().post(path, json=other)
            assert replacement.status_code == 201, replacement.text
        finally:
            release.set()
        old = future.result(timeout=10)
        assert old.status_code == 409, old.text
    with Session(world.engine) as session:
        rows = session.scalars(select(AIAnalysis).order_by(AIAnalysis.reserved_at)).all()
        assert [row.status for row in rows] == ["FAILED", "SUCCEEDED"]
        assert rows[0].output is None


@pytest.mark.parametrize(
    "clause",
    [
        "generation_version=0",
        "evidence_hash='bad'",
        "audience='UNKNOWN'",
        "output='[]'::jsonb",
        "generated_at=NULL",
        "completed_at=NULL",
        "error_code='bad'",
        "lease_until=reserved_at",
        "calculation_version=999",
        "requested_by='00000000-0000-0000-0000-000000000000'",
    ],
)
def test_database_rejects_invalid_analysis_states(ai_world, clause):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    world, _, _, path, body, _ = ai_world
    response = world.client().post(path, json=body)
    assert response.status_code == 201, response.text
    with pytest.raises(IntegrityError), world.engine.begin() as connection:
        connection.execute(text(f"UPDATE ai_analyses SET {clause}"))


def test_ai_migration_roundtrip_preserves_existing_evidence(ai_world):
    from alembic.config import Config

    from alembic import command
    from app.modules.performance.models import PerformanceReviewRevision

    from .conftest import ALEMBIC_INI

    world, _, _, path, body, _ = ai_world
    assert world.client().post(path, json=body).status_code == 201
    with Session(world.engine) as session:
        revision = session.scalars(select(PerformanceReviewRevision)).one()
        before = (revision.evidence_hash, revision.final_score, revision.evidence_snapshot)
    config = Config(str(ALEMBIC_INI))
    command.check(config)
    command.downgrade(config, "20261022_0006")
    command.upgrade(config, "head")
    with Session(world.engine) as session:
        revision = session.scalars(select(PerformanceReviewRevision)).one()
        assert before == (revision.evidence_hash, revision.final_score, revision.evidence_snapshot)
        assert session.scalar(select(func.count()).select_from(AIAnalysis)) == 0


def test_cooldown_idempotency_conflict_and_regeneration_cas(ai_world, monkeypatch):
    world, provider, _, path, body, _ = ai_world
    assert world.client().post(path, json=body).status_code == 201
    assert world.client().post(path, json={**body, "audience": "HR_PRIVATE"}).status_code == 409
    regen = {
        **body,
        "client_request_id": str(uuid4()),
        "regenerate": True,
        "expected_latest_generation": 0,
    }
    assert world.client().post(path, json=regen).json()["error"]["code"] == "stale_analysis_version"
    regen["expected_latest_generation"] = 1
    monkeypatch.setattr("app.modules.ai.service.COOLDOWN_SECONDS", 30)
    assert world.client().post(path, json=regen).status_code == 429
    assert len(provider.calls) == 1


@pytest.mark.parametrize("stage", ["requested", "succeeded"])
def test_audit_failure_rolls_back_its_transaction(ai_world, monkeypatch, stage):
    from app.modules.audit.service import AuditWriter

    world, provider, _, path, body, _ = ai_world
    original = AuditWriter.record

    def failing(self, *args, **kwargs):
        if args[2] == "ai_analysis." + stage:
            raise RuntimeError("offline audit failure")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(AuditWriter, "record", failing)
    response = world.client().post(path, json=body)
    assert response.status_code == 500
    with Session(world.engine) as session:
        rows = session.scalars(select(AIAnalysis)).all()
        if stage == "requested":
            assert rows == [] and provider.calls == []
        else:
            assert len(provider.calls) == 1
            assert len(rows) == 1 and rows[0].status == "RUNNING" and rows[0].output is None


def test_finalize_and_close_during_provider_preserve_versions(ai_world):
    from app.modules.performance.models import PerformanceReviewRevision

    from .test_performance import finalize_body

    world, provider, report, path, body, _ = ai_world

    def close():
        finalized = world.client().post(
            f"/api/v1/reviews/{report['review_id']}/finalize", json=finalize_body(report)
        )
        assert finalized.status_code == 200, finalized.text
        closed = world.client().post(
            f"/api/v1/review-cycles/{report['cycle_id']}/close",
            json={"expected_version": finalized.json()["cycle_version"]},
        )
        assert closed.status_code == 200, closed.text

    provider.hook = close
    response = world.client().post(path, json=body)
    assert response.status_code == 201, response.text
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(PerformanceReviewRevision)) == 1
    provider.hook = None
    assert (
        world.client()
        .post(path, json={**body, "client_request_id": str(uuid4()), "audience": "HR_PRIVATE"})
        .status_code
        == 201
    )
