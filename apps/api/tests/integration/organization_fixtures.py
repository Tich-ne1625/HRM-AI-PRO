from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import TokenService, hash_opaque_token, new_opaque_token
from app.models import AuthSession, Department, Employee, EmploymentStatus, Position, User, UserRole


@pytest.fixture
def world(mutation_app, auth_engine):
    class World:
        app = mutation_app
        engine = auth_engine

        def __init__(self):
            self.users = {}
            self.employees = {}
            self.cookies = {}
            self.departments = {}
            self.positions = {}

        def client(self, name="hr"):
            cookies = self.cookies[name]
            return TestClient(
                self.app,
                cookies=cookies,
                raise_server_exceptions=False,
                headers={
                    "Origin": "http://testserver",
                    "X-CSRF-Token": cookies["insighthr_csrf"],
                },
            )

        def employee_payload(self, **overrides):
            return {
                "employee_code": "NEW-01",
                "display_name": "New Person",
                "department_id": self.departments["ENG"],
                "position_id": self.positions["DEV"],
                **overrides,
            }

    data = World()
    with Session(auth_engine) as session, session.begin():
        hr = session.scalars(select(User)).one()
        data.users["hr"] = str(hr.id)
        for name, role in [
            ("admin", "ADMIN"),
            ("manager", "MANAGER"),
            ("other", "MANAGER"),
            ("alice", "EMPLOYEE"),
            ("bob", "EMPLOYEE"),
            ("indirect", "EMPLOYEE"),
            ("unlinked", "MANAGER"),
            ("spare", "EMPLOYEE"),
        ]:
            user = User(
                email=f"{name}@example.com", password_hash=hr.password_hash, role=UserRole(role)
            )
            session.add(user)
            session.flush()
            data.users[name] = str(user.id)
        for code in ("ENG", "SALES", "UNUSED"):
            row = Department(code=code, name=code.title())
            session.add(row)
            session.flush()
            data.departments[code] = str(row.id)
        for code in ("LEAD", "DEV", "SALES"):
            row = Position(code=code, title=code.title())
            session.add(row)
            session.flush()
            data.positions[code] = str(row.id)
        for name, manager, department, position in [
            ("manager", None, "ENG", "LEAD"),
            ("other", None, "SALES", "LEAD"),
            ("alice", "manager", "ENG", "DEV"),
            ("bob", "other", "SALES", "SALES"),
            ("indirect", "alice", "SALES", "DEV"),
        ]:
            employee = Employee(
                employee_code=f"EMP-{name.upper()}",
                display_name=name.title(),
                department_id=data.departments[department],
                position_id=data.positions[position],
                manager_id=data.employees.get(manager),
                user_id=data.users[name],
                employment_status=EmploymentStatus.ACTIVE,
            )
            session.add(employee)
            session.flush()
            data.employees[name] = str(employee.id)
        for name, user_id in data.users.items():
            family = uuid4()
            refresh, csrf = new_opaque_token(), new_opaque_token()
            session.add(
                AuthSession(
                    user_id=user_id,
                    family_id=family,
                    token_hash=hash_opaque_token(refresh),
                    csrf_hash=hash_opaque_token(csrf),
                    expires_at=datetime.now(UTC) + timedelta(days=7),
                )
            )
            data.cookies[name] = {
                "insighthr_access": TokenService(
                    mutation_app.state.settings.access_signing_key
                ).create_access_token(user_id, family),
                "insighthr_refresh": refresh,
                "insighthr_csrf": csrf,
            }
    return data
