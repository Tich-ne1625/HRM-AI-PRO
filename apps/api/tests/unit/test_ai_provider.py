import asyncio
import json

import httpx
import pytest
from google import genai

from app.core.config import Settings
from app.modules.ai.provider import GeminiProvider, ProviderError

OUTPUT = {
    "summary": "Advice",
    "strengths": [],
    "improvement_areas": [],
    "feedback_themes": [],
    "recommended_actions": [],
    "caveats": ["Advisory"],
}


@pytest.mark.parametrize(
    "status,code",
    [
        (400, "provider_configuration"),
        (404, "provider_model_unavailable"),
        (429, "provider_quota"),
        (503, "provider_unavailable"),
        (403, "provider_configuration"),
        (200, None),
    ],
)
def test_real_sdk_transport_has_no_retries_or_tools(monkeypatch, caplog, status, code):
    calls = []
    clients = []
    closed = []
    real_client = genai.Client

    async def handler(request):
        calls.append(json.loads(request.content))
        assert request.headers["x-goog-api-key"] == "offline-key"
        if status != 200:
            return httpx.Response(status, json={"error": {"code": status, "message": "SECRET"}})
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": json.dumps(OUTPUT)}], "role": "model"},
                    }
                ],
                "modelVersion": "offline-model",
            },
        )

    def factory(**kwargs):
        options = kwargs["http_options"]
        assert options.timeout == 5000 and options.retry_options.attempts == 1
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        clients.append(client)
        options.httpx_async_client = client
        sdk = real_client(**kwargs)
        original_close = sdk.aio.aclose

        async def close():
            await original_close()
            closed.append(True)
            # Injected transport belongs to this test; the SDK deliberately does not own it.
            await client.aclose()

        sdk.aio.aclose = close
        return sdk

    monkeypatch.setattr(genai, "Client", factory)
    provider = GeminiProvider(
        Settings(
            _env_file=None,
            gemini_enabled=True,
            gemini_api_key="offline-key",
            gemini_model="offline-model",
            gemini_timeout_seconds=5,
        )
    )
    if code:
        with pytest.raises(ProviderError, match=code) as error:
            provider.generate({"audience": "PUBLIC"})
        assert "SECRET" not in str(error.value)
    else:
        assert provider.generate({"audience": "PUBLIC"}).output.summary == "Advice"
    assert len(calls) == 1
    assert not calls[0]["generationConfig"].get("tools")
    assert not calls[0].get("tools")
    assert all(client.is_closed for client in clients)
    assert closed == [True]
    assert "SECRET" not in caplog.text and "offline-key" not in caplog.text


def test_total_timeout_and_cleanup(monkeypatch):
    closed = []

    class Client:
        @property
        def aio(self):
            return self

        @property
        def models(self):
            return self

        async def generate_content(self, **kwargs):
            await asyncio.sleep(1)

        async def aclose(self):
            closed.append(True)

        def close(self):
            pass

    monkeypatch.setattr(genai, "Client", lambda **kwargs: Client())
    settings = Settings(_env_file=None, gemini_timeout_seconds=5)
    settings.gemini_timeout_seconds = 0.01
    with pytest.raises(ProviderError, match="provider_timeout"):
        GeminiProvider(settings).generate({})
    assert closed == [True]
