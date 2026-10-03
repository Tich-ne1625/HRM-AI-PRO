from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_unknown_route_uses_stable_error_envelope() -> None:
    app = create_app(_test_settings())

    response = TestClient(app).get("/missing")

    assert response.status_code == 404
    assert set(response.json()) == {"error", "request_id"}
    assert response.json()["error"] == {
        "code": "not_found",
        "message": "Not Found",
        "details": [],
    }
    assert response.json()["request_id"]
    assert response.headers["x-request-id"] == response.json()["request_id"]


def test_unexpected_exception_is_sanitized() -> None:
    app = create_app(_test_settings())

    @app.get("/explode")
    def explode() -> None:
        raise RuntimeError("database-password-must-not-leak")

    response = TestClient(app, raise_server_exceptions=False).get("/explode")

    assert response.status_code == 500
    assert response.json()["error"] == {
        "code": "internal_server_error",
        "message": "An unexpected error occurred",
        "details": [],
    }
    assert "database-password-must-not-leak" not in response.text


def _test_settings() -> Settings:
    return Settings(
        app_env="test",
        database_url="postgresql+psycopg://user:password@localhost/test",
    )

