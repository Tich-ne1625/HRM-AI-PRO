"""Historical identities come from activation, never from the current manager tree."""

from collections.abc import Mapping
from typing import Any

from app.modules.feedback.models import Relationship


def historical_candidates(
    snapshot: Mapping[str, Any], relationship: Relationship
) -> dict[str, str]:
    if relationship == Relationship.SELF:
        return {str(snapshot["user_id"]): str(snapshot["employee_id"])}
    if relationship == Relationship.MANAGER:
        return {str(snapshot["manager_user_id"]): str(snapshot["manager_id"])}
    if relationship == Relationship.SUBORDINATE:
        return {
            str(row["user_id"]): str(row["employee_id"])
            for row in snapshot.get("direct_reports", [])
            if row.get("user_id")
            and row["employment_status"] == "ACTIVE"
            and relationship_for(snapshot, str(row["user_id"]), str(row["employee_id"]))
            == Relationship.SUBORDINATE
        }
    return {}


def relationship_for(snapshot: Mapping[str, Any], user_id: str, employee_id: str) -> Relationship:
    # Exclude both user and employee identities from PEER classification, including
    # inactive historical direct reports and employee profiles relinked after activation.
    if user_id == str(snapshot["user_id"]) or employee_id == str(snapshot["employee_id"]):
        return Relationship.SELF
    if user_id == str(snapshot["manager_user_id"]) or employee_id == str(snapshot["manager_id"]):
        return Relationship.MANAGER
    if any(
        user_id == str(row.get("user_id")) or employee_id == str(row["employee_id"])
        for row in snapshot.get("direct_reports", [])
    ):
        return Relationship.SUBORDINATE
    return Relationship.PEER
