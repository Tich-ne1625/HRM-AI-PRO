from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def test_compose_service_dependency_and_persistence_contract() -> None:
    compose = _compose()
    services = compose["services"]

    assert set(services) == {"postgres", "migrate", "api", "web"}
    assert "healthcheck" in services["postgres"]
    assert "postgres_data:/var/lib/postgresql/data" in services["postgres"]["volumes"]
    assert "postgres_data" in compose["volumes"]

    assert services["migrate"]["depends_on"]["postgres"]["condition"] == "service_healthy"
    assert services["migrate"]["command"] == ["alembic", "upgrade", "head"]
    assert services["migrate"]["image"] == services["api"]["image"] == "insighthr-api:local"
    assert services["api"]["depends_on"]["migrate"]["condition"] == (
        "service_completed_successfully"
    )
    assert services["api"]["healthcheck"]["test"][-1].endswith("/health/ready')")
    assert services["web"]["depends_on"]["api"]["condition"] == "service_healthy"


def test_application_containers_are_immutable_and_nonroot() -> None:
    services = _compose()["services"]

    for service_name in ("migrate", "api", "web"):
        service = services[service_name]
        assert service["user"] == "10001:10001"
        assert "volumes" not in service


def _compose() -> dict[str, Any]:
    with (REPOSITORY_ROOT / "docker-compose.yml").open(encoding="utf-8") as compose_file:
        parsed = yaml.safe_load(compose_file)
    assert isinstance(parsed, dict)
    return parsed

