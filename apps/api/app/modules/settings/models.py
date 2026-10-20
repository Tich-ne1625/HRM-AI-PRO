from sqlalchemy import CheckConstraint, Integer, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.organization.models import Timestamps


class SystemConfig(Timestamps, Base):
    __tablename__ = "system_config"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_system_config_singleton"),
        CheckConstraint("version >= 1", name="ck_system_config_version"),
        CheckConstraint("jsonb_typeof(scoring_policy) = 'object'", name="ck_system_config_policy"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=1)
    version: Mapped[int] = mapped_column(default=1, server_default=text("1"))
    scoring_policy: Mapped[dict[str, object]] = mapped_column(JSONB(none_as_null=True))
