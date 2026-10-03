from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://insighthr_test:test-password@localhost:5432/insighthr_test",
)
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("AUTH_ACCESS_SECRET", "test-only-signing-key-32-characters")
os.environ.setdefault("WEB_ORIGIN", "http://testserver")

