from __future__ import annotations

from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.core.errors import register_error_handling


def create_app(settings: Settings | None = None) -> FastAPI:
    application_settings = settings or get_settings()
    app = FastAPI(title=application_settings.app_name)
    app.state.settings = application_settings
    register_error_handling(app)
    return app


app = create_app()

