import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.service import AuditWriter


def test_scoring_defaults_admin_only_and_versioned(world):
    admin = world.client("admin")
    first = admin.get("/api/v1/settings/scoring")
    assert first.status_code == 200
    assert first.headers["cache-control"] == "no-store"
    assert first.json()["version"] == 1
    for role in ("hr", "manager", "alice", "unlinked"):
        assert world.client(role).get("/api/v1/settings/scoring").status_code == 403
        assert (
            world.client(role)
            .patch(
                "/api/v1/settings/scoring",
                json={
                    "expected_version": 1,
                    "policy": {},
                },
            )
            .status_code
            == 403
        )
    body = {
        "expected_version": 1,
        "policy": {
            "kpi_weight": "80.00",
            "feedback_weight": "20.00",
            "kpi_cap": None,
        },
    }
    saved = admin.patch("/api/v1/settings/scoring", json=body)
    assert saved.status_code == 200
    assert saved.json()["version"] == 2
    assert saved.json()["policy"]["kpi_weight"] == "80.00"
    assert (
        admin.patch("/api/v1/settings/scoring", json=body).json()["error"]["code"]
        == "stale_version"
    )
    assert (
        admin.patch("/api/v1/settings/scoring", json={**body, "expected_version": 2}).json()[
            "version"
        ]
        == 2
    )


def test_scoring_update_csrf_and_atomic_audit(world, monkeypatch):
    from app.models import AuditLog, SystemConfig

    client = world.client("admin")
    body = {"expected_version": 1, "policy": {"kpi_cap": "150.00"}}
    assert (
        client.patch(
            "/api/v1/settings/scoring", json=body, headers={"Origin": "http://evil.example"}
        ).status_code
        == 403
    )
    assert (
        client.patch(
            "/api/v1/settings/scoring", json=body, headers={"X-CSRF-Token": "wrong"}
        ).status_code
        == 403
    )

    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(AuditWriter, "record", fail)
    assert client.patch("/api/v1/settings/scoring", json=body).status_code == 500
    with Session(world.engine) as session:
        config = session.get(SystemConfig, 1)
        assert config.version == 1
        assert config.scoring_policy["kpi_cap"] == "100.00"
        assert not list(session.scalars(select(AuditLog)))


@pytest.mark.parametrize(
    "policy",
    [
        {"kpi_weight": "60.00"},
        {"kpi_cap": "0.00"},
        {"kpi_cap": "NaN"},
        {"kpi_weight": 70},
        {"kpi_cap": "1.000"},
    ],
)
def test_scoring_invalid_policy_returns_422(world, policy):
    response = world.client("admin").patch(
        "/api/v1/settings/scoring",
        json={
            "expected_version": 1,
            "policy": policy,
        },
    )
    assert response.status_code == 422
