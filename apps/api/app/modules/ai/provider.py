import asyncio
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import Settings
from app.modules.ai.input_builder import SYSTEM_PROMPT, canonical
from app.modules.ai.schemas import AnalysisOutput, parse_output


class ProviderError(Exception):
    """Only allowlisted codes may cross this boundary; never provider exception text."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ProviderResult:
    output: AnalysisOutput
    model: str | None = None


class Provider(Protocol):
    def generate(self, payload: dict[str, Any]) -> ProviderResult: ...


class GeminiProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(self, payload: dict[str, Any]) -> ProviderResult:
        try:
            return asyncio.run(self._generate(payload))
        except TimeoutError:
            raise ProviderError("provider_timeout") from None
        except ProviderError:
            raise
        except Exception as error:
            code = getattr(error, "code", 0)
            code = code if isinstance(code, int) else 0
            mapped = {
                401: "provider_configuration",
                403: "provider_configuration",
                429: "provider_quota",
            }.get(code, "provider_unavailable")
            raise ProviderError(mapped) from None

    async def _generate(self, payload: dict[str, Any]) -> ProviderResult:
        # Lazy import/client construction: keyless startup and saved GETs never initialize an SDK.
        from google import genai
        from google.genai import types

        owner = genai.Client(
            api_key=self.settings.gemini_api_key.get_secret_value(),
            vertexai=False,
            http_options=types.HttpOptions(
                api_version="v1beta",
                timeout=self.settings.gemini_timeout_seconds * 1000,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        client = owner.aio
        try:
            async with asyncio.timeout(self.settings.gemini_timeout_seconds):
                response = await client.models.generate_content(
                    model=self.settings.gemini_model,
                    contents=canonical(payload),
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        response_json_schema=AnalysisOutput.model_json_schema(),
                        max_output_tokens=self.settings.gemini_max_output_tokens,
                        tools=[],
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(
                            disable=True
                        ),
                    ),
                )
                candidates = response.candidates or []
                if len(candidates) != 1 or candidates[0].finish_reason != types.FinishReason.STOP:
                    raise ProviderError("provider_blocked")
                if not response.text:
                    raise ProviderError("provider_invalid_output")
                try:
                    output = parse_output(response.text)
                except ValueError:
                    raise ProviderError("provider_invalid_output") from None
                return ProviderResult(output, response.model_version)
        finally:
            try:
                await client.aclose()
            finally:
                owner.close()
