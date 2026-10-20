from uuid import uuid4

import pytest

from app.modules.feedback.eligibility import historical_candidates, relationship_for
from app.modules.feedback.models import Relationship


def snapshot():
    return {
        "employee_id": str(uuid4()),
        "user_id": str(uuid4()),
        "manager_id": str(uuid4()),
        "manager_user_id": str(uuid4()),
        "direct_reports": [
            {"employee_id": str(uuid4()), "user_id": str(uuid4()), "employment_status": "ACTIVE"},
            {"employee_id": str(uuid4()), "user_id": str(uuid4()), "employment_status": "INACTIVE"},
            {"employee_id": str(uuid4()), "user_id": None, "employment_status": "ACTIVE"},
        ],
    }


def test_historical_candidates_exclude_inactive_or_unlinked_subordinates():
    s = snapshot()
    assert historical_candidates(s, Relationship.SELF) == {s["user_id"]: s["employee_id"]}
    assert historical_candidates(s, Relationship.MANAGER) == {s["manager_user_id"]: s["manager_id"]}
    assert historical_candidates(s, Relationship.SUBORDINATE) == {
        s["direct_reports"][0]["user_id"]: s["direct_reports"][0]["employee_id"]
    }


@pytest.mark.parametrize(
    "kind,key", [(Relationship.SELF, "user_id"), (Relationship.MANAGER, "manager_user_id")]
)
def test_classification_keeps_historical_principal(kind, key):
    s = snapshot()
    assert relationship_for(s, s[key], str(uuid4())) == kind


def test_peer_cannot_impersonate_historical_relationship_by_relinking():
    s = snapshot()
    assert relationship_for(s, str(uuid4()), s["employee_id"]) == Relationship.SELF
    report = s["direct_reports"][1]
    assert relationship_for(s, report["user_id"], report["employee_id"]) == Relationship.SUBORDINATE
    assert relationship_for(s, str(uuid4()), str(uuid4())) == Relationship.PEER
