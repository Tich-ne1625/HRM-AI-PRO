"""Import every mapped model to populate the shared Alembic metadata."""

from app.modules.ai.models import AIAnalysis, AnalysisStatus
from app.modules.audit.models import AuditLog
from app.modules.auth.limiter import LoginLimit
from app.modules.auth.models import AuthSession
from app.modules.collaboration.models import ChatMessage, InternalPost, PostComment
from app.modules.employees.models import Employee, EmploymentStatus
from app.modules.feedback.models import AssignmentStatus, Feedback, FeedbackAssignment, Relationship
from app.modules.kpis.models import EmployeeKPI, KPIDefinition, KPIDirection
from app.modules.notifications.models import Notification
from app.modules.organization.models import Department, Position
from app.modules.performance.models import PerformanceReview, PerformanceReviewRevision
from app.modules.review_cycles.models import CycleParticipant, CycleStatus, ReviewCycle
from app.modules.settings.models import SystemConfig
from app.modules.users.models import User, UserRole
from app.modules.work_management.models import (
    EvidenceSubmission,
    PlanRevision,
    WorkEvent,
    WorkGoal,
    WorkItem,
    WorkPlan,
)

__all__ = [
    "AIAnalysis",
    "AnalysisStatus",
    "AssignmentStatus",
    "AuditLog",
    "AuthSession",
    "ChatMessage",
    "CycleParticipant",
    "CycleStatus",
    "Department",
    "Employee",
    "EmployeeKPI",
    "EmploymentStatus",
    "EvidenceSubmission",
    "Feedback",
    "FeedbackAssignment",
    "InternalPost",
    "KPIDefinition",
    "KPIDirection",
    "LoginLimit",
    "Notification",
    "PerformanceReview",
    "PerformanceReviewRevision",
    "PlanRevision",
    "Position",
    "PostComment",
    "Relationship",
    "ReviewCycle",
    "SystemConfig",
    "User",
    "UserRole",
    "WorkEvent",
    "WorkGoal",
    "WorkItem",
    "WorkPlan",
]
