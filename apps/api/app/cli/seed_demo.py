"""Explicit, atomic office demo for development/test; never invokes an AI provider."""

from __future__ import annotations

import argparse
import secrets
import sys
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import Engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.cli.create_admin import BootstrapInputError, _read_password
from app.core.config import get_settings
from app.core.database import get_engine
from app.core.errors import ApiError
from app.core.policies import AuthContext
from app.core.security import PasswordService, hash_opaque_token, new_opaque_token
from app.models import (
    AuditLog,
    AuthSession,
    CycleParticipant,
    CycleStatus,
    Department,
    Employee,
    KPIDefinition,
    Position,
    ReviewCycle,
    User,
    UserRole,
)
from app.modules.audit.service import AuditWriter
from app.modules.feedback.models import Relationship
from app.modules.feedback.schemas import AssignmentCreate, FeedbackCreate
from app.modules.feedback.service import FeedbackService
from app.modules.kpis.allocations import AllocationService
from app.modules.kpis.models import KPIDirection
from app.modules.kpis.schemas import ActualUpdate, AllocationItem, AllocationReplace
from app.modules.organization.repository import OrganizationRepository
from app.modules.performance.schemas import CalculateInput, FinalizeInput, PerformanceReport
from app.modules.performance.service import PerformanceService
from app.modules.review_cycles.activation import CycleActivation
from app.modules.review_cycles.schemas import CycleCreate, Enrollment
from app.modules.review_cycles.service import CycleService

DATASET = "office-demo-v1"
MARKER = "user.demo_seed_completed"
ACCOUNTS = {
    "admin": ("Quản trị demo", UserRole.ADMIN),
    "hr": ("Nhân sự demo", UserRole.HR),
    "manager": ("Nguyễn Lan — quản lý kỹ thuật", UserRole.MANAGER),
    "sales.manager": ("Trần Huy — quản lý kinh doanh", UserRole.MANAGER),
    "an": ("Lê Minh An", UserRole.EMPLOYEE),
    "binh": ("Phạm Thanh Bình", UserRole.EMPLOYEE),
    "chi": ("Hoàng Mai Chi", UserRole.EMPLOYEE),
    "dung": ("Vũ Anh Dũng", UserRole.EMPLOYEE),
    "ha": ("Đỗ Thu Hà", UserRole.EMPLOYEE),
    "linh": ("Bùi Ngọc Linh", UserRole.EMPLOYEE),
}


def email(name: str) -> str:
    return f"{name}.demo@example.com"


class DemoConflict(ValueError):
    pass


class DemoBuilder:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users: dict[str, User] = {}
        self.employees: dict[str, Employee] = {}
        self.contexts: dict[str, AuthContext] = {}
        self.definitions: list[UUID] = []

    @staticmethod
    def csrf(_: AuthSession) -> None:
        # Trusted CLI only; the command never exposes an HTTP bypass or issues tokens.
        pass

    def audit(self, actor: UUID, action: str, kind: str, identifier: UUID) -> None:
        AuditWriter().record(self.session, actor, action, kind, str(identifier), DATASET, {})

    def foundation(self, password_hash: str) -> None:
        with self.session.begin():
            for name, (_, role) in ACCOUNTS.items():
                user = User(
                    email=email(name), role=role, password_hash=password_hash, is_active=True
                )
                self.session.add(user)
                self.session.flush()
                self.users[name] = user
                self.audit(user.id, "user.bootstrap_created", "user", user.id)
                auth = AuthSession(
                    user_id=user.id,
                    family_id=uuid4(),
                    token_hash=hash_opaque_token(new_opaque_token()),
                    csrf_hash=hash_opaque_token(new_opaque_token()),
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
                self.session.add(auth)
                self.session.flush()
                self.contexts[name] = AuthContext(user=user, session=auth, family_id=auth.family_id)
            departments = {}
            for code, name in (("TECH", "Kỹ thuật"), ("SALES", "Kinh doanh")):
                department = Department(code=f"DEMO-{code}", name=f"[DEMO] {name}")
                self.session.add(department)
                self.session.flush()
                departments[code] = department.id
                self.audit(self.users["hr"].id, "department.created", "department", department.id)
            positions = {}
            for code, title in (("LEAD", "Trưởng nhóm"), ("STAFF", "Chuyên viên")):
                position = Position(code=f"DEMO-{code}", title=f"[DEMO] {title}")
                self.session.add(position)
                self.session.flush()
                positions[code] = position.id
                self.audit(self.users["hr"].id, "position.created", "position", position.id)
            for name, manager, department_code in (
                ("manager", None, "TECH"),
                ("sales.manager", None, "SALES"),
                ("an", "manager", "TECH"),
                ("binh", "manager", "TECH"),
                ("chi", "an", "TECH"),
                ("dung", "manager", "TECH"),
                ("ha", "sales.manager", "SALES"),
                ("linh", "sales.manager", "SALES"),
            ):
                employee = Employee(
                    employee_code="DEMO-" + name.replace(".", "-").upper(),
                    display_name=ACCOUNTS[name][0],
                    department_id=departments[department_code],
                    position_id=positions["LEAD" if manager is None else "STAFF"],
                    user_id=self.users[name].id,
                    manager_id=self.employees[manager].id if manager else None,
                )
                self.session.add(employee)
                self.session.flush()
                self.employees[name] = employee
                self.audit(self.users["hr"].id, "employee.created", "employee", employee.id)
            for code, title in (
                ("DELIVERY", "Tiến độ hoàn thành công việc"),
                ("QUALITY", "Chất lượng hồ sơ và báo cáo"),
            ):
                definition = KPIDefinition(
                    code=f"DEMO-{code}",
                    name=f"[DEMO] {title}",
                    unit="%",
                    description="Dữ liệu hư cấu để thực hành, không dùng đánh giá người thật.",
                    direction=KPIDirection.HIGHER_IS_BETTER,
                )
                self.session.add(definition)
                self.session.flush()
                self.definitions.append(definition.id)
                self.audit(
                    self.users["hr"].id, "kpi_definition.created", "kpi_definition", definition.id
                )

    def participant(self, cycle_id: UUID, person: str) -> CycleParticipant:
        with self.session.begin():
            return self.session.scalars(
                select(CycleParticipant).where(
                    CycleParticipant.cycle_id == cycle_id,
                    CycleParticipant.employee_id == self.employees[person].id,
                )
            ).one()

    def cycle(self, label: str, people: list[str], *, activate: bool, year: int) -> UUID:
        cycles = CycleService(self.session)
        context = self.contexts["hr"]
        row = cycles.write(
            CycleCreate(
                name=f"[DEMO] {label}", start_date=date(year, 1, 1), end_date=date(year, 12, 31)
            ),
            context,
            csrf=self.csrf,
            request_id=DATASET,
        )
        enrolled = cycles.enroll(
            row.id,
            Enrollment(
                expected_version=row.version,
                employee_ids=[self.employees[name].id for name in people],
            ),
            context,
            csrf=self.csrf,
            request_id=DATASET,
        )
        if activate:
            CycleActivation(self.session).activate(
                row.id, enrolled.version, context, csrf=self.csrf, request_id=DATASET
            )
        return row.id

    def allocate(self, cycle_id: UUID, person: str, *, partial: bool = False) -> list[UUID]:
        participant = self.participant(cycle_id, person)
        context = self.contexts["hr"]
        service = AllocationService(self.session)
        allocation = service.replace(
            self.employees[person].id,
            cycle_id,
            AllocationReplace(
                expected_evidence_version=participant.evidence_version,
                items=[
                    AllocationItem(definition_id=identifier, target="100", weight=weight)
                    for identifier, weight in zip(self.definitions, ("60", "40"), strict=True)
                ],
            ),
            context,
            csrf=self.csrf,
            request_id=DATASET,
        )
        ids = [item.id for item in allocation.items]
        for identifier in ids[:1] if partial else ids:
            participant = self.participant(cycle_id, person)
            service.actual(
                identifier,
                ActualUpdate(
                    expected_evidence_version=participant.evidence_version,
                    actual="90" if not partial else "50",
                ),
                context,
                csrf=self.csrf,
                request_id=DATASET,
            )
        return ids

    def assign(
        self,
        cycle_id: UUID,
        person: str,
        reviewer: str,
        relationship: Relationship,
        *,
        submitted: bool = True,
    ) -> None:
        participant = self.participant(cycle_id, person)
        service = FeedbackService(self.session)
        assignment = service.create(
            AssignmentCreate(
                participant_id=participant.id,
                reviewer_id=self.users[reviewer].id,
                relationship=relationship,
                required=relationship in (Relationship.SELF, Relationship.MANAGER),
                expected_evidence_version=participant.evidence_version,
            ),
            self.contexts["hr"],
            csrf=self.csrf,
            request_id=DATASET,
        )
        if submitted:
            participant = self.participant(cycle_id, person)
            service.submit(
                FeedbackCreate(
                    assignment_id=assignment.id,
                    expected_assignment_version=assignment.version,
                    expected_evidence_version=participant.evidence_version,
                    rating=4,
                    comment=f"[DEMO — hư cấu] {ACCOUNTS[person][0]} hoàn thành công việc đúng hạn, "
                    "phối hợp tốt với nhóm. Nên chủ động báo sớm rủi ro "
                    "và chuẩn hóa tài liệu bàn giao.",
                ),
                self.contexts[reviewer],
                csrf=self.csrf,
                request_id=DATASET,
            )

    def mandatory(self, cycle_id: UUID, person: str, *, submitted: bool = True) -> None:
        manager = "sales.manager" if person in ("ha", "linh") else "manager"
        self.assign(cycle_id, person, person, Relationship.SELF, submitted=submitted)
        self.assign(cycle_id, person, manager, Relationship.MANAGER, submitted=submitted)

    def calculate(self, cycle_id: UUID, person: str) -> PerformanceReport:
        participant = self.participant(cycle_id, person)
        report, _ = PerformanceService(self.session).calculate(
            self.employees[person].id,
            CalculateInput(
                cycle_id=cycle_id, expected_evidence_version=participant.evidence_version
            ),
            self.contexts["hr"],
            csrf=self.csrf,
            request_id=DATASET,
        )
        return report

    def finalize(self, report: PerformanceReport) -> None:
        assert report.review_id is not None and report.current_result is not None
        PerformanceService(self.session).finalize(
            report.review_id,
            FinalizeInput(
                expected_evidence_version=report.evidence_version,
                expected_calculation_version=report.current_result.calculation_version,
                acknowledge_open_optional_count=0,
            ),
            self.contexts["hr"],
            csrf=self.csrf,
            request_id=DATASET,
        )

    def build(self, password_hash: str) -> None:
        self.foundation(password_hash)
        year = datetime.now(UTC).year
        historical = self.cycle("Lịch sử đã đóng", ["an", "ha"], activate=True, year=year - 1)
        for person in ("an", "ha"):
            self.allocate(historical, person)
            self.mandatory(historical, person)
            self.finalize(self.calculate(historical, person))
        with self.session.begin():
            cycle = self.session.get(ReviewCycle, historical)
            assert cycle is not None
            version = cycle.version
        PerformanceService(self.session).close(
            historical, version, self.contexts["hr"], csrf=self.csrf, request_id=DATASET
        )
        current = self.cycle(
            "Thực hành đánh giá", ["an", "binh", "dung", "ha", "linh"], activate=True, year=year
        )
        for person in ("an", "binh", "dung", "ha", "linh"):
            items = self.allocate(current, person, partial=person == "binh")
            self.mandatory(current, person, submitted=person != "binh")
            if person == "an":
                for reviewer in ("binh", "dung", "ha"):
                    self.assign(current, person, reviewer, Relationship.PEER)
                self.assign(current, person, "chi", Relationship.SUBORDINATE)
                self.assign(current, person, "linh", Relationship.PEER, submitted=False)
            if person in ("an", "ha", "linh"):
                report = self.calculate(current, person)
                if person == "ha":
                    self.finalize(report)
                else:
                    participant = self.participant(current, person)
                    AllocationService(self.session).actual(
                        items[0],
                        ActualUpdate(
                            expected_evidence_version=participant.evidence_version,
                            actual="80",
                        ),
                        self.contexts["hr"],
                        csrf=self.csrf,
                        request_id=DATASET,
                    )
                    if person == "an":
                        self.calculate(current, person)
        self.cycle("Kỳ tiếp theo — bản nháp", ["an", "binh"], activate=False, year=year + 1)
        with self.session.begin():
            for context in self.contexts.values():
                context.session.revoked_at = datetime.now(UTC)
            AuditWriter().record(
                self.session, self.users["admin"].id, MARKER, "demo_dataset", DATASET, DATASET, {}
            )


def seed_demo(engine: Engine, password: str) -> bool:
    """Every domain-service commit is a savepoint in one outer atomic transaction."""
    with (
        engine.begin() as connection,
        Session(
            bind=connection,
            expire_on_commit=False,
            autoflush=False,
            join_transaction_mode="create_savepoint",
        ) as session,
    ):
        with session.begin():
            OrganizationRepository(session).lock_guard()
            if session.scalar(
                select(AuditLog.id).where(
                    AuditLog.action == MARKER,
                    AuditLog.entity_id == DATASET,
                )
            ):
                return False
            if session.scalar(
                select(ReviewCycle.id).where(ReviewCycle.status == CycleStatus.ACTIVE)
            ):
                raise DemoConflict(
                    "An ACTIVE cycle already exists; existing data was left unchanged."
                )
            reserved = session.scalar(
                select(User.id).where(User.email.in_([email(n) for n in ACCOUNTS]))
            )
            codes = any(
                session.scalar(select(model.id).where(model.code.startswith("DEMO-")))
                for model in (Department, Position, KPIDefinition)
            )
            employees = session.scalar(
                select(Employee.id).where(Employee.employee_code.startswith("DEMO-"))
            )
            if reserved or codes or employees:
                raise DemoConflict("Demo identifiers already exist without a complete seed marker.")
        DemoBuilder(session).build(PasswordService().hash(password))
    return True


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Add a fictional office demo without resetting data."
    )
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read two matching password lines; otherwise generate a random password.",
    )
    args = parser.parse_args(argv)
    try:
        settings = get_settings()
        if settings.app_env not in ("development", "test"):
            raise DemoConflict("Demo data is allowed only in development/test, never production.")
        password = _read_password(True) if args.password_stdin else secrets.token_urlsafe(18)
        engine = get_engine(settings)
        try:
            created = seed_demo(engine, password)
        finally:
            engine.dispose()
    except (DemoConflict, BootstrapInputError) as error:
        print(str(error), file=sys.stderr)
        return 1
    except (SQLAlchemyError, ApiError, ValueError):
        print("Demo creation failed; all changes were rolled back.", file=sys.stderr)
        return 1
    if not created:
        print("Demo already exists. Accounts, passwords and practice progress were not changed.")
        return 0
    print("Fictional office demo created. No AI provider was called.")
    for name, (_, role) in ACCOUNTS.items():
        print(f"{role.value:8} {email(name)}")
    print(f"Shared demo password (save it now): {password}")
    print("Walkthrough: docs/demo.vi.md. Existing accounts/data were retained.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
