from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.core.policies import AuthContext, get_auth_context
from app.modules.auth.router import require_csrf, require_same_origin
from app.modules.work_management.schemas import PlanAction, PlanDraft, WorkAction, WorkCreate
from app.modules.work_management.service import WorkService

router = APIRouter(prefix="/api/v1/work-management", tags=["work-management"])
Actor = Annotated[AuthContext, Depends(get_auth_context)]
Database = Annotated[Session, Depends(get_db_session)]
Page = Annotated[int, Query(ge=1, le=10000)]


@router.get("/participants")
def participants(
    context: Actor, session: Database, page: Page = 1, cycle_id: UUID | None = None
) -> dict[str, Any]:
    return WorkService(session).participants(context.user, page, cycle_id)


@router.get("/definitions")
def definitions(
    context: Actor,
    session: Database,
    page: Page = 1,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Any:
    from app.core.errors import ApiError
    from app.modules.kpis.service import DefinitionService
    from app.modules.users.models import UserRole

    if context.user.role != UserRole.MANAGER:
        raise ApiError(403, "forbidden", "Only managers prepare performance plans")
    with session.begin():
        return DefinitionService(session).list(
            context.user,
            page=page,
            page_size=20,
            sort="code",
            q=q,
            is_active=True,
            direction=None,
            options=True,
        )


@router.post("/participants/{identifier}/plan", dependencies=[Depends(require_same_origin)])
def save_plan(
    identifier: UUID, data: PlanDraft, context: Actor, session: Database, request: Request
) -> dict[str, Any]:
    return WorkService(session).save_plan(
        context, lambda row: require_csrf(request, row), identifier, data, request.state.request_id
    )


@router.get("/plans/{identifier}")
def plan(identifier: UUID, context: Actor, session: Database) -> dict[str, Any]:
    return WorkService(session).detail(context.user, identifier)


@router.post("/plans/{identifier}/actions", dependencies=[Depends(require_same_origin)])
def plan_action(
    identifier: UUID, data: PlanAction, context: Actor, session: Database, request: Request
) -> dict[str, Any]:
    return WorkService(session).plan_action(
        context, lambda row: require_csrf(request, row), identifier, data, request.state.request_id
    )


@router.get("/plans/{identifier}/history")
def history(
    identifier: UUID, context: Actor, session: Database, page: Page = 1, work_id: UUID | None = None
) -> dict[str, Any]:
    return WorkService(session).history(context.user, identifier, work_id, page)


@router.get("/plans/{identifier}/revisions")
def revisions(
    identifier: UUID, context: Actor, session: Database, page: Page = 1
) -> dict[str, Any]:
    return WorkService(session).revisions(context.user, identifier, page)


@router.get("/items")
def items(
    context: Actor,
    session: Database,
    page: Page = 1,
    plan_id: UUID | None = None,
    status: Annotated[str | None, Query(max_length=24)] = None,
    blocked: bool | None = None,
) -> dict[str, Any]:
    return WorkService(session).work_list(context.user, page, plan_id, status, blocked)


@router.get("/items/{identifier}")
def item(identifier: UUID, context: Actor, session: Database, page: Page = 1) -> dict[str, Any]:
    return WorkService(session).work_detail(context.user, identifier, page)


@router.post("/plans/{identifier}/items", dependencies=[Depends(require_same_origin)])
def create_work(
    identifier: UUID, data: WorkCreate, context: Actor, session: Database, request: Request
) -> dict[str, Any]:
    return WorkService(session).create_work(
        context, lambda row: require_csrf(request, row), identifier, data, request.state.request_id
    )


@router.post("/items/{identifier}/actions", dependencies=[Depends(require_same_origin)])
def action(
    identifier: UUID, data: WorkAction, context: Actor, session: Database, request: Request
) -> dict[str, Any]:
    return WorkService(session).action(
        context, lambda row: require_csrf(request, row), identifier, data, request.state.request_id
    )


@router.post("/items/{identifier}/draft", dependencies=[Depends(require_same_origin)])
def edit_proposal(
    identifier: UUID, data: WorkCreate, context: Actor, session: Database, request: Request
) -> dict[str, Any]:
    return WorkService(session).edit_proposal(
        context, lambda row: require_csrf(request, row), identifier, data, request.state.request_id
    )
