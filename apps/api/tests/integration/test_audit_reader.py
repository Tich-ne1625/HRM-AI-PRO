from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditLog
from app.modules.audit.router import ADMIN_EVENTS, HR_EVENTS


def test_audit_exact_allowlist_projection_and_pagination(world):
    with Session(world.engine) as session, session.begin():
        for action, entity in sorted(ADMIN_EVENTS | HR_EVENTS):
            session.add(
                AuditLog(
                    action=action,
                    entity_type=entity,
                    entity_id=str(uuid4()),
                    request_id="SECRET_REQUEST",
                    metadata_={"secret": "SECRET_METADATA"},
                )
            )
        for action, entity in (
            ("user.created", "ai_analysis"),
            ("auth.login_failed", "user"),
            ("ai_analysis.completed", "ai_analysis"),
            ("employee.created", "user"),
        ):
            session.add(
                AuditLog(
                    action=action,
                    entity_type=entity,
                    entity_id="unknown",
                    request_id="SECRET_REQUEST",
                    metadata_={},
                )
            )
    with Session(world.engine) as session:
        before = session.scalar(select(func.count()).select_from(AuditLog))
    for role, events in (("admin", ADMIN_EVENTS), ("hr", HR_EVENTS)):
        client = world.client(role)
        response = client.get("/api/v1/audit-logs?page_size=2")
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["total"] == len(events)
        first = response.json()["items"]
        second = client.get("/api/v1/audit-logs?page_size=2&page=2").json()["items"]
        assert not ({r["id"] for r in first} & {r["id"] for r in second})
        for row in first + second:
            assert set(row) == {"id", "action", "entity_type", "entity_id", "created_at"}
            assert (row["action"], row["entity_type"]) in events
        assert "SECRET" not in response.text
        for action in ("unknown.event", "ai_analysis.completed", "auth.login_failed"):
            assert client.get("/api/v1/audit-logs?action=" + action).json()["total"] == 0
        assert client.get("/api/v1/audit-logs?page_size=101").status_code == 422
    for role in ("manager", "alice", "unlinked"):
        assert world.client(role).get("/api/v1/audit-logs").status_code == 403
    assert TestClient(world.app).get("/api/v1/audit-logs").status_code == 401
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(AuditLog)) == before
