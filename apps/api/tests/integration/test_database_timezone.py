from datetime import timedelta

from sqlalchemy import Engine, text

from app.core.config import Settings
from app.core.database import get_engine


def test_application_connections_override_timezone_and_preserve_options(
    empty_test_engine: Engine,
) -> None:
    url = empty_test_engine.url.update_query_dict(
        {"options": "-c timezone=Asia/Bangkok -c statement_timeout=4321"}
    )
    engine = get_engine(Settings(database_url=url.render_as_string(hide_password=False)))
    try:
        for _ in range(2):
            with engine.connect() as connection:
                assert connection.scalar(text("SHOW timezone")) == "UTC"
                assert connection.scalar(text("SHOW statement_timeout")) == "4321ms"
                assert connection.scalar(text("SELECT now()")).utcoffset() == timedelta(0)
    finally:
        engine.dispose()
