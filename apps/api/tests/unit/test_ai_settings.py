import pytest
from pydantic import ValidationError

from app.core.config import Settings


def settings(**values):
    return Settings(
        _env_file=None, database_url="postgresql+psycopg://test:test@localhost/db_test", **values
    )


def test_ai_is_optional_and_secret_safe():
    assert not settings().gemini_enabled
    configured = settings(
        gemini_enabled=True, gemini_api_key="key-sentinel", gemini_model="configured-model"
    )
    assert configured.gemini_api_key.get_secret_value() == "key-sentinel"
    assert "key-sentinel" not in repr(configured)


@pytest.mark.parametrize(
    "values",
    [
        {"gemini_enabled": True},
        {"gemini_enabled": True, "gemini_api_key": "sentinel"},
        {"gemini_timeout_seconds": 31},
        {"gemini_timeout_seconds": 4},
        {"gemini_max_output_tokens": 4097},
        {"gemini_model": "bad\nmodel"},
    ],
)
def test_invalid_ai_configuration_is_rejected(values):
    with pytest.raises(ValidationError) as error:
        settings(**values)
    assert "sentinel" not in str(error.value)
