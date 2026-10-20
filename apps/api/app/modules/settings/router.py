from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.core.policies import AuthContext, require_roles
from app.modules.auth.router import require_csrf, require_same_origin
from app.modules.settings.schemas import ScoringUpdate, ScoringView
from app.modules.settings.service import SettingsService
from app.modules.users.models import UserRole

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])
Admin = Annotated[AuthContext, Depends(require_roles(UserRole.ADMIN))]
Database = Annotated[Session, Depends(get_db_session)]


@router.get("/scoring", response_model=ScoringView)
def scoring_defaults(context: Admin, session: Database, response: Response) -> ScoringView:
    response.headers["Cache-Control"] = "no-store"
    return SettingsService(session).read()


@router.patch("/scoring", response_model=ScoringView, dependencies=[Depends(require_same_origin)])
def update_defaults(
    body: ScoringUpdate, context: Admin, session: Database, request: Request, response: Response
) -> ScoringView:
    response.headers["Cache-Control"] = "no-store"
    return SettingsService(session).update(
        body,
        context,
        csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )
