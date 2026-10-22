"""Import every mapped model to populate the shared Alembic metadata."""

from app.modules.audit.models import AuditLog
from app.modules.auth.models import AuthSession
from app.modules.employees.models import Employee, EmploymentStatus
from app.modules.feedback.models import AssignmentStatus, Feedback, FeedbackAssignment, Relationship
from app.modules.kpis.models import EmployeeKPI, KPIDefinition, KPIDirection
from app.modules.organization.models import Department, Position
from app.modules.performance.models import PerformanceReview, PerformanceReviewRevision
from app.modules.review_cycles.models import CycleParticipant, CycleStatus, ReviewCycle
from app.modules.settings.models import SystemConfig
from app.modules.users.models import User, UserRole

__all__ = [
    "AssignmentStatus",
    "AuditLog",
    "AuthSession",
    "CycleParticipant",
    "CycleStatus",
    "Department",
    "Employee",
    "EmployeeKPI",
    "EmploymentStatus",
    "Feedback",
    "FeedbackAssignment",
    "KPIDefinition",
    "KPIDirection",
    "PerformanceReview",
    "PerformanceReviewRevision",
    "Position",
    "Relationship",
    "ReviewCycle",
    "SystemConfig",
    "User",
    "UserRole",
]
