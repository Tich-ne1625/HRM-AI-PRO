from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .test_employee_kpis import allocation_world, replace_body


@pytest.mark.parametrize("failure", ["origin", "csrf", "family"])
def test_every_phase4_mutation_checks_origin_csrf_and_live_family(world, failure):
    from app.models import AuditLog, AuthSession

    cycle, first, _second, path = allocation_world(world)
    saved = world.client().put(path, json=replace_body(first)).json()
    cycle_path = "/api/v1/review-cycles/" + cycle["id"]
    cases = [
        (
            "hr",
            "POST",
            "/api/v1/review-cycles",
            {"name": "Unauthorized", "start_date": "2026-01-01", "end_date": "2026-02-01"},
        ),
        ("hr", "PATCH", cycle_path, {"expected_version": 3, "name": "Forbidden"}),
        (
            "hr",
            "POST",
            cycle_path + "/participants",
            {"expected_version": 3, "employee_ids": [world.employees["indirect"]]},
        ),
        (
            "hr",
            "DELETE",
            cycle_path + "/participants/" + saved["participant"]["id"],
            {"expected_version": 3},
        ),
        ("hr", "POST", cycle_path + "/activate", {"expected_version": 3}),
        (
            "hr",
            "POST",
            "/api/v1/kpis",
            {"code": "FORGED", "name": "Forbidden", "unit": "%", "direction": "HIGHER_IS_BETTER"},
        ),
        (
            "hr",
            "PATCH",
            "/api/v1/kpis/" + first["id"],
            {"expected_version": 1, "name": "Forbidden"},
        ),
        ("hr", "PUT", path, replace_body(first, version=3)),
        (
            "hr",
            "PATCH",
            "/api/v1/employee-kpis/" + saved["items"][0]["id"],
            {"expected_evidence_version": 3, "actual": "10.0000"},
        ),
        (
            "admin",
            "PATCH",
            "/api/v1/settings/scoring",
            {"expected_version": 1, "policy": {"kpi_cap": None}},
        ),
    ]
    with Session(world.engine) as session, session.begin():
        before = session.scalar(select(func.count()).select_from(AuditLog))
        if failure == "family":
            session.execute(update(AuthSession).values(revoked_at=datetime.now(UTC)))
    for role, method, url, body in cases:
        headers = (
            {"Origin": "http://evil.example"}
            if failure == "origin"
            else {"X-CSRF-Token": "wrong"}
            if failure == "csrf"
            else {}
        )
        response = world.client(role).request(method, url, json=body, headers=headers)
        assert response.status_code == (401 if failure == "family" else 403), (url, response.text)
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(AuditLog)) == before


def test_forged_evidence_fields_are_rejected_and_audits_do_not_copy_payloads(world):
    from app.models import AuditLog

    _cycle, first, _second, path = allocation_world(world)
    body = replace_body(first)
    for extra in ({"scope": "HR"}, {"snapshot": {}}, {"manager_id": world.employees["other"]}):
        assert world.client().put(path, json={**body, **extra}).status_code == 422
    saved = world.client().put(path, json=body).json()
    world.client().patch(
        "/api/v1/employee-kpis/" + saved["items"][0]["id"],
        json={
            "expected_evidence_version": 3,
            "actual": "10.0000",
        },
    )
    with Session(world.engine) as session:
        audits = list(session.scalars(select(AuditLog)))
        assert any(a.action == "employee_kpi.actual_updated" for a in audits)
        assert all(
            not set(a.metadata_)
            & {
                "snapshot",
                "scoring_policy",
                "password",
                "actual",
                "target",
                "description",
                "name",
                "email",
            }
            for a in audits
        )
