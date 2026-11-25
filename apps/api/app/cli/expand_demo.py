"""Add a larger fictional company without replacing any existing records."""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import Engine, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.cli.expanded_demo_data import DEPARTMENTS, KPIS, POSITIONS, roster
from app.cli.seed_demo import DATASET as BASE_DATASET
from app.cli.seed_demo import MARKER, DemoBuilder, DemoConflict, email
from app.core.config import get_settings
from app.core.database import get_engine
from app.core.errors import ApiError
from app.core.policies import AuthContext
from app.core.security import PasswordService, hash_opaque_token, new_opaque_token
from app.models import (
    AuditLog,
    AuthSession,
    Department,
    Employee,
    EmploymentStatus,
    KPIDefinition,
    Position,
    User,
    UserRole,
)
from app.modules.audit.service import AuditWriter
from app.modules.collaboration.models import ChatMessage, InternalPost, PostComment
from app.modules.collaboration.schemas import ContentInput, PostInput
from app.modules.collaboration.service import CollaborationService
from app.modules.kpis.models import KPIDirection
from app.modules.organization.repository import OrganizationRepository
from app.modules.review_cycles.schemas import CycleCreate, Enrollment
from app.modules.review_cycles.service import CycleService
from app.modules.users.repository import UserRepository

DATASET = "office-demo-expansion-v1"
CYCLE_NAME = "[DEMO+] Đánh giá toàn công ty — mở rộng"


class Expansion:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users: dict[str, User] = {}
        self.employees: dict[str, Employee] = {}
        self.departments: dict[str, Department] = {}
        self.contexts: dict[str, AuthContext] = {}

    def audit(self, action: str, kind: str, identifier: UUID | str) -> None:
        AuditWriter().record(
            self.session, self.users["hr"].id, action, kind, str(identifier), DATASET, {}
        )

    def preflight(self) -> bool:
        if self.session.scalar(
            select(AuditLog.id).where(AuditLog.action == MARKER, AuditLog.entity_id == DATASET)
        ):
            return False
        if not self.session.scalar(
            select(AuditLog.id).where(AuditLog.action == MARKER, AuditLog.entity_id == BASE_DATASET)
        ):
            raise DemoConflict("Seed the original office demo first; nothing was changed.")
        from app.models import ReviewCycle

        collisions = (
            self.session.scalar(
                select(User.id).where(User.email.in_([email(r[0]) for r in roster()]))
            ),
            self.session.scalar(
                select(Employee.id).where(
                    Employee.employee_code.in_(
                        ["DEMO-" + r[0].replace(".", "-").upper() for r in roster()]
                    )
                )
            ),
            self.session.scalar(
                select(Department.id).where(
                    Department.code.in_(["DEMO-" + d.code for d in DEPARTMENTS if not d.existing])
                )
            ),
            self.session.scalar(
                select(Position.id).where(Position.code.in_(["DEMO-" + code for code in POSITIONS]))
            ),
            self.session.scalar(
                select(KPIDefinition.id).where(
                    KPIDefinition.code.in_(["DEMO-X-" + row[0] for row in KPIS])
                )
            ),
            self.session.scalar(select(ReviewCycle.id).where(ReviewCycle.name == CYCLE_NAME)),
        )
        if any(collisions):
            raise DemoConflict("Expansion identifiers already exist; existing data was retained.")
        for name, role in (
            ("hr", UserRole.HR),
            ("admin", UserRole.ADMIN),
            ("manager", UserRole.MANAGER),
            ("sales.manager", UserRole.MANAGER),
        ):
            user = self.session.scalar(select(User).where(User.email == email(name)))
            if user is None or not user.is_active or user.role != role:
                raise DemoConflict("Required original demo accounts changed; nothing was changed.")
            self.users[name] = user
        for spec in DEPARTMENTS:
            if spec.existing:
                department = self.session.scalar(
                    select(Department).where(
                        Department.code == "DEMO-" + spec.code, Department.is_active.is_(True)
                    )
                )
                manager = self.session.scalar(
                    select(Employee).where(
                        Employee.user_id == self.users[spec.manager].id,
                        Employee.employment_status == EmploymentStatus.ACTIVE,
                    )
                )
                if department is None or manager is None or manager.department_id != department.id:
                    raise DemoConflict("Original department/manager changed; nothing was changed.")
                self.departments[spec.code] = department
                self.employees[spec.manager] = manager
        if not self.session.scalar(
            select(Position.id).where(Position.code == "DEMO-LEAD", Position.is_active.is_(True))
        ):
            raise DemoConflict("Original lead position unavailable; nothing was changed.")
        return True

    def foundation(self, password: str) -> None:
        password_hash = PasswordService().hash(password)
        for spec in DEPARTMENTS:
            if not spec.existing:
                department = Department(code="DEMO-" + spec.code, name="[DEMO] " + spec.name)
                self.session.add(department)
                self.session.flush()
                self.departments[spec.code] = department
                self.audit("department.created", "department", department.id)
        positions = {
            p.code.removeprefix("DEMO-"): p
            for p in self.session.scalars(select(Position).where(Position.code == "DEMO-LEAD"))
        }
        for code, title in POSITIONS.items():
            position = Position(code="DEMO-" + code, title="[DEMO] " + title)
            self.session.add(position)
            self.session.flush()
            positions[code] = position
            self.audit("position.created", "position", position.id)
        for name, display, department_code, job, manager in roster():
            user = User(
                email=email(name),
                role=UserRole.MANAGER if manager is None else UserRole.EMPLOYEE,
                password_hash=password_hash,
                is_active=True,
            )
            self.session.add(user)
            self.session.flush()
            self.users[name] = user
            self.audit("user.bootstrap_created", "user", user.id)
            employee = Employee(
                employee_code="DEMO-" + name.replace(".", "-").upper(),
                display_name=display,
                user_id=user.id,
                department_id=self.departments[department_code].id,
                position_id=positions[job].id,
                manager_id=self.employees[manager].id if manager else None,
            )
            self.session.add(employee)
            self.session.flush()
            self.employees[name] = employee
            self.audit("employee.created", "employee", employee.id)
        for code, title, unit, lower in KPIS:
            definition = KPIDefinition(
                code="DEMO-X-" + code,
                name="[DEMO] " + title,
                unit=unit,
                direction=KPIDirection.LOWER_IS_BETTER if lower else KPIDirection.HIGHER_IS_BETTER,
                description="KPI hư cấu cho bộ công ty mở rộng; "
                "quản lý đặt mục tiêu và trọng số theo kỳ.",
            )
            self.session.add(definition)
            self.session.flush()
            self.audit("kpi_definition.created", "kpi_definition", definition.id)

    def context(self, name: str) -> AuthContext:
        if name not in self.contexts:
            with self.session.begin():
                auth = AuthSession(
                    user_id=self.users[name].id,
                    family_id=uuid4(),
                    token_hash=hash_opaque_token(new_opaque_token()),
                    csrf_hash=hash_opaque_token(new_opaque_token()),
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
                self.session.add(auth)
                self.session.flush()
                self.contexts[name] = AuthContext(
                    user=self.users[name], family_id=auth.family_id, session=auth
                )
        return self.contexts[name]

    def draft(self) -> None:
        context = self.context("hr")
        with self.session.begin():
            employees = list(
                self.session.scalars(
                    select(Employee).where(
                        Employee.employee_code.startswith("DEMO-"),
                        Employee.employment_status == EmploymentStatus.ACTIVE,
                    )
                )
            )
            users = {u.id: u for u in self.session.scalars(select(User))}
            managers = {e.id: e for e in employees}
            eligible = []
            for employee in employees:
                manager = managers.get(employee.manager_id) if employee.manager_id else None
                account = users.get(employee.user_id) if employee.user_id else None
                leader = users.get(manager.user_id) if manager and manager.user_id else None
                if (
                    account
                    and account.is_active
                    and account.role == UserRole.EMPLOYEE
                    and leader
                    and leader.is_active
                    and leader.role == UserRole.MANAGER
                ):
                    eligible.append(employee.id)
        service = CycleService(self.session)
        year = datetime.now(UTC).year + 1
        cycle = service.write(
            CycleCreate(name=CYCLE_NAME, start_date=date(year, 1, 1), end_date=date(year, 12, 31)),
            context,
            csrf=DemoBuilder.csrf,
            request_id=DATASET,
        )
        for start in range(0, len(eligible), 100):
            result = service.enroll(
                cycle.id,
                Enrollment(
                    expected_version=cycle.version, employee_ids=eligible[start : start + 100]
                ),
                context,
                csrf=DemoBuilder.csrf,
                request_id=DATASET,
            )
            cycle = cycle.model_copy(update={"version": result.version})

    def communication(self) -> None:
        service = CollaborationService(self.session)
        hr = self.context("hr")
        welcome = service.publish(
            hr,
            DemoBuilder.csrf,
            PostInput(
                id=uuid4(),
                title="[DEMO+] Chào mừng đến với không gian công ty mở rộng",
                body="Dữ liệu hư cấu: công ty có 60 nhân viên ở 8 phòng ban. "
                "Dùng bảng tin để cập nhật công việc chung, @nhắc để phối hợp và chat "
                "cho trao đổi riêng. HR tổ chức, quản lý "
                "phụ trách nhóm, nhân viên thực hiện và phản hồi. Đây không phải điểm đánh giá.",
                mentions=[self.users["product.manager"].id, self.users["care.manager"].id],
            ),
            DATASET,
        )
        self.stamp(InternalPost, welcome["id"])
        for spec in DEPARTMENTS:
            manager = self.context(spec.manager)
            post = service.publish(
                manager,
                DemoBuilder.csrf,
                PostInput(
                    id=uuid4(),
                    department_id=self.departments[spec.code].id,
                    title=f"[DEMO+] {spec.name}: phối hợp công việc tuần này",
                    body=f"Phòng {spec.name} có {spec.target} nhân viên demo. "
                    "Cập nhật tiến độ và vướng "
                    "mắc trong trao đổi bên dưới. KPI cá nhân và phản hồi 360 thực hiện ở tab đánh "
                    "giá, không đăng nhận xét riêng tư lên bảng tin.",
                ),
                DATASET,
            )
            self.stamp(InternalPost, post["id"])
            staff = spec.code.lower() + "01"
            comment = service.publish(
                self.context(staff),
                DemoBuilder.csrf,
                ContentInput(
                    id=uuid4(),
                    body="[DEMO+] Đã nhận kế hoạch. Tôi sẽ cập nhật tiến độ "
                    "và báo sớm nếu có vướng mắc.",
                    mentions=[self.users[spec.manager].id],
                ),
                DATASET,
                post["id"],
            )
            self.stamp(PostComment, comment["id"])
            message = service.send(
                manager,
                DemoBuilder.csrf,
                self.users[staff].id,
                ContentInput(
                    id=uuid4(),
                    body="[DEMO+] Chào bạn, kiểm tra kế hoạch tại bảng tin phòng và trao đổi ở đây "
                    "nếu cần hỗ trợ nhé.",
                    mentions=[self.users[staff].id],
                ),
                DATASET,
            )
            self.stamp(ChatMessage, message["id"])
            reply = service.send(
                self.context(staff),
                DemoBuilder.csrf,
                self.users[spec.manager].id,
                ContentInput(
                    id=uuid4(), body="[DEMO+] Em đã nhận thông tin, sẽ chủ động cập nhật."
                ),
                DATASET,
            )
            self.stamp(ChatMessage, reply["id"])

    def stamp(
        self, model: type[InternalPost] | type[PostComment] | type[ChatMessage], identifier: UUID
    ) -> None:
        # PostgreSQL now() is fixed for the outer transaction. Preserve creation order
        # for these new fictional rows so a reply cannot sort before its question.
        with self.session.begin():
            self.session.execute(
                update(model).where(model.id == identifier).values(created_at=datetime.now(UTC))
            )

    def finish(self) -> None:
        with self.session.begin():
            for context in self.contexts.values():
                context.session.revoked_at = datetime.now(UTC)
            self.audit(MARKER, "demo_dataset", DATASET)


def expand_demo(engine: Engine, password: str = "1") -> bool:
    with (
        engine.begin() as connection,
        Session(
            bind=connection,
            expire_on_commit=False,
            autoflush=False,
            join_transaction_mode="create_savepoint",
        ) as session,
    ):
        builder = Expansion(session)
        with session.begin():
            OrganizationRepository(session).lock_guard()
            UserRepository(session).lock_active_admins()
            list(
                session.scalars(
                    select(User)
                    .where(
                        User.email.in_(
                            [email(name) for name in ("hr", "admin", "manager", "sales.manager")]
                        )
                    )
                    .order_by(User.id)
                    .with_for_update()
                )
            )
            if not builder.preflight():
                return False
            builder.foundation(password)
        builder.draft()
        builder.communication()
        builder.finish()
    return True


def main() -> int:
    try:
        settings = get_settings()
        if settings.app_env not in ("development", "test"):
            raise DemoConflict("Expanded demo is allowed only in development/test.")
        engine = get_engine(settings)
        try:
            created = expand_demo(engine)
        finally:
            engine.dispose()
    except (DemoConflict, ApiError, SQLAlchemyError, ValueError) as error:
        message = (
            str(error)
            if isinstance(error, DemoConflict)
            else "Expansion failed; all changes rolled back."
        )
        print(message, file=sys.stderr)
        return 1
    print(
        "Expanded company demo created."
        if created
        else "Expansion already exists; nothing changed."
    )
    print("Existing accounts, passwords, cycles and practice progress were retained. No AI called.")
    print("Guide: docs/du-lieu-mo-rong.vi.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
