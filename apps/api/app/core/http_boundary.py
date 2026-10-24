"""Bounded ASGI ingress: consume at most limit+one chunk, before any domain work."""

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import _request_id, _response


class HTTPBoundary:
    def __init__(self, app: ASGIApp, *, limit: int, https: bool = False) -> None:
        self.app, self.limit, self.https = app, limit, https

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        api = scope["path"].startswith("/api/v1/")

        async def secured_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                if api:
                    headers["Cache-Control"] = "no-store"
                    headers["Content-Security-Policy"] = (
                        "default-src 'none'; frame-ancestors 'none'"
                    )
                if self.https:
                    headers["Strict-Transport-Security"] = "max-age=31536000"
            await send(message)

        if not api:
            await self.app(scope, receive, secured_send)
            return
        scope.setdefault("state", {})["request_id"] = _request_id(Request(scope))
        body_buffer = bytearray()
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.limit:
                await _response(
                    Request(scope),
                    413,
                    "request_too_large",
                    "Request body exceeds the allowed size",
                )(scope, receive, secured_send)
                return
            body_buffer.extend(chunk)
            if not message.get("more_body", False):
                break
        body = bytes(body_buffer)
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, secured_send)
