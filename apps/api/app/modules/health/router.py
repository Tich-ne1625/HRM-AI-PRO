from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request

from app.core.errors import ApiError
from app.modules.health.schemas import (
    LivenessResponse,
    ReadinessChecks,
    ReadinessResponse,
)
from app.modules.health.service import ReadinessService

router = APIRouter(prefix="/health", tags=["health"])


def get_readiness_service(request: Request) -> ReadinessService:
    return cast(ReadinessService, request.app.state.readiness_service)


@router.get("/live", response_model=LivenessResponse)
def liveness() -> LivenessResponse:
    return LivenessResponse()


@router.get("/ready", response_model=ReadinessResponse)
def readiness(
    service: Annotated[ReadinessService, Depends(get_readiness_service)],
) -> ReadinessResponse:
    result = service.check()
    if not result.is_ready:
        raise ApiError(
            503,
            "service_not_ready",
            "Service dependencies are not ready",
            details=[
                {"check": "database", "status": result.database},
                {"check": "migrations", "status": result.migrations},
            ],
        )
    return ReadinessResponse(checks=ReadinessChecks())

