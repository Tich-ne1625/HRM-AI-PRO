"""OFFLINE TEST HARNESS, bind mounted only into a disposable acceptance container.

No fixture/provider switch is added to the production application or shipped image.
"""

import os

from pydantic import SecretStr
from sqlalchemy.engine import make_url

import app.modules.ai.service as service_module
from app.core.config import Settings
from app.main import create_app
from app.modules.ai.provider import ProviderError, ProviderResult
from app.modules.ai.schemas import AnalysisOutput

settings = Settings(_env_file=None)
assert settings.app_env == "test"
assert os.environ.get("PHASE9_PROJECT") == "insighthr-phase9-acceptance"
assert make_url(settings.database_url.get_secret_value()).database == "phase9_ui_test"
settings.gemini_enabled = True
settings.gemini_api_key = SecretStr("offline-test-only-key")
settings.gemini_model = "OFFLINE-TEST-PROVIDER"


class OfflineProvider:
    calls = 0

    def generate(self, payload):
        self.calls += 1
        if self.calls == 3:
            raise ProviderError("provider_quota")
        return ProviderResult(
            AnalysisOutput(
                summary="OFFLINE PRIVATE SENTINEL"
                if payload["audience"] == "HR_PRIVATE"
                else "OFFLINE PUBLIC ADVICE",
                strengths=["Fictional data only"],
                improvement_areas=[],
                feedback_themes=[],
                recommended_actions=["Discuss fictional goals"],
                caveats=["Injected test provider; never a live Gemini response."],
            ),
            "OFFLINE-TEST-PROVIDER",
        )


service_module.COOLDOWN_SECONDS = 0
app = create_app(settings)
app.state.ai_provider = OfflineProvider()
