from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.review_cycles.schemas import CycleCreate
from app.modules.work_management.schemas import GoalInput, PlanDraft, WorkAction


def goal(**changes):
    return {
        "definition_id": str(uuid4()),
        "baseline": "0",
        "target": "100",
        "weight": "100",
        "method": "SUM",
        "source": "Unique verified record IDs",
        "acceptance": "QA approved",
        **changes,
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"target": "0"},
        {"baseline": "NaN"},
        {"target": "Infinity"},
        {"weight": "100.001"},
        {"method": "RATIO", "numerator": "Resolved"},
        {"method": "MILESTONE", "milestones": [{"title": "Draft", "weight": "50"}]},
        {"milestones": [{"title": "Draft", "weight": "100"}]},
    ],
)
def test_goal_rules_reject_unverifiable_or_nonfinite_targets(changes):
    with pytest.raises(ValidationError):
        GoalInput.model_validate(goal(**changes))


def test_plan_weights_are_exact_and_kpis_are_distinct():
    one, two = goal(weight="33.33"), goal(weight="66.67")
    PlanDraft.model_validate(
        {
            "client_request_id": str(uuid4()),
            "expected_version": 1,
            "objective": "Office performance",
            "goals": [one, two],
        }
    )
    for goals in ([one], [one, {**two, "definition_id": one["definition_id"]}]):
        with pytest.raises(ValidationError):
            PlanDraft.model_validate(
                {
                    "client_request_id": str(uuid4()),
                    "expected_version": 1,
                    "objective": "Office performance",
                    "goals": goals,
                }
            )


@pytest.mark.parametrize(
    "url", ["javascript:alert(1)", "file:///private", "ftp://example.com/file"]
)
def test_evidence_accepts_only_http_urls(url):
    with pytest.raises(ValidationError):
        WorkAction.model_validate(
            {
                "client_request_id": str(uuid4()),
                "expected_version": 1,
                "action": "submit",
                "body": "Evidence",
                "url": url,
            }
        )


def test_continuous_schedule_is_explicit_and_legacy_cannot_smuggle_it():
    with pytest.raises(ValidationError):
        CycleCreate.model_validate(
            {
                "name": "Cycle",
                "start_date": "2026-12-01",
                "end_date": "2026-12-31",
                "workflow_mode": "CONTINUOUS",
            }
        )
