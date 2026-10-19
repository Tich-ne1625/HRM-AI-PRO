from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_db_session
from app.core.errors import ApiError
from app.modules.auth.cookies import set_auth_cookies
from app.modules.auth.schemas import CurrentUser, LoginCommand, LoginRequest
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def require_same_origin(request: Request) -> None:
    settings = cast(Settings, request.app.state.settings)
    origins = [value for name, value in request.scope["headers"] if name.lower() == b"origin"]
    if origins != [settings.web_origin.encode("utf-8")]:
        raise ApiError(403, "origin_not_allowed", "Request origin is not allowed")


def get_auth_service(
    request: Request, session: Annotated[Session, Depends(get_db_session)]
) -> AuthService:
    return AuthService(session, cast(Settings, request.app.state.settings))


@router.post("/login", response_model=CurrentUser, dependencies=[Depends(require_same_origin)])
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> CurrentUser:
    result = service.login(
        LoginCommand(email=body.email, password=body.password, request_id=request.state.request_id)
    )
    set_auth_cookies(response, result, cast(Settings, request.app.state.settings))
    response.headers["Cache-Control"] = "no-store"
    return result.user
