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
    assert services["postgres"]["environment"]["POSTGRES_PASSWORD"] == (
        "${POSTGRES_PASSWORD:-change-me@local-only}"
    )

    assert services["migrate"]["depends_on"]["postgres"]["condition"] == "service_healthy"
    assert services["migrate"]["command"] == ["alembic", "upgrade", "head"]
    assert services["migrate"]["image"] == services["api"]["image"] == "insighthr-api:local"
    assert "POSTGRES_PASSWORD_URLENCODED" in services["migrate"]["environment"][
        "DATABASE_URL"
    ]
    assert services["api"]["depends_on"]["migrate"]["condition"] == (
        "service_completed_successfully"
    )
    assert services["api"]["environment"]["ALEMBIC_CONFIG_PATH"] == (
        "/app/alembic.ini"
    )
    assert services["api"]["healthcheck"]["test"][-1].endswith("/health/ready')")
    assert services["web"]["depends_on"]["api"]["condition"] == "service_healthy"


def test_application_containers_are_immutable_and_nonroot() -> None:
    services = _compose()["services"]

    for service_name in ("migrate", "api", "web"):
        service = services[service_name]
        assert service["user"] == "10001:10001"
        assert "volumes" not in service


def test_build_context_excludes_nested_environment_files() -> None:
    dockerignore = (REPOSITORY_ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert "**/.env" in dockerignore.splitlines()
    assert "**/.env.*" in dockerignore.splitlines()


def test_api_image_resolves_runtime_dependencies_with_lock_constraints() -> None:
    dockerfile = (
        REPOSITORY_ROOT / "infrastructure" / "docker" / "api.Dockerfile"
    ).read_text(encoding="utf-8")

    assert "COPY apps/api/pyproject.toml apps/api/requirements.lock ./" in dockerfile
    assert "--constraint requirements.lock" in dockerfile


def test_ci_verifies_restart_persistence_and_final_image_contents() -> None:
    workflow = (
        REPOSITORY_ROOT / ".github" / "workflows" / "phase1-ci.yml"
    ).read_text(encoding="utf-8")

    assert "Verify persistence across normal restart" in workflow
    assert 'SELECT version_num FROM alembic_version' in workflow
    restart_step = workflow.index("Verify persistence across normal restart")
    shutdown = workflow.index("down", restart_step)
    postgres_only_start = workflow.index(
        "up --detach --wait --no-build postgres",
        shutdown,
    )
    revision_after_restart = workflow.index("revision_after_restart", shutdown)
    full_stack_restart = workflow.index(
        "up --detach --wait --no-build\n",
        postgres_only_start,
    )
    assert postgres_only_start < revision_after_restart < full_stack_restart
    assert "Inspect final images" in workflow


def _compose() -> dict[str, Any]:
    with (REPOSITORY_ROOT / "docker-compose.yml").open(encoding="utf-8") as compose_file:
        parsed = yaml.safe_load(compose_file)
    assert isinstance(parsed, dict)
    return parsed

