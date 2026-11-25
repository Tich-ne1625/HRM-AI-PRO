"""Standalone fictional Phase 11 story, restricted to an empty disposable _test database."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.cli.seed_demo import DemoConflict
from app.core.config import get_settings
from app.core.database import get_engine
from app.core.policies import AuthContext
from app.core.security import PasswordService, hash_opaque_token, new_opaque_token
from app.models import AuditLog, AuthSession, Department, Employee, KPIDefinition, Position, User
from app.modules.audit.service import AuditWriter
from app.modules.review_cycles.activation import CycleActivation
from app.modules.review_cycles.models import CycleParticipant
from app.modules.review_cycles.schemas import CycleCreate, Enrollment
from app.modules.review_cycles.service import CycleService
from app.modules.users.models import UserRole
from app.modules.work_management.schemas import (
    PlanAction,
    PlanDraft,
    WorkAction,
    WorkCreate,
    WorkflowSchedule,
)
from app.modules.work_management.service import WorkService

DATASET = "continuous-demo-v1"


class ContinuousDemo:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.contexts: dict[str, AuthContext] = {}
        self.employee_id: UUID
        self.definition_id: UUID

    @staticmethod
    def csrf(_: AuthSession) -> None:
        pass  # Trusted, test-only CLI; no token or bypass is exposed over HTTP.

    def foundation(self) -> None:
        with self.session.begin():
            password_hash = PasswordService().hash("1")
            department = Department(code="CONT-CARE", name="Chăm sóc khách hàng")
            position = Position(code="CONT-SUPPORT", title="Chuyên viên CSKH")
            self.session.add_all([department, position])
            self.session.flush()
            manager_employee = None
            for name, role, display in [
                ("admin", UserRole.ADMIN, "Quản trị demo"),
                ("hr", UserRole.HR, "Nhân sự điều phối"),
                ("care.manager", UserRole.MANAGER, "Hoàng Mai Anh"),
                ("care01", UserRole.EMPLOYEE, "Vũ Đức Huy"),
            ]:
                user = User(
                    email=f"{name}.demo@example.com",
                    role=role,
                    password_hash=password_hash,
                    is_active=True,
                )
                self.session.add(user)
                self.session.flush()
                if role in {UserRole.MANAGER, UserRole.EMPLOYEE}:
                    employee = Employee(
                        employee_code=f"CONT-{name.replace('.', '-').upper()}",
                        display_name=display,
                        department_id=department.id,
                        position_id=position.id,
                        user_id=user.id,
                        manager_id=manager_employee,
                    )
                    self.session.add(employee)
                    self.session.flush()
                    if role == UserRole.MANAGER:
                        manager_employee = employee.id
                    else:
                        self.employee_id = employee.id
                family_id = uuid4()
                auth = AuthSession(
                    user_id=user.id,
                    family_id=family_id,
                    token_hash=hash_opaque_token(new_opaque_token()),
                    csrf_hash=hash_opaque_token(new_opaque_token()),
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
                self.session.add(auth)
                self.session.flush()
                self.contexts[name] = AuthContext(user, family_id, auth)
            definition = KPIDefinition(
                code="CONT-RESOLVED",
                name="Hồ sơ được xác minh hoàn tất",
                description="Mỗi mã hồ sơ tính một lần sau khi QA xác nhận",
                unit="hồ sơ",
                direction="HIGHER_IS_BETTER",
            )
            self.session.add(definition)
            self.session.flush()
            self.definition_id = definition.id

    def cycle(self, title: str) -> tuple[UUID, UUID]:
        today = datetime.now(UTC).date()
        start, end = today, today + timedelta(days=30)
        schedule = WorkflowSchedule(
            acknowledgement_due_at=datetime.combine(
                today - timedelta(days=1), datetime.min.time(), UTC
            ),
            input_cutoff_at=datetime.combine(end + timedelta(days=1), datetime.min.time(), UTC),
            verification_due_at=datetime.combine(end + timedelta(days=2), datetime.min.time(), UTC),
            response_due_at=datetime.combine(end + timedelta(days=3), datetime.min.time(), UTC),
        )
        hr = self.contexts["hr"]
        cycle = CycleService(self.session).write(
            CycleCreate(
                name=title,
                start_date=start,
                end_date=end,
                workflow_mode="CONTINUOUS",
                workflow_schedule=schedule,
            ),
            hr,
            csrf=self.csrf,
            request_id=DATASET,
        )
        CycleService(self.session).enroll(
            cycle.id,
            Enrollment(expected_version=1, employee_ids=[self.employee_id]),
            hr,
            csrf=self.csrf,
            request_id=DATASET,
        )
        with self.session.begin():
            participant = self.session.scalar(
                select(CycleParticipant.id).where(CycleParticipant.cycle_id == cycle.id)
            )
            assert participant is not None
            return cycle.id, participant

    def plan(self, participant: UUID) -> dict[str, object]:
        data = PlanDraft.model_validate(
            {
                "client_request_id": str(uuid4()),
                "expected_version": 1,
                "objective": "Xử lý hồ sơ CSKH có kiểm tra chất lượng và bằng chứng rõ ràng.",
                "goals": [
                    {
                        "definition_id": str(self.definition_id),
                        "baseline": "0",
                        "target": "120",
                        "weight": "100",
                        "method": "SUM",
                        "source": "Mã hồ sơ CSKH duy nhất, được QA xác minh; không cộng hai lần.",
                        "acceptance": "Khách hàng xác nhận, có đối chiếu QA, hồ sơ lưu đầy đủ.",
                    }
                ],
            }
        )
        return WorkService(self.session).save_plan(
            self.contexts["care.manager"], self.csrf, participant, data, DATASET
        )

    def advance_plan(
        self, plan: dict[str, object], action: str, actor: str = "care.manager"
    ) -> dict[str, object]:
        return WorkService(self.session).plan_action(
            self.contexts[actor],
            self.csrf,
            UUID(str(plan["id"])),
            PlanAction.model_validate(
                {
                    "client_request_id": str(uuid4()),
                    "expected_version": plan["version"],
                    "revision": plan["revision"],
                    "action": action,
                    "body": "Cần làm rõ tiêu chuẩn xác nhận của khách hàng."
                    if action == "clarify"
                    else None,
                }
            ),
            DATASET,
        )

    def story(self) -> None:
        _, draft_participant = self.cycle("[CONT DEMO] Chuẩn bị — kế hoạch cần làm rõ")
        plan = self.advance_plan(self.plan(draft_participant), "submit")
        self.advance_plan(plan, "clarify", "care01")
        cycle, participant = self.cycle("[CONT DEMO] Thực hành giao việc và nghiệm thu")
        plan = self.plan(participant)
        for action, actor in [
            ("submit", "care.manager"),
            ("approve", "care.manager"),
            ("acknowledge", "care01"),
        ]:
            plan = self.advance_plan(plan, action, actor)
        CycleActivation(self.session).activate(
            cycle, 2, self.contexts["hr"], csrf=self.csrf, request_id=DATASET
        )
        goals = plan["goals"]
        assert isinstance(goals, list) and isinstance(goals[0], dict)
        goal_id = str(goals[0]["id"])
        scenarios = [
            ("CSKH-001", "Đối chiếu hồ sơ khách hàng mới", []),
            (
                "CSKH-002",
                "Xử lý yêu cầu đang thiếu dữ liệu",
                [("start", "care01"), ("block", "care01")],
            ),
            (
                "CSKH-003",
                "Bổ sung kết quả kiểm tra chất lượng",
                [("start", "care01"), ("submit", "care01"), ("return", "care.manager")],
            ),
            (
                "CSKH-004",
                "Hoàn thiện hồ sơ đã nghiệm thu",
                [("start", "care01"), ("submit", "care01"), ("accept", "care.manager")],
            ),
        ]
        for code, title, actions in scenarios:
            work = WorkService(self.session).create_work(
                self.contexts["care.manager"],
                self.csrf,
                UUID(str(plan["id"])),
                WorkCreate.model_validate(
                    {
                        "client_request_id": str(uuid4()),
                        "expected_version": plan["version"],
                        "title": title,
                        "acceptance": "Có xác nhận khách hàng và kết quả đối chiếu của QA.",
                        "source_key": code,
                        "goal_id": goal_id if code != "CSKH-002" else None,
                        "due_at": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
                        "priority": "HIGH" if code == "CSKH-002" else "NORMAL",
                    }
                ),
                DATASET,
            )
            for action, actor in actions:
                work = WorkService(self.session).action(
                    self.contexts[actor],
                    self.csrf,
                    UUID(str(work["id"])),
                    WorkAction.model_validate(
                        {
                            "client_request_id": str(uuid4()),
                            "expected_version": work["version"],
                            "action": action,
                            "body": {
                                "block": "Cần bộ phận kinh doanh bổ sung mã đơn để đối chiếu.",
                                "submit": "Đã đối chiếu hồ sơ, ghi nhận xác nhận khách hàng.",
                                "return": "Bổ sung URL kết quả kiểm tra QA trước khi nghiệm thu.",
                                "accept": "Đủ xác nhận và bằng chứng QA; đồng ý nghiệm thu.",
                            }.get(action),
                        }
                    ),
                    DATASET,
                )
        with self.session.begin():
            for context in self.contexts.values():
                context.session.revoked_at = datetime.now(UTC)
            AuditWriter().record(
                self.session,
                self.contexts["hr"].user.id,
                "user.demo_seed_completed",
                "demo_dataset",
                DATASET,
                DATASET,
                {},
            )


def seed_continuous_demo(engine: Engine) -> bool:
    if not (engine.url.database or "").endswith("_test"):
        raise DemoConflict("Continuous demo is restricted to an isolated _test database")
    with (
        engine.begin() as connection,
        Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as session,
    ):
        with session.begin():
            if session.scalar(
                select(AuditLog.id).where(
                    AuditLog.action == "user.demo_seed_completed", AuditLog.entity_id == DATASET
                )
            ):
                return False
            if session.scalar(select(User.id).limit(1)):
                raise DemoConflict(
                    "Use an empty isolated database; existing users were not changed"
                )
        builder = ContinuousDemo(session)
        builder.foundation()
        builder.story()
    return True


def main() -> int:
    settings = get_settings()
    if settings.app_env not in {"development", "test"}:
        print("Continuous demo is development/test only", file=sys.stderr)
        return 1
    engine = get_engine(settings)
    try:
        changed = seed_continuous_demo(engine)
        print("Continuous demo created" if changed else "Continuous demo already exists")
        return 0
    except DemoConflict as error:
        print(str(error), file=sys.stderr)
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
