from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.core.database import get_engine
from app.core.errors import register_error_handling
from app.modules.health.router import router as health_router
from app.modules.health.service import ReadinessService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    app.state.engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    application_settings = settings or get_settings()
    app = FastAPI(title=application_settings.app_name, lifespan=lifespan)
    app.state.settings = application_settings
    app.state.engine = get_engine(application_settings)
    app.state.readiness_service = ReadinessService(
        app.state.engine,
        Path(__file__).resolve().parents[1] / "alembic.ini",
    )
    register_error_handling(app)
    app.include_router(health_router)
    return app


app = create_app()

