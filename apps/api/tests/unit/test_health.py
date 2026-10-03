from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.modules.health.router import get_readiness_service
from app.modules.health.service import ReadinessResult


@dataclass
class FakeReadinessService:
    result: ReadinessResult
    calls: int = 0

    def check(self) -> ReadinessResult:
        self.calls += 1
        return self.result


def test_liveness_does_not_check_dependencies() -> None:
    service = FakeReadinessService(ReadinessResult.ready())
    client = _client(service)

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api"}
    assert service.calls == 0


def test_readiness_reports_current_database_and_migrations() -> None:
    service = FakeReadinessService(ReadinessResult.ready())
    client = _client(service)

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"database": "ok", "migrations": "current"},
    }
    assert service.calls == 1


def test_database_failure_is_sanitized_and_liveness_stays_available() -> None:
    service = FakeReadinessService(
        ReadinessResult.not_ready(database="unavailable", migrations="unavailable")
    )
    client = _client(service)

    readiness = client.get("/health/ready")
    liveness = client.get("/health/live")

    assert readiness.status_code == 503
    assert readiness.json()["error"] == {
        "code": "service_not_ready",
        "message": "Service dependencies are not ready",
        "details": [
            {"check": "database", "status": "unavailable"},
            {"check": "migrations", "status": "unavailable"},
        ],
    }
    assert "password" not in readiness.text.lower()
    assert liveness.status_code == 200


def test_migration_mismatch_is_not_ready() -> None:
    service = FakeReadinessService(
        ReadinessResult.not_ready(database="ok", migrations="pending")
    )
    client = _client(service)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["error"]["details"] == [
        {"check": "database", "status": "ok"},
        {"check": "migrations", "status": "pending"},
    ]


def _client(service: FakeReadinessService) -> TestClient:
    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://user:password@localhost/test",
    )
    app = create_app(settings)
    app.dependency_overrides[get_readiness_service] = lambda: service
    return TestClient(app)

