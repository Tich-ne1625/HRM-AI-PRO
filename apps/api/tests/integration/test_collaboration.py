from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.orm import Session

from app.models import ChatMessage, Employee, InternalPost, Notification, PostComment, User
from app.modules.collaboration.service import CollaborationService

ROOT = "/api/v1/collaboration"


def content(**extra):
    return {
        "id": str(uuid4()),
        "body": "Plain text <script>alert(1)</script>",
        "mentions": [],
        **extra,
    }


def publish(world, who="hr", **extra):
    response = world.client(who).post(
        f"{ROOT}/posts", json=content(**{"title": "Company update", **extra})
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize("who", ["admin", "hr", "manager", "alice"])
def test_directory_has_only_public_contact_fields_and_company_feed_for_every_role(world, who):
    post = publish(world)
    client = world.client(who)
    assert post["id"] in {row["id"] for row in client.get(f"{ROOT}/posts").json()["items"]}
    rows = client.get(f"{ROOT}/people").json()["items"]
    assert rows and all(
        set(row) == {"id", "name", "role", "department", "department_id"} for row in rows
    )
    assert world.users[who] not in {row["id"] for row in rows}
    assert client.get(f"{ROOT}/people?search=%25").json()["items"] == []


@pytest.mark.parametrize("who", ["alice", "manager", "unlinked"])
def test_company_publish_is_hr_admin_only(world, who):
    response = world.client(who).post(f"{ROOT}/posts", json=content(title="No"))
    assert response.status_code == 403


def test_department_authorization_applies_to_feed_detail_comments_mentions_and_notifications(world):
    post = publish(
        world, "alice", department_id=world.departments["ENG"], mentions=[world.users["manager"]]
    )
    client = world.client("bob")
    assert client.get(f"{ROOT}/posts").json()["items"] == []
    assert client.get(f"{ROOT}/posts/{post['id']}").status_code == 404
    assert client.post(f"{ROOT}/posts/{post['id']}/comments", json=content()).status_code == 404
    assert client.get(f"{ROOT}/people?post_id={post['id']}").status_code == 404
    assert client.get("/api/v1/notifications").json()["items"] == []
    for who in ("hr", "admin", "manager"):
        response = world.client(who).get(f"{ROOT}/posts/{post['id']}")
        assert response.status_code == 200, response.text
    assert (
        world.client("alice")
        .post(
            f"{ROOT}/posts",
            json=content(title="Other department", department_id=world.departments["SALES"]),
        )
        .status_code
        == 403
    )


def test_hr_can_announce_in_specific_department_without_employee_record(world):
    post = publish(world, department_id=world.departments["ENG"])
    assert world.client("alice").get(f"{ROOT}/posts/{post['id']}").status_code == 200
    assert world.client("bob").get(f"{ROOT}/posts/{post['id']}").status_code == 404


def test_mentions_are_validated_before_any_content_or_notice_is_written(world):
    response = world.client("alice").post(
        f"{ROOT}/posts",
        json=content(
            title="Wrong audience",
            department_id=world.departments["ENG"],
            mentions=[world.users["bob"]],
        ),
    )
    assert response.status_code == 422
    with Session(world.engine) as session:
        assert session.scalar(select(func.count()).select_from(InternalPost)) == 0
        assert session.scalar(select(func.count()).select_from(Notification)) == 0


def test_comment_mentions_notify_only_tagged_people_and_author_without_leaking_body(world):
    post = publish(world)
    with Session(world.engine) as session, session.begin():
        session.query(Notification).delete()
    response = world.client("alice").post(
        f"{ROOT}/posts/{post['id']}/comments",
        json=content(mentions=[world.users["bob"], world.users["bob"]]),
    )
    assert response.status_code == 201, response.text
    assert [p["id"] for p in response.json()["mentions"]] == [world.users["bob"]]
    with Session(world.engine) as session:
        rows = list(session.scalars(select(Notification)))
        assert {str(row.recipient_id) for row in rows} == {world.users["bob"], world.users["hr"]}
    inbox = world.client("bob").get("/api/v1/notifications").json()["items"]
    assert inbox[0]["href"] == f"/news?post={post['id']}"
    assert "script" not in str(inbox)


def test_department_transfer_revokes_post_and_old_notice_visibility(world):
    post = publish(world, "alice", department_id=world.departments["ENG"])
    assert world.client("manager").get("/api/v1/notifications").json()["unread_count"] == 1
    with Session(world.engine) as session, session.begin():
        employee = session.get(Employee, UUID(world.employees["manager"]))
        employee.department_id = UUID(world.departments["SALES"])
    assert world.client("manager").get(f"{ROOT}/posts/{post['id']}").status_code == 404
    assert world.client("manager").get("/api/v1/notifications").json()["unread_count"] == 0


@pytest.mark.parametrize("stranger_role", ["manager", "hr", "admin"])
def test_private_chat_is_pair_scoped_and_read_receipt_updates_only_seen_messages(
    world, stranger_role
):
    alice, bob = world.client("alice"), world.client("bob")
    peer = world.users["bob"]
    first = alice.post(f"{ROOT}/chat/{peer}", json=content(mentions=[peer])).json()
    second = alice.post(f"{ROOT}/chat/{peer}", json=content()).json()
    assert bob.get(f"{ROOT}/chat/{world.users['alice']}").json()["items"][0]["id"] == first["id"]
    stranger = world.client(stranger_role)
    assert stranger.get(f"{ROOT}/chat/{peer}").json()["items"] == []
    assert stranger.get(f"{ROOT}/messages/{first['id']}").status_code == 404
    assert stranger.get(f"{ROOT}/chat/{peer}?before={first['id']}").status_code == 404
    assert (
        stranger.post(f"{ROOT}/chat/{peer}/read", json={"through_id": first["id"]}).status_code
        == 404
    )
    assert (
        bob.post(
            f"{ROOT}/chat/{world.users['alice']}/read", json={"through_id": first["id"]}
        ).status_code
        == 204
    )
    messages = alice.get(f"{ROOT}/chat/{peer}").json()["items"]
    assert messages[0]["read_at"] and messages[1]["read_at"] is None
    assert bob.get(f"{ROOT}/conversations").json()["unread_count"] == 1
    notices = bob.get("/api/v1/notifications").json()
    assert notices["unread_count"] == 1
    assert any(row["href"] == f"/news?message={second['id']}" for row in notices["items"])


def test_chat_rejects_self_inactive_account_and_third_party_mention(world):
    client = world.client("alice")
    for peer in (world.users["alice"], str(uuid4())):
        assert client.post(f"{ROOT}/chat/{peer}", json=content()).status_code == 404
    assert (
        client.post(
            f"{ROOT}/chat/{world.users['bob']}", json=content(mentions=[world.users["hr"]])
        ).status_code
        == 422
    )
    with Session(world.engine) as session, session.begin():
        session.get(User, UUID(world.users["bob"])).is_active = False
    assert client.post(f"{ROOT}/chat/{world.users['bob']}", json=content()).status_code == 404
    assert world.users["bob"] not in {
        row["id"] for row in client.get(f"{ROOT}/people").json()["items"]
    }


@pytest.mark.parametrize("kind", ["chat", "post", "comment"])
def test_content_and_notice_rollback_together_on_delivery_failure(world, monkeypatch, kind):
    post = publish(world)
    with Session(world.engine) as session:
        counts = [
            session.scalar(select(func.count()).select_from(model))
            for model in (ChatMessage, InternalPost, PostComment, Notification)
        ]

    def fail(*args, **kwargs):
        raise RuntimeError("notification persistence failed")

    monkeypatch.setattr(CollaborationService, "notify", fail)
    url = {
        "chat": f"/chat/{world.users['bob']}",
        "post": "/posts",
        "comment": f"/posts/{post['id']}/comments",
    }[kind]
    body = content(**({"title": "Will roll back"} if kind == "post" else {}))
    assert world.client().post(ROOT + url, json=body).status_code == 500
    with Session(world.engine) as session:
        assert [
            session.scalar(select(func.count()).select_from(model))
            for model in (ChatMessage, InternalPost, PostComment, Notification)
        ] == counts


@pytest.mark.parametrize("kind", ["chat", "post", "comment"])
def test_retries_and_concurrent_replays_create_one_content_and_notice(world, kind):
    post = publish(world)
    url = {
        "chat": f"/chat/{world.users['bob']}",
        "post": "/posts",
        "comment": f"/posts/{post['id']}/comments",
    }[kind]
    body = content(**({"title": "One post"} if kind == "post" else {}))

    def send(_):
        return world.client("hr" if kind == "post" else "alice").post(ROOT + url, json=body)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(send, range(2)))
    assert [r.status_code for r in responses] == [201, 201], [r.text for r in responses]
    model = {"chat": ChatMessage, "post": InternalPost, "comment": PostComment}[kind]
    with Session(world.engine) as session:
        assert (
            session.scalar(
                select(func.count()).select_from(model).where(model.id == UUID(body["id"]))
            )
            == 1
        )
    assert (
        world.client("hr" if kind == "post" else "alice")
        .post(ROOT + url, json={**body, "body": "Changed under same identifier"})
        .status_code
        == 409
    )


@pytest.mark.parametrize("path", ["/posts", "/chat/bob", "/chat/bob/read"])
def test_mutations_require_csrf_and_origin(world, path):
    path = path.replace("bob", world.users["bob"])
    body = (
        {"through_id": str(uuid4())}
        if path.endswith("/read")
        else content(**({"title": "News"} if path == "/posts" else {}))
    )
    client = world.client()
    client.headers.pop("X-CSRF-Token")
    assert client.post(ROOT + path, json=body).status_code == 403
    client = world.client()
    client.headers["Origin"] = "https://elsewhere.example"
    assert client.post(ROOT + path, json=body).status_code == 403


def test_message_pagination_is_stable_and_read_does_not_include_newer_messages(world):
    client = world.client("alice")
    peer = world.users["bob"]
    for i in range(33):
        assert (
            client.post(f"{ROOT}/chat/{peer}", json=content(body=f"message {i}")).status_code == 201
        )
    current = client.get(f"{ROOT}/chat/{peer}").json()
    previous = client.get(f"{ROOT}/chat/{peer}?before={current['items'][0]['id']}").json()
    assert current["has_more"] and not previous["has_more"]
    assert len(current["items"]) == 30 and len(previous["items"]) == 3
    assert {r["id"] for r in current["items"]}.isdisjoint(r["id"] for r in previous["items"])


def test_collaboration_migration_matches_metadata_and_preserves_existing_rows(world):
    from alembic.config import Config

    from alembic import command

    from .conftest import ALEMBIC_INI

    with world.engine.connect() as connection:
        users = connection.scalar(text("SELECT count(*) FROM users"))
        employees = connection.scalar(text("SELECT count(*) FROM employees"))
    config = Config(str(ALEMBIC_INI))
    command.check(config)
    command.downgrade(config, "20261114_0009")
    command.upgrade(config, "head")
    with world.engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM users")) == users
        assert connection.scalar(text("SELECT count(*) FROM employees")) == employees
        assert connection.scalar(text("SELECT count(*) FROM internal_posts")) == 0
        assert connection.scalar(text("SELECT count(*) FROM chat_messages")) == 0
    command.check(config)


def test_feed_batch_loads_authors_and_mentions_with_bounded_queries(world):
    for i in range(8):
        publish(world, title=f"Post {i}", mentions=[world.users["alice"], world.users["bob"]])
    reads = []

    def count(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith("SELECT"):
            reads.append(statement)

    event.listen(world.engine, "before_cursor_execute", count)
    try:
        response = world.client("alice").get(f"{ROOT}/posts")
    finally:
        event.remove(world.engine, "before_cursor_execute", count)
    assert response.status_code == 200, response.text
    assert len(response.json()["items"]) == 8
    assert all(len(post["mentions"]) == 2 for post in response.json()["items"])
    assert len(reads) <= 10, reads


def test_opposite_direction_chat_writes_do_not_deadlock(world):
    def send(pair):
        sender, recipient = pair
        return world.client(sender).post(f"{ROOT}/chat/{world.users[recipient]}", json=content())

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(send, [("alice", "bob"), ("bob", "alice")]))
    assert [row.status_code for row in responses] == [201, 201], [row.text for row in responses]
    assert len(world.client("alice").get(f"{ROOT}/chat/{world.users['bob']}").json()["items"]) == 2
