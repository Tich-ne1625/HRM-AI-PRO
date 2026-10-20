from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.modules.settings.models import SystemConfig


class SettingsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, *, lock: bool = False) -> SystemConfig:
        row = self.session.get(SystemConfig, 1, with_for_update=lock, populate_existing=True)
        if row is None:
            raise ApiError(503, "configuration_unavailable", "Scoring defaults are unavailable")
        return row
