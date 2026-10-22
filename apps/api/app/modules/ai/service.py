import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.domain_writes import CsrfCheck, authorize_domain_write, require_version
from app.core.errors import ApiError
from app.core.policies import AuthContext
from app.modules.ai.input_builder import (
    PROMPT_VERSION,
    REDACTION_VERSION,
    SCHEMA_VERSION,
    build_payload,
    fingerprint,
)
from app.modules.ai.models import AIAnalysis, AnalysisStatus
from app.modules.ai.provider import Provider, ProviderError, ProviderResult
from app.modules.ai.schemas import (
    AnalysisOutput,
    AnalysisState,
    AnalysisView,
    Audience,
    GenerateInput,
)
from app.modules.audit.service import AuditWriter
from app.modules.employees.models import Employee
from app.modules.feedback.models import Feedback, FeedbackAssignment
from app.modules.organization.schemas import Page
from app.modules.performance.engine import ENGINE_VERSION
from app.modules.performance.models import PerformanceReview, PerformanceReviewRevision
from app.modules.performance.service import PerformanceService
from app.modules.review_cycles.models import CycleParticipant, CycleStatus, ReviewCycle
from app.modules.users.models import User, UserRole

COOLDOWN_SECONDS = 30
LEASE_SECONDS = 60
ERROR_STATUS = {
    "provider_timeout": 504,
    "provider_invalid_output": 502,
    "provider_blocked": 502,
    "provider_configuration": 503,
    "provider_quota": 503,
    "provider_unavailable": 503,
    "analysis_stale": 409,
    "generation_expired": 409,
    "authority_changed": 403,
}


@dataclass(frozen=True)
class Reservation:
    id: UUID
    review_id: UUID
    participant_id: UUID
    cycle_id: UUID
    fence: UUID
    payload: dict[str, Any]


class AIService:
    def __init__(self, session: Session, settings: Settings, provider: Provider) -> None:
        self.session = session
        self.settings = settings
        self.provider = provider
        self.performance = PerformanceService(session)

    def now(self) -> datetime:
        value = self.session.scalar(select(func.clock_timestamp()))
        assert value is not None
        return cast(datetime, value)

    @staticmethod
    def audience(user: User, audience: Audience) -> None:
        if audience == Audience.HR_PRIVATE and user.role != UserRole.HR:
            raise ApiError(403, "forbidden", "HR access is required")

    @staticmethod
    def current(
        review: PerformanceReview, participant: CycleParticipant, cycle: ReviewCycle
    ) -> bool:
        if (
            review.evidence_version != participant.evidence_version
            or cycle.status == CycleStatus.DRAFT
        ):
            return False
        if review.finalized_at or participant.finalized_at:
            return bool(review.finalized_at and review.finalized_at == participant.finalized_at)
        return cycle.status == CycleStatus.ACTIVE and review.engine_version == ENGINE_VERSION

    @staticmethod
    def view(row: AIAnalysis, now: datetime) -> AnalysisView:
        expired = row.status == AnalysisStatus.RUNNING and row.lease_until <= now
        return AnalysisView(
            id=row.id,
            audience=row.audience,
            generation_version=row.generation_version,
            calculation_version=row.calculation_version,
            evidence_version=row.evidence_version,
            status="FAILED" if expired else row.status.value,
            model=row.actual_model or row.model,
            prompt_version=row.prompt_version,
            reserved_at=row.reserved_at,
            generated_at=row.generated_at,
            error_code="generation_expired" if expired else row.error_code,
            output=AnalysisOutput.model_validate(row.output) if row.output is not None else None,
            input_sampled=row.input_sampled,
        )

    def query(self, review_id: UUID, audience: Audience) -> Select[AIAnalysis]:
        return select(AIAnalysis).where(
            AIAnalysis.review_id == review_id, AIAnalysis.audience == audience
        )

    def state(self, identifier: UUID, audience: Audience, user: User) -> AnalysisState:
        self.audience(user, audience)
        with self.session.begin():
            self.performance.repeatable_read()
            review, participant, _, cycle = self.performance.scoped_review(identifier, user)
            now = self.now()
            query = self.query(identifier, audience).order_by(AIAnalysis.generation_version.desc())
            latest = self.session.scalar(query.limit(1))
            successful = self.session.scalar(
                query.where(AIAnalysis.status == AnalysisStatus.SUCCEEDED).limit(1)
            )
            current = (
                successful
                if successful
                and self.current(review, participant, cycle)
                and successful.calculation_version == review.calculation_version
                and successful.evidence_hash == review.evidence_hash
                else None
            )
            expired = bool(
                latest and latest.status == AnalysisStatus.RUNNING and latest.lease_until <= now
            )
            running = bool(latest and latest.status == AnalysisStatus.RUNNING and not expired)
            state = (
                "CURRENT"
                if current
                else "RUNNING"
                if running
                else "STALE"
                if successful
                else "FAILED"
                if latest
                else "NOT_GENERATED"
            )
            allowed = (
                user.role == UserRole.HR
                and self.settings.gemini_enabled
                and self.current(review, participant, cycle)
            )
            return AnalysisState(
                audience=audience,
                state=state,
                configured=self.settings.gemini_enabled,
                can_generate=allowed and not running,
                can_retry=allowed
                and latest is not None
                and (expired or latest.status == AnalysisStatus.FAILED),
                current_analysis=self.view(current, now) if current else None,
                last_successful_analysis=self.view(successful, now) if successful else None,
                latest_attempt=self.view(latest, now) if latest else None,
            )

    def history(
        self, identifier: UUID, audience: Audience, user: User, page: int, page_size: int
    ) -> Page[AnalysisView]:
        self.audience(user, audience)
        with self.session.begin():
            self.performance.repeatable_read()
            self.performance.scoped_review(identifier, user)
            query = self.query(identifier, audience)
            total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
            rows = self.session.scalars(
                query.order_by(AIAnalysis.generation_version.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            now = self.now()
            return Page(
                items=[self.view(row, now) for row in rows],
                total=total,
                page=page,
                page_size=page_size,
            )

    def detail(self, identifier: UUID, analysis_id: UUID, user: User) -> AnalysisView:
        with self.session.begin():
            self.performance.repeatable_read()
            self.performance.scoped_review(identifier, user)
            # Apply audience in SQL, even when a caller guesses a private UUID.
            query = select(AIAnalysis).where(
                AIAnalysis.id == analysis_id, AIAnalysis.review_id == identifier
            )
            if user.role != UserRole.HR:
                query = query.where(AIAnalysis.audience == Audience.PUBLIC)
            row = self.session.scalar(query)
            if row is None:
                raise ApiError(404, "analysis_not_found", "Analysis not found")
            return self.view(row, self.now())

    def locked(
        self, review_id: UUID, participant_id: UUID, cycle_id: UUID
    ) -> tuple[PerformanceReview, CycleParticipant, ReviewCycle]:
        cycle = self.session.get(
            ReviewCycle, cycle_id, with_for_update=True, populate_existing=True
        )
        participant = self.session.get(
            CycleParticipant, participant_id, with_for_update=True, populate_existing=True
        )
        review = self.session.get(
            PerformanceReview, review_id, with_for_update=True, populate_existing=True
        )
        assert cycle is not None and participant is not None and review is not None
        return review, participant, cycle

    def audit(self, row: AIAnalysis, actor_id: UUID | None, action: str, request_id: str) -> None:
        AuditWriter().record(
            self.session,
            actor_id,
            action,
            "ai_analysis",
            str(row.id),
            request_id,
            {
                "review_id": str(row.review_id),
                "audience": row.audience.value,
                "generation_version": row.generation_version,
                "calculation_version": row.calculation_version,
                "evidence_version": row.evidence_version,
                "model": row.model,
                "prompt_version": row.prompt_version,
                "error_code": row.error_code,
            },
        )

    def failed(self, row: AIAnalysis, code: str, now: datetime) -> None:
        row.status, row.error_code, row.completed_at = AnalysisStatus.FAILED, code, now
        row.output, row.generated_at = None, None

    def payload(self, review: PerformanceReview, audience: Audience) -> tuple[dict[str, Any], bool]:
        revision = self.session.scalar(
            select(PerformanceReviewRevision).where(
                PerformanceReviewRevision.review_id == review.id,
                PerformanceReviewRevision.calculation_version == review.calculation_version,
            )
        )
        if revision is None or revision.evidence_hash != review.evidence_hash:
            raise ApiError(409, "evidence_inconsistent", "Calculation revision is inconsistent")
        comments: list[str] = []
        identifiers: list[str] = []
        if audience == Audience.HR_PRIVATE:
            snapshot = revision.evidence_snapshot
            assignments = snapshot["assignments"]
            assert isinstance(assignments, list)
            ids = [UUID(a["id"]) for a in assignments if a["status"] == "SUBMITTED"]
            rows = self.session.execute(
                select(Feedback.comment, User.email, Employee.display_name, Employee.employee_code)
                .join(FeedbackAssignment, Feedback.assignment_id == FeedbackAssignment.id)
                .join(User, FeedbackAssignment.reviewer_id == User.id)
                .join(Employee, FeedbackAssignment.reviewer_employee_id == Employee.id)
                .where(FeedbackAssignment.id.in_(ids))
            ).all()
            comments = [r[0] for r in rows]
            identifiers = [value for r in rows for value in r[1:]]
            subject = snapshot.get("subject", {})
            if isinstance(subject, dict):
                identifiers.extend(str(value) for value in subject.values())
        try:
            return build_payload(
                revision.evidence_snapshot,
                revision.policy_snapshot,
                {
                    key: format(getattr(revision, key), ".2f")
                    for key in ("kpi_score", "feedback_score", "final_score")
                },
                audience.value,
                comments,
                identifiers,
            )
        except ValueError:
            raise ApiError(
                409, "ai_input_too_large", "The analysis input exceeds the allowed size"
            ) from None

    def reserve(
        self,
        identifier: UUID,
        body: GenerateInput,
        context: AuthContext,
        csrf: CsrfCheck,
        request_id: str,
    ) -> tuple[Reservation | None, AnalysisView, int]:
        with self.session.begin():
            actor = authorize_domain_write(self.session, context, csrf, (UserRole.HR,))
            scoped, part, _, cycle = self.performance.scoped_review(identifier, actor)
            review, participant, cycle = self.locked(scoped.id, part.id, cycle.id)
            now = self.now()
            intent = fingerprint({"review_id": str(identifier), **body.model_dump(mode="json")})
            replay = self.session.scalar(
                select(AIAnalysis).where(
                    AIAnalysis.requested_by == actor.id,
                    AIAnalysis.client_request_id == body.client_request_id,
                )
            )
            if replay:
                if replay.request_fingerprint != intent:
                    raise ApiError(
                        409, "idempotency_conflict", "This request ID belongs to a different intent"
                    )
                return (
                    None,
                    self.view(replay, now),
                    202
                    if replay.status == AnalysisStatus.RUNNING and replay.lease_until > now
                    else 200,
                )
            require_version(
                participant.evidence_version, body.expected_evidence_version, evidence=True
            )
            if review.calculation_version != body.expected_calculation_version:
                raise ApiError(
                    409, "stale_calculation_version", "Calculation changed; reload explicitly"
                )
            if not self.current(review, participant, cycle):
                raise ApiError(409, "review_stale", "Recalculate before requesting advice")
            successful = self.session.scalar(
                self.query(identifier, body.audience)
                .where(
                    AIAnalysis.status == AnalysisStatus.SUCCEEDED,
                    AIAnalysis.calculation_version == review.calculation_version,
                    AIAnalysis.evidence_hash == review.evidence_hash,
                )
                .order_by(AIAnalysis.generation_version.desc())
                .limit(1)
            )
            if successful and not body.regenerate:
                return None, self.view(successful, now), 200
            expected = successful.generation_version if successful else 0
            if body.regenerate and body.expected_latest_generation != expected:
                raise ApiError(
                    409, "stale_analysis_version", "Analysis changed; review the latest generation"
                )
            if not self.settings.gemini_enabled:
                raise ApiError(503, "ai_not_configured", "Gemini is not configured")
            running = self.session.scalar(
                select(AIAnalysis)
                .where(
                    AIAnalysis.review_id == identifier, AIAnalysis.status == AnalysisStatus.RUNNING
                )
                .with_for_update()
            )
            if running:
                if running.lease_until > now:
                    raise ApiError(409, "generation_in_progress", "An analysis is already running")
                self.failed(running, "generation_expired", now)
                self.audit(running, actor.id, "ai_analysis.expired", request_id)
                self.session.flush()
            previous = self.session.scalar(
                select(func.max(AIAnalysis.reserved_at)).where(AIAnalysis.review_id == identifier)
            )
            if previous and now < previous + timedelta(seconds=COOLDOWN_SECONDS):
                raise ApiError(
                    429, "generation_cooldown", "Wait before requesting another analysis"
                )
            payload, sampled = self.payload(review, body.audience)
            version = (
                self.session.scalar(
                    select(func.max(AIAnalysis.generation_version)).where(
                        AIAnalysis.review_id == identifier, AIAnalysis.audience == body.audience
                    )
                )
                or 0
            ) + 1
            row = AIAnalysis(
                review_id=identifier,
                audience=body.audience,
                status=AnalysisStatus.RUNNING,
                generation_version=version,
                calculation_version=review.calculation_version,
                evidence_version=review.evidence_version,
                engine_version=review.engine_version,
                evidence_hash=review.evidence_hash,
                input_hash=fingerprint(
                    {
                        "payload": payload,
                        "model": self.settings.gemini_model,
                        "prompt": PROMPT_VERSION,
                        "redaction": REDACTION_VERSION,
                        "schema": SCHEMA_VERSION,
                    }
                ),
                prompt_version=PROMPT_VERSION,
                redaction_version=REDACTION_VERSION,
                schema_version=SCHEMA_VERSION,
                model=self.settings.gemini_model,
                requested_by=actor.id,
                client_request_id=body.client_request_id,
                request_fingerprint=intent,
                reserved_at=now,
                lease_until=now + timedelta(seconds=LEASE_SECONDS),
                input_sampled=sampled,
            )
            self.session.add(row)
            self.session.flush()
            self.audit(row, actor.id, "ai_analysis.requested", request_id)
            return (
                Reservation(
                    row.id, review.id, participant.id, cycle.id, row.fencing_token, payload
                ),
                self.view(row, now),
                201,
            )

    def complete(
        self,
        reservation: Reservation,
        result: ProviderResult | None,
        provider_error: str | None,
        context: AuthContext,
        csrf: CsrfCheck,
        request_id: str,
    ) -> AnalysisView:
        failure: ApiError | None = None
        with self.session.begin():
            try:
                actor = authorize_domain_write(self.session, context, csrf, (UserRole.HR,))
            except ApiError as denied:
                actor = None
                failure = denied
            # Trusted reservation IDs only: internal cleanup may mark a revoked caller's
            # attempt failed, but must never return its output to that caller.
            review, participant, cycle = self.locked(
                reservation.review_id, reservation.participant_id, reservation.cycle_id
            )
            row = self.session.get(
                AIAnalysis, reservation.id, with_for_update=True, populate_existing=True
            )
            assert row is not None
            now = self.now()
            if row.status != AnalysisStatus.RUNNING or row.fencing_token != reservation.fence:
                failure = failure or ApiError(
                    409, "generation_expired", "The generation lease is no longer active"
                )
            else:
                code = provider_error
                if failure:
                    code = "authority_changed"
                elif row.lease_until <= now:
                    code = "generation_expired"
                elif (
                    not self.current(review, participant, cycle)
                    or review.calculation_version != row.calculation_version
                    or review.evidence_hash != row.evidence_hash
                ):
                    code = "analysis_stale"
                if code:
                    self.failed(row, code, now)
                    failure = failure or ApiError(
                        ERROR_STATUS[code],
                        code,
                        "Analysis could not be completed; retry deliberately",
                    )
                else:
                    assert result is not None
                    # Validate even injected providers: this is the persistence boundary.
                    output = AnalysisOutput.model_validate(result.output.model_dump())
                    row.status, row.output = AnalysisStatus.SUCCEEDED, output.model_dump()
                    row.completed_at = row.generated_at = now
                    row.actual_model = result.model
                self.audit(
                    row,
                    actor.id if actor else None,
                    "ai_analysis.succeeded"
                    if row.status == AnalysisStatus.SUCCEEDED
                    else "ai_analysis.failed",
                    request_id,
                )
            self.session.flush()
            view = self.view(row, now)
        if failure:
            raise failure
        return view

    def generate(
        self,
        identifier: UUID,
        body: GenerateInput,
        context: AuthContext,
        csrf: CsrfCheck,
        request_id: str,
    ) -> tuple[AnalysisView, int]:
        reservation, view, status = self.reserve(identifier, body, context, csrf, request_id)
        if reservation is None:
            return view, status
        result: ProviderResult | None = None
        error: str | None = None
        try:
            result = self.provider.generate(reservation.payload)
            AnalysisOutput.model_validate(result.output.model_dump())
            if result.model and (
                len(result.model) > 128 or not re.fullmatch(r"[A-Za-z0-9._/-]+", result.model)
            ):
                raise ProviderError("provider_invalid_output")
        except ProviderError as problem:
            error = (
                problem.code
                if problem.code in ERROR_STATUS and problem.code.startswith("provider_")
                else "provider_unavailable"
            )
        except Exception:
            error = "provider_invalid_output"
        return self.complete(reservation, result, error, context, csrf, request_id), status
