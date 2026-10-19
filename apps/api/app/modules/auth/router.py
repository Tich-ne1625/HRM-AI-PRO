from secrets import compare_digest
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_db_session
from app.core.errors import ApiError
from app.core.policies import AuthContext, get_auth_context
from app.core.security import (
    ACCESS_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    REFRESH_COOKIE_NAME,
    hash_opaque_token,
)
from app.modules.auth.cookies import clear_auth_cookies, set_auth_cookies
from app.modules.auth.models import AuthSession
from app.modules.auth.schemas import ChangePasswordRequest, CurrentUser, LoginCommand, LoginRequest
from app.modules.auth.service import AuthService
from app.modules.users.presenters import current_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/me", response_model=CurrentUser)
def me(
    response: Response,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    session: Annotated[Session, Depends(get_db_session)],
) -> CurrentUser:
    response.headers["Cache-Control"] = "no-store"
    with session.begin():
        return current_user(session, context.user)


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


def require_csrf(request: Request, active_session: AuthSession) -> None:
    header = request.headers.get("X-CSRF-Token")
    cookie = request.cookies.get(CSRF_COOKIE_NAME)
    if (
        not header
        or not cookie
        or not compare_digest(header.encode("utf-8"), cookie.encode("utf-8"))
        or not compare_digest(hash_opaque_token(cookie), active_session.csrf_hash)
    ):
        raise ApiError(403, "csrf_failed", "CSRF validation failed")


@router.post("/refresh", status_code=204, dependencies=[Depends(require_same_origin)])
def refresh(
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    result = service.rotate_refresh(
        request.cookies.get(REFRESH_COOKIE_NAME),
        csrf_token=request.cookies.get(CSRF_COOKIE_NAME),
        require_csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    set_auth_cookies(response, result, cast(Settings, request.app.state.settings))
    return response


@router.post("/logout", status_code=204, dependencies=[Depends(require_same_origin)])
def logout(
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    service.revoke_family(
        request.cookies.get(ACCESS_COOKIE_NAME),
        require_csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    clear_auth_cookies(response, cast(Settings, request.app.state.settings))
    return response


@router.post("/change-password", status_code=204, dependencies=[Depends(require_same_origin)])
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    service.change_password(
        request.cookies.get(ACCESS_COOKIE_NAME),
        body,
        require_csrf=lambda row: require_csrf(request, row),
        request_id=request.state.request_id,
    )
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
