from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["api"] = "api"


class ReadinessChecks(BaseModel):
    database: Literal["ok"] = "ok"
    migrations: Literal["current"] = "current"


class ReadinessResponse(BaseModel):
    status: Literal["ready"] = "ready"
    checks: ReadinessChecks

