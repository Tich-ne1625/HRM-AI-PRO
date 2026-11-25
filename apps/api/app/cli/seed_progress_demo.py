"""Fictional Phase 12 process story. Never seeds an existing company database."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.cli.seed_continuous_demo import ContinuousDemo
from app.cli.seed_demo import DemoConflict
from app.core.config import get_settings
from app.core.database import get_engine
from app.models import AuditLog, KPIDefinition, User
from app.modules.audit.service import AuditWriter
from app.modules.progress.checkins import CheckinService
from app.modules.progress.schemas import (
    CheckinCommand,
    CheckinCreate,
    FollowupCreate,
    MeasurementCommand,
    MeasurementDraft,
    PreparationDraft,
)
from app.modules.progress.service import ProgressService
from app.modules.review_cycles.activation import CycleActivation
from app.modules.work_management.schemas import PlanDraft, WorkAction, WorkCreate
from app.modules.work_management.service import WorkService

DATASET = "continuous-progress-demo-v1"


class ProgressDemo(ContinuousDemo):
    def foundation(self) -> None:
        super().foundation()
        with self.session.begin():
            definition = self.session.get(KPIDefinition, self.definition_id)
            assert definition is not None
            definition.name = "Yêu cầu hỗ trợ đã được xác minh"
            definition.unit = "yêu cầu"
            definition.description = (
                "Mỗi mã hồ sơ khách hàng có danh sách yêu cầu riêng không trùng; "
                "delta là số yêu cầu đạt QA trong hồ sơ đó, không phải số hồ sơ."
            )
            self.definitions: dict[str, UUID] = {"SUM": self.definition_id}
            for method, name, unit in [
                ("RATIO", "Tỷ lệ hồ sơ xử lý đúng hạn", "%"),
                ("MILESTONE", "Bàn giao quy trình CSKH có kiểm thử", "%"),
                ("LAST", "Snapshot hồ sơ đã đối chiếu lũy kế", "hồ sơ"),
            ]:
                row = KPIDefinition(
                    code=f"PROGRESS-{method}",
                    name=name,
                    unit=unit,
                    description="Dữ liệu minh họa cách đo, không phải điểm hiệu suất.",
                    direction="HIGHER_IS_BETTER",
                )
                self.session.add(row)
                self.session.flush()
                self.definitions[method] = row.id

    @staticmethod
    def command(version: int = 1, **values: Any) -> dict[str, Any]:
        return {"client_request_id": str(uuid4()), "expected_version": version, **values}

    def plan(self, participant: UUID) -> dict[str, object]:
        goals = []
        for method in ("SUM", "RATIO", "MILESTONE", "LAST"):
            goals.append(
                {
                    "definition_id": str(self.definitions[method]),
                    "baseline": "0",
                    "target": "95" if method == "RATIO" else "100",
                    "weight": "25",
                    "method": method,
                    "source": {
                        "SUM": (
                            "Mỗi nguồn là một hồ sơ khách hàng có danh sách yêu cầu riêng. "
                            "Khai số yêu cầu đạt QA, không ghi lại ở hồ sơ khác "
                            "và không cộng báo cáo tuần/tháng chồng lấn."
                        ),
                        "RATIO": (
                            "Mỗi hồ sơ ghi đúng hạn 0 hoặc 1 trên mẫu 1; "
                            "tổng hợp từ các mã không trùng."
                        ),
                        "MILESTONE": "Bộ mốc cố định đã thống nhất; mỗi mốc nghiệm thu một lần.",
                        "LAST": (
                            "Snapshot lũy kế tại từng thời điểm; lấy giá trị mới nhất, "
                            "không cộng các lần đo."
                        ),
                    }[method],
                    "acceptance": "Có nguồn đối chiếu, quản lý kiểm tra và ghi rõ quyết định.",
                    "numerator": "Hồ sơ đúng hạn" if method == "RATIO" else None,
                    "denominator": "Hồ sơ đã xử lý" if method == "RATIO" else None,
                    "milestones": [
                        {"title": "Thống nhất checklist và kiểm tra thử", "weight": "30"},
                        {"title": "Bàn giao, đào tạo và nghiệm thu", "weight": "70"},
                    ]
                    if method == "MILESTONE"
                    else [],
                }
            )
        return WorkService(self.session).save_plan(
            self.contexts["care.manager"],
            self.csrf,
            participant,
            PlanDraft.model_validate(
                self.command(
                    objective="Theo dõi công việc, số liệu có nguồn và hỗ trợ CSKH trong kỳ.",
                    goals=goals,
                )
            ),
            DATASET,
        )

    def measurement(
        self,
        plan: dict[str, Any],
        goal: dict[str, Any],
        key: str,
        *,
        verify: bool = True,
        work: dict[str, Any] | None = None,
        **values: Any,
    ) -> dict[str, Any]:
        service = ProgressService(self.session)
        row = service.save(
            self.contexts["care01"],
            self.csrf,
            UUID(str(goal["id"])),
            MeasurementDraft.model_validate(
                self.command(
                    plan["version"],
                    source_key=key,
                    source_kind="WORK" if work else "EXTERNAL_REFERENCE",
                    work_item_id=work["id"] if work else None,
                    occurred_at=values.pop(
                        "occurred_at", datetime.now(UTC) - timedelta(seconds=10)
                    ),
                    body="Đối chiếu sổ hồ sơ và kết quả QA. Dữ liệu hư cấu để thực hành.",
                    **values,
                )
            ),
            DATASET,
        )
        row = self.decide(row, "submit")
        return self.decide(row, "verify") if verify else row

    def decide(self, row: dict[str, Any], action: str) -> dict[str, Any]:
        actor = "care01" if action == "submit" else "care.manager"
        return ProgressService(self.session).command(
            self.contexts[actor],
            self.csrf,
            UUID(str(row["id"])),
            MeasurementCommand.model_validate(
                self.command(
                    row["version"],
                    action=action,
                    body="Đã đối chiếu nguồn và quy tắc; giữ nguyên lịch sử quyết định.",
                )
            ),
            DATASET,
        )

    def revise(
        self, row: dict[str, Any], *, kind: str = "VALUE", value: str | None = None
    ) -> dict[str, Any]:
        return ProgressService(self.session).save(
            self.contexts["care01"],
            self.csrf,
            UUID(str(row["goal_id"])),
            MeasurementDraft.model_validate(
                self.command(
                    row["version"],
                    source_key=row["source_key"],
                    source_kind=row["source_kind"],
                    work_item_id=row["work_item_id"],
                    occurred_at=row["occurred_at"],
                    kind=kind,
                    value=value,
                    body=(
                        "Đề nghị điều chỉnh sau đối chiếu lại sổ nguồn; không sửa bản đã xác minh."
                    ),
                )
            ),
            DATASET,
            UUID(str(row["id"])),
        )

    def work_item(
        self,
        plan: dict[str, Any],
        goal: dict[str, Any],
        key: str,
        title: str,
        *,
        accepted: bool = True,
    ) -> dict[str, Any]:
        service = WorkService(self.session)
        current = service.detail(self.contexts["care.manager"].user, UUID(str(plan["id"])))
        row = service.create_work(
            self.contexts["care.manager"],
            self.csrf,
            UUID(str(plan["id"])),
            WorkCreate.model_validate(
                self.command(
                    current["version"],
                    title=title,
                    source_key=key,
                    goal_id=goal["id"],
                    acceptance="Có xác nhận khách hàng và đối chiếu QA.",
                    due_at=datetime.now(UTC) + timedelta(days=3),
                )
            ),
            DATASET,
        )
        if accepted:
            for action, actor in [
                ("start", "care01"),
                ("submit", "care01"),
                ("accept", "care.manager"),
            ]:
                row = service.action(
                    self.contexts[actor],
                    self.csrf,
                    UUID(str(row["id"])),
                    WorkAction.model_validate(
                        self.command(
                            row["version"],
                            action=action,
                            body="Đủ hồ sơ, xác nhận và bằng chứng đối chiếu QA.",
                        )
                    ),
                    DATASET,
                )
        return row

    def story(self) -> None:
        cycle_id, participant = self.cycle("[PHASE 12] CSKH — số liệu có nguồn và hỗ trợ")
        plan: dict[str, Any] = self.plan(participant)
        for action, actor in [
            ("submit", "care.manager"),
            ("approve", "care.manager"),
            ("acknowledge", "care01"),
        ]:
            plan = self.advance_plan(plan, action, actor)
        cycle = CycleActivation(self.session).activate(
            cycle_id, 2, self.contexts["hr"], csrf=self.csrf, request_id=DATASET
        )
        goals = {g["method"]: g for g in plan["goals"]}
        self.work_item(
            plan, goals["SUM"], "P12-101", "Hồ sơ mới để thực hành từ đầu", accepted=False
        )
        verified_work = self.work_item(
            plan, goals["SUM"], "P12-102", "Hồ sơ đã nghiệm thu, có số xác minh"
        )
        plan = WorkService(self.session).detail(
            self.contexts["care.manager"].user, UUID(str(plan["id"]))
        )
        verified = self.measurement(plan, goals["SUM"], "P12-102", work=verified_work, value="5")
        self.decide(self.revise(verified, value="4"), "submit")
        returned = self.measurement(plan, goals["SUM"], "P12-RETURNED", verify=False, value="3")
        self.decide(returned, "return")
        self.measurement(plan, goals["SUM"], "P12-PENDING", verify=False, value="2")
        withdrawn = self.measurement(plan, goals["SUM"], "P12-VOID", value="2")
        self.decide(self.decide(self.revise(withdrawn, kind="VOID"), "submit"), "verify")
        reopened = self.work_item(
            plan, goals["SUM"], "P12-REOPEN", "Hồ sơ cần bổ sung sau nghiệm thu"
        )
        plan = WorkService(self.session).detail(
            self.contexts["care.manager"].user, UUID(str(plan["id"]))
        )
        self.measurement(plan, goals["SUM"], "P12-REOPEN", work=reopened, value="7")
        WorkService(self.session).action(
            self.contexts["care.manager"],
            self.csrf,
            UUID(str(reopened["id"])),
            WorkAction.model_validate(
                self.command(
                    reopened["version"],
                    action="reopen",
                    body="Cần bổ sung liên kết QA; tạm ngừng tính nguồn này.",
                )
            ),
            DATASET,
        )
        for index, on_time in enumerate([1] * 9 + [0, 1, 0], 1):
            self.measurement(
                plan, goals["RATIO"], f"P12-SLA-{index:03}", numerator=str(on_time), denominator="1"
            )
        for offset, value in [(180, "20"), (120, "35"), (60, "50")]:
            self.measurement(
                plan,
                goals["LAST"],
                f"P12-SNAPSHOT-{value}",
                value=value,
                occurred_at=datetime.now(UTC) - timedelta(seconds=offset),
            )
        self.measurement(plan, goals["MILESTONE"], "P12-MILESTONE-1", milestone=0)
        self.measurement(plan, goals["MILESTONE"], "P12-MILESTONE-2", milestone=1, verify=False)
        service = CheckinService(self.session)
        meeting = service.create(
            self.contexts["care.manager"],
            self.csrf,
            UUID(str(plan["id"])),
            CheckinCreate.model_validate(
                self.command(
                    plan["version"],
                    title="Rà soát tuần — hỗ trợ hồ sơ còn vướng",
                    scheduled_at=datetime.now(UTC) + timedelta(hours=2),
                    period_start=cycle.start_date,
                    period_end=datetime.now(UTC).date(),
                )
            ),
            DATASET,
        )
        service.prepare(
            self.contexts["care01"],
            self.csrf,
            UUID(str(meeting["id"])),
            PreparationDraft.model_validate(
                self.command(body="Tôi cần quản lý hỗ trợ nguồn QA của hồ sơ mở lại.", shared=True)
            ),
            DATASET,
        )
        for action, body in [
            ("open", None),
            (
                "publish",
                (
                    "Số đang chờ không cộng vào tổng. Mai Anh hỗ trợ đối tác cung cấp QA; "
                    "Huy bổ sung hồ sơ."
                ),
            ),
        ]:
            meeting = service.command(
                self.contexts["care.manager"],
                self.csrf,
                UUID(str(meeting["id"])),
                CheckinCommand.model_validate(
                    self.command(meeting["version"], action=action, body=body)
                ),
                DATASET,
            )
        for actor in ("care.manager", "care01"):
            service.followup(
                self.contexts["care.manager"],
                self.csrf,
                UUID(str(meeting["id"])),
                FollowupCreate.model_validate(
                    self.command(
                        meeting["version"],
                        owner_id=self.contexts[actor].user.id,
                        body="Liên hệ đối tác lấy kết quả QA"
                        if actor == "care.manager"
                        else "Bổ sung bằng chứng và nộp lại số đo",
                        due_at=datetime.now(UTC) + timedelta(days=2),
                    )
                ),
                DATASET,
            )
            meeting = service.detail(
                self.contexts["care.manager"].user, UUID(str(meeting["id"])), 1
            )
        second = service.create(
            self.contexts["care.manager"],
            self.csrf,
            UUID(str(plan["id"])),
            CheckinCreate.model_validate(
                self.command(
                    plan["version"],
                    title="Chuẩn bị cuộc rà soát kế tiếp",
                    scheduled_at=datetime.now(UTC) + timedelta(days=7),
                    period_start=cycle.start_date,
                    period_end=cycle.end_date,
                )
            ),
            DATASET,
        )
        service.prepare(
            self.contexts["care01"],
            self.csrf,
            UUID(str(second["id"])),
            PreparationDraft.model_validate(
                self.command(
                    body="Ghi chú riêng để chuẩn bị; chưa chia sẻ cho quản lý.", shared=False
                )
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


def seed_progress_demo(engine: Engine) -> bool:
    if not (engine.url.database or "").endswith("_test"):
        raise DemoConflict("Progress demo requires an empty isolated _test database")
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
        builder = ProgressDemo(session)
        builder.foundation()
        builder.story()
    return True


def main() -> int:
    settings = get_settings()
    if settings.app_env not in {"development", "test"}:
        print("Progress demo is development/test only", file=sys.stderr)
        return 1
    engine = get_engine(settings)
    try:
        print(
            "Progress demo created"
            if seed_progress_demo(engine)
            else "Progress demo already exists"
        )
        return 0
    except DemoConflict as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
