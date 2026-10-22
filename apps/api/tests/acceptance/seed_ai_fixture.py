"""OFFLINE acceptance fixture, host test runner only; never shipped in runtime."""

import sys
from datetime import timedelta
from uuid import uuid4

from pydantic import SecretStr
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.modules.ai.service as service_module
from app.core.config import Settings
from app.core.policies import AuthContext
from app.models import AIAnalysis, AuthSession, PerformanceReview, User, UserRole
from app.modules.ai.provider import ProviderError, ProviderResult
from app.modules.ai.schemas import AnalysisOutput, Audience, GenerateInput
from app.modules.ai.service import AIService

assert len(sys.argv) == 2 and sys.argv[1] in {"insighthr-ci", "insighthr-phase7-acceptance"}
settings = Settings(_env_file=None)
assert settings.app_env in {"development", "test"}
engine = create_engine(settings.database_url.get_secret_value())
assert engine.url.host == "postgres" and engine.url.database == "insighthr"
settings.gemini_enabled = True
settings.gemini_api_key = SecretStr("offline-fixture-key")
settings.gemini_model = "demo-fixture"
service_module.COOLDOWN_SECONDS = 0


class Provider:
    fail = False

    def generate(self, payload):
        if self.fail:
            raise ProviderError("provider_timeout")
        private = payload["audience"] == "HR_PRIVATE"
        return ProviderResult(
            AnalysisOutput(
                summary="OFFLINE DEMO: "
                + ("HR PRIVATE SENTINEL" if private else "PUBLIC ADVISORY"),
                strengths=["Fictional test advice"],
                improvement_areas=[],
                feedback_themes=[],
                recommended_actions=["Discuss goals with the employee"],
                caveats=["Synthetic injected-provider output; never a live Gemini response."],
            ),
            "demo-fixture",
        )


with Session(engine, expire_on_commit=False) as session:
    user = session.scalars(select(User).where(User.role == UserRole.HR, User.is_active)).first()
    auth = session.scalars(
        select(AuthSession).where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
            AuthSession.consumed_at.is_(None),
        )
    ).first()
    review = session.scalars(select(PerformanceReview)).one()
    assert not session.scalars(select(AIAnalysis)).first(), "Fixture must start empty"
    context = AuthContext(user=user, session=auth, family_id=auth.family_id)
    session.commit()
    provider = Provider()
    service = AIService(session, settings, provider)

    def body(audience, regenerate=False):
        return GenerateInput(
            client_request_id=uuid4(),
            audience=audience,
            expected_calculation_version=review.calculation_version,
            expected_evidence_version=review.evidence_version,
            regenerate=regenerate,
            expected_latest_generation=1 if regenerate else None,
        )

    for audience in (Audience.PUBLIC, Audience.HR_PRIVATE):
        service.generate(review.id, body(audience), context, lambda _: None, "offline-fixture")
    provider.fail = True
    try:
        service.generate(
            review.id,
            body(Audience.PUBLIC, True),
            context,
            lambda _: None,
            "offline-fixture-failure",
        )
    except Exception as error:
        assert getattr(error, "code", None) == "provider_timeout"
    reservation, _, _ = service.reserve(
        review.id,
        body(Audience.HR_PRIVATE, True),
        context,
        lambda _: None,
        "offline-fixture-expiry",
    )
    with session.begin():
        row = session.get(AIAnalysis, reservation.id)
        row.reserved_at -= timedelta(seconds=120)
        row.lease_until -= timedelta(seconds=120)
engine.dispose()
print("OFFLINE fixture: two audience successes, failed regeneration and expired lease saved.")
