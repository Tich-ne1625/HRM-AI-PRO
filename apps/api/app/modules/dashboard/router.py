from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.core.policies import AuthContext, get_auth_context
from app.modules.dashboard.schemas import AdminDashboard, Dashboard
from app.modules.dashboard.service import DashboardService

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


@router.get("/dashboard", response_model=Dashboard | AdminDashboard)
def dashboard(
    context: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[Session, Depends(get_db_session)],
    response: Response,
    cycle_id: UUID | None = None,
) -> Dashboard | AdminDashboard:
    response.headers["Cache-Control"] = "no-store"
    return DashboardService(session).read(context.user, cycle_id)
