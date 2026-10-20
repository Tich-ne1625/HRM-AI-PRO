from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import text


def race(monkeypatch, *calls):
    from app.modules.organization.repository import OrganizationRepository

    barrier = Barrier(len(calls))
    original = OrganizationRepository.lock_guard

    def acquire(self):
        self.session.execute(text("SET LOCAL lock_timeout = '8s'"))
        if not self.session.info.get("race_entered"):
            self.session.info["race_entered"] = True
            barrier.wait(timeout=15)
        return original(self)

    monkeypatch.setattr(OrganizationRepository, "lock_guard", acquire)
    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        futures = [pool.submit(call) for call in calls]
        return [future.result(timeout=25) for future in futures]


def test_concurrent_scoring_versions_have_one_winner(world, monkeypatch):
    def save(cap):
        return world.client("admin").patch(
            "/api/v1/settings/scoring",
            json={
                "expected_version": 1,
                "policy": {"kpi_cap": cap},
            },
        )

    responses = race(monkeypatch, lambda: save("120.00"), lambda: save("150.00"))
    assert sorted(r.status_code for r in responses) == [200, 409]
    assert world.client("admin").get("/api/v1/settings/scoring").json()["version"] == 2


def test_concurrent_definition_codes_have_one_winner(world, monkeypatch):
    from .test_kpi_definitions import definition

    def create():
        return world.client().post("/api/v1/kpis", json=definition())

    responses = race(monkeypatch, create, create)
    assert sorted(r.status_code for r in responses) == [201, 409]


def test_concurrent_definition_versions_have_one_winner(world, monkeypatch):
    from .test_kpi_definitions import definition

    row = world.client().post("/api/v1/kpis", json=definition()).json()

    def save(name):
        return world.client().patch(
            f"/api/v1/kpis/{row['id']}",
            json={
                "expected_version": 1,
                "name": name,
            },
        )

    responses = race(monkeypatch, lambda: save("First"), lambda: save("Second"))
    assert sorted(r.status_code for r in responses) == [200, 409]
