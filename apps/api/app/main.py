from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.core.database import get_engine, get_session_factory
from app.core.errors import register_error_handling
from app.modules.auth.router import router as auth_router
from app.modules.employees.router import router as employees_router
from app.modules.feedback.router import router as feedback_router
from app.modules.health.router import router as health_router
from app.modules.health.service import ReadinessService
from app.modules.kpis.allocation_router import router as allocation_router
from app.modules.kpis.router import router as kpis_router
from app.modules.organization.router import router as organization_router
from app.modules.review_cycles.router import router as cycles_router
from app.modules.settings.router import router as settings_router
from app.modules.users.router import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    app.state.engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    application_settings = settings or get_settings()
    app = FastAPI(title=application_settings.app_name, lifespan=lifespan)
    app.state.settings = application_settings
    app.state.engine = get_engine(application_settings)
    app.state.session_factory = get_session_factory(app.state.engine)
    app.state.readiness_service = ReadinessService(
        app.state.engine,
        application_settings.alembic_config_path,
    )
    register_error_handling(app)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(organization_router)
    app.include_router(employees_router)
    app.include_router(settings_router)
    app.include_router(kpis_router)
    app.include_router(cycles_router)
    app.include_router(allocation_router)
    app.include_router(feedback_router)
    return app


app = create_app()

