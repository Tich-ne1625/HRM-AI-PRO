from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.core.policies import AuthContext, get_auth_context
from app.modules.auth.router import require_csrf, require_same_origin
from app.modules.collaboration.schemas import ContentInput, PostInput, ReadInput
from app.modules.collaboration.service import CollaborationService

router = APIRouter(prefix="/api/v1/collaboration", tags=["collaboration"])
Actor = Annotated[AuthContext, Depends(get_auth_context)]
Database = Annotated[Session, Depends(get_db_session)]
Page = Annotated[int, Query(ge=1, le=10000)]


@router.get("/people")
def people(
    context: Actor,
    session: Database,
    search: Annotated[str, Query(max_length=100)] = "",
    page: Page = 1,
    post_id: UUID | None = None,
    own_department: bool = False,
    department_id: UUID | None = None,
) -> dict[str, Any]:
    return CollaborationService(session).directory(
        context.user, search, page, post_id, own_department, department_id
    )


@router.get("/posts")
def feed(
    context: Actor,
    session: Database,
    page: Page = 1,
    audience: Literal["all", "company", "department"] = "all",
) -> dict[str, Any]:
    return CollaborationService(session).feed(context.user, page, audience)


@router.get("/posts/{identifier}")
def detail(identifier: UUID, context: Actor, session: Database, page: Page = 1) -> dict[str, Any]:
    return CollaborationService(session).detail(context.user, identifier, page)


@router.post("/posts", status_code=201, dependencies=[Depends(require_same_origin)])
def publish(data: PostInput, context: Actor, session: Database, request: Request) -> dict[str, Any]:
    return CollaborationService(session).publish(
        context, lambda row: require_csrf(request, row), data, request.state.request_id
    )


@router.post(
    "/posts/{identifier}/comments", status_code=201, dependencies=[Depends(require_same_origin)]
)
def comment(
    identifier: UUID, data: ContentInput, context: Actor, session: Database, request: Request
) -> dict[str, Any]:
    return CollaborationService(session).publish(
        context, lambda row: require_csrf(request, row), data, request.state.request_id, identifier
    )


@router.get("/conversations")
def conversations(context: Actor, session: Database, page: Page = 1) -> dict[str, Any]:
    return CollaborationService(session).conversations(context.user, page)


@router.get("/messages/{identifier}")
def message_link(identifier: UUID, context: Actor, session: Database) -> dict[str, Any]:
    from sqlalchemy import or_, select

    from app.core.errors import ApiError
    from app.modules.collaboration.models import ChatMessage

    with session.begin():
        row = session.scalar(
            select(ChatMessage).where(
                ChatMessage.id == identifier,
                or_(
                    ChatMessage.sender_id == context.user.id,
                    ChatMessage.recipient_id == context.user.id,
                ),
            )
        )
        if row is None:
            raise ApiError(404, "message_not_found", "Message not found")
        return CollaborationService.message_view(row)


@router.get("/chat/{peer_id}")
def messages(
    peer_id: UUID, context: Actor, session: Database, before: UUID | None = None
) -> dict[str, Any]:
    return CollaborationService(session).messages(context.user, peer_id, before)


@router.post("/chat/{peer_id}", status_code=201, dependencies=[Depends(require_same_origin)])
def send(
    peer_id: UUID, data: ContentInput, context: Actor, session: Database, request: Request
) -> dict[str, Any]:
    return CollaborationService(session).send(
        context, lambda row: require_csrf(request, row), peer_id, data, request.state.request_id
    )


@router.post("/chat/{peer_id}/read", status_code=204, dependencies=[Depends(require_same_origin)])
def read(
    peer_id: UUID, data: ReadInput, context: Actor, session: Database, request: Request
) -> Response:
    CollaborationService(session).read(
        context, lambda row: require_csrf(request, row), peer_id, data.through_id
    )
    return Response(status_code=204)
