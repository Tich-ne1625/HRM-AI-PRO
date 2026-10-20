from .test_kpi_concurrency import race
from .test_review_cycles import draft, enroll


def test_concurrent_enrollment_uses_cycle_version(world, monkeypatch):
    cycle = draft(world)

    def add(name):
        return world.client().post(
            f"/api/v1/review-cycles/{cycle['id']}/participants",
            json={
                "expected_version": 1,
                "employee_ids": [world.employees[name]],
            },
        )

    responses = race(monkeypatch, lambda: add("alice"), lambda: add("bob"))
    assert sorted(r.status_code for r in responses) == [200, 409]
    current = world.client().get(f"/api/v1/review-cycles/{cycle['id']}").json()
    assert current["version"] == 2 and current["participant_count"] == 1


def test_concurrent_removal_and_metadata_do_not_lose_changes(world, monkeypatch):
    cycle = enroll(world, draft(world), "alice")
    path = f"/api/v1/review-cycles/{cycle['id']}"
    participant = world.client().get(f"{path}/participants").json()["items"][0]
    responses = race(
        monkeypatch,
        lambda: world.client().request(
            "DELETE", f"{path}/participants/{participant['id']}", json={"expected_version": 2}
        ),
        lambda: world.client().patch(path, json={"expected_version": 2, "name": "Renamed"}),
    )
    assert sorted(r.status_code for r in responses) == [200, 409]
    assert world.client().get(path).json()["version"] == 3
