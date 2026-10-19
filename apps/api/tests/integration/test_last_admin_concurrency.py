from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, UserRole
from app.modules.users.repository import UserRepository


@pytest.mark.parametrize("change", [{"role": "HR"}, {"is_active": False}])
def test_concurrent_last_two_admin_removals_preserve_one(
    mutation_app,
    login_cookies,
    auth_engine,
    monkeypatch,
    change,
):
    first_cookies = login_cookies()
    with Session(auth_engine) as session, session.begin():
        first = session.scalars(select(User)).one()
        first.role = UserRole.ADMIN
        first_id = str(first.id)
        second = User(
            email="second@example.com",
            password_hash=first.password_hash,
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(second)
        session.flush()
        second_id = str(second.id)
    second_login = TestClient(mutation_app).post(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://testserver",
        },
        json={"email": "second@example.com", "password": "original-password"},
    )
    assert second_login.status_code == 200
    barrier = Barrier(2)
    original = UserRepository.lock_active_admins

    def lock(self):
        barrier.wait(timeout=10)
        return original(self)

    monkeypatch.setattr(UserRepository, "lock_active_admins", lock)

    def remove(item):
        user_id, cookies = item
        client = TestClient(
            mutation_app,
            cookies=cookies,
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": cookies["insighthr_csrf"],
            },
        )
        return client.patch(f"/api/v1/users/{user_id}", json=change)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                remove,
                [
                    (first_id, first_cookies),
                    (second_id, dict(second_login.cookies)),
                ],
            )
        )
    assert sorted(response.status_code for response in responses) == [200, 409]
    assert next(r for r in responses if r.status_code == 409).json()["error"]["code"] == (
        "last_active_admin"
    )
    with Session(auth_engine) as session:
        admins = session.scalars(
            select(User).where(
                User.role == UserRole.ADMIN,
                User.is_active.is_(True),
            )
        ).all()
        assert len(admins) == 1
