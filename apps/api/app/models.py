"""Import every mapped model to populate the shared Alembic metadata."""

from app.modules.audit.models import AuditLog
from app.modules.auth.models import AuthSession
from app.modules.users.models import User, UserRole

__all__ = ["AuditLog", "AuthSession", "User", "UserRole"]
