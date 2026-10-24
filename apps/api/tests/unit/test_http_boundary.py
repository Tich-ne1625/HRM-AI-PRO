import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import Settings
from app.core.http_boundary import HTTPBoundary
from app.main import create_app


@pytest.mark.parametrize("declared", [None, b"1", b"999999"])
@pytest.mark.parametrize("size,status", [(1024, 200), (1025, 413)])
def test_actual_bytes_bounded_before_app_for_chunked_or_false_length(declared, size, status):
    calls, output = [], []

    async def app(scope, receive, send):
        calls.append(True)
        body = await Request(scope, receive).body()
        await JSONResponse({"size": len(body)})(scope, receive, send)

    messages = iter(
        [
            {"type": "http.request", "body": b"x" * 512, "more_body": True},
            {"type": "http.request", "body": b"x" * (size - 512)},
        ]
    )

    async def receive():
        return next(messages, {"type": "http.disconnect"})

    async def send(message):
        output.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/test",
        "query_string": b"",
        "headers": [(b"content-length", declared)] if declared else [],
    }
    asyncio.run(HTTPBoundary(app, limit=1024)(scope, receive, send))
    start = next(m for m in output if m["type"] == "http.response.start")
    assert start["status"] == status
    assert dict(start["headers"])[b"cache-control"] == b"no-store"
    assert bool(calls) == (status == 200)
    raw = b"".join(m.get("body", b"") for m in output)
    if status == 413:
        assert json.loads(raw)["error"]["code"] == "request_too_large" and "xxxx" not in str(raw)


def test_error_responses_are_private_and_secret_safe():
    app = create_app(Settings(_env_file=None, database_url="postgresql+psycopg://x:x@localhost/x"))

    @app.get("/api/v1/test-error")
    def explode():
        raise ValueError("SECRET_SENTINEL")

    for path, status in (
        ("/api/v1/unknown", 404),
        ("/api/v1/test-error", 500),
        ("/api/v1/auth/login", 405),
    ):
        response = TestClient(app, raise_server_exceptions=False).get(path)
        assert response.status_code == status
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "SECRET_SENTINEL" not in response.text
