from collections.abc import AsyncIterator
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.core.database import get_db_session
from app.core.errors import ApiError
from app.core.policies import AuthContext, get_auth_context
from app.core.security import ACCESS_COOKIE_NAME, TokenService
from app.modules.auth.router import require_csrf, require_same_origin
from app.modules.notifications.realtime import NotificationHub, stream
from app.modules.notifications.schemas import NotificationPage, WorkPage
from app.modules.notifications.service import NotificationService

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])
Reader = Annotated[AuthContext, Depends(get_auth_context)]
Database = Annotated[Session, Depends(get_db_session)]


@router.get("", response_model=NotificationPage)
def inbox(
    context: Reader,
    session: Database,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
    unread: bool = False,
) -> NotificationPage:
    return NotificationService(session).list(
        context.user, page=page, page_size=page_size, unread=unread
    )


@router.get("/tasks", response_model=WorkPage)
def tasks(context: Reader, session: Database) -> WorkPage:
    return NotificationService(session).tasks(context.user)


@router.post("/read-all", status_code=204, dependencies=[Depends(require_same_origin)])
def read_all(context: Reader, session: Database, request: Request) -> Response:
    NotificationService(session).read(context, lambda row: require_csrf(request, row), None)
    return Response(status_code=204)


@router.post("/{identifier}/read", status_code=204, dependencies=[Depends(require_same_origin)])
def read_one(identifier: UUID, context: Reader, session: Database, request: Request) -> Response:
    NotificationService(session).read(context, lambda row: require_csrf(request, row), identifier)
    return Response(status_code=204)


@router.get("/events")
def events(context: Reader, request: Request) -> StreamingResponse:
    settings = request.app.state.settings
    origin = request.headers.get("origin")
    if (origin and origin != settings.web_origin) or request.headers.get(
        "sec-fetch-site"
    ) == "cross-site":
        raise ApiError(403, "forbidden", "Access is forbidden")
    hub = cast(NotificationHub, request.app.state.notification_hub)

    # Subscription belongs to the ASGI event loop, not this synchronous endpoint's worker.
    async def body() -> AsyncIterator[str]:
        try:
            queue = hub.subscribe(context.user.id)
        except ValueError:
            yield "event: reconnect\ndata: {}\n\n"
            return
        async for chunk in stream(
            hub,
            queue,
            request.app.state.session_factory,
            TokenService(settings.access_signing_key),
            request.cookies.get(ACCESS_COOKIE_NAME, ""),
            context.user.id,
            context.family_id,
            context.user.role,
        ):
            yield chunk

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store, no-transform", "X-Accel-Buffering": "no"},
    )
