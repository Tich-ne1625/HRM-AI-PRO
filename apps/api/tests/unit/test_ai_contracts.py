import json
from copy import deepcopy
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.ai.input_builder import build_payload, redact
from app.modules.ai.schemas import AnalysisOutput, GenerateInput, parse_output


def output():
    return {
        "summary": "Kết quả dựa trên bằng chứng.",
        "strengths": [],
        "improvement_areas": [],
        "feedback_themes": [],
        "recommended_actions": [],
        "caveats": ["Chỉ mang tính tư vấn."],
    }


def snapshot():
    return {
        "subject": {"display_name": "Alice Secret"},
        "items": [
            {
                "id": str(uuid4()),
                "code": "PRIVATE",
                "name": "Alice Secret",
                "unit": "private",
                "target": "100.0000",
                "actual": "90.0000",
                "weight": "100.00",
                "direction": "HIGHER_IS_BETTER",
            }
        ],
        "assignments": [
            {
                "id": str(uuid4()),
                "reviewer_id": str(uuid4()),
                "status": "SUBMITTED",
                "relationship": "PEER",
                "rating": 4,
            }
        ],
    }


def test_strict_output_and_input():
    assert parse_output(json.dumps(output())).summary.startswith("Kết quả")
    for field, value in (("summary", True), ("strengths", "x"), ("caveats", []), ("score", 100)):
        with pytest.raises(ValidationError):
            AnalysisOutput.model_validate({**output(), field: value})
    body = {
        "client_request_id": str(uuid4()),
        "expected_calculation_version": 1,
        "expected_evidence_version": 1,
    }
    assert GenerateInput.model_validate(body).audience == "PUBLIC"
    for values in (
        {"regenerate": True},
        {"regenerate": "false"},
        {"expected_calculation_version": True},
        {"score": "100"},
    ):
        with pytest.raises(ValidationError):
            GenerateInput.model_validate({**body, **values})


@pytest.mark.parametrize(
    "raw",
    ['{"summary":"x","summary":"y"}', '{"x":NaN}', "[]", '"text"', "{bad", "x" * 32769],
    ids=["duplicate", "nan", "array", "scalar", "invalid", "oversize"],
)
def test_rejects_ambiguous_or_oversized_provider_json(raw):
    with pytest.raises(ValueError):
        parse_output(raw)


def test_public_payload_never_contains_comments_or_identity():
    source = snapshot()
    body, sampled = build_payload(
        source,
        {"kpi_weight": "70.00"},
        {"kpi_score": "90.00", "feedback_score": "80.00", "final_score": "87.00"},
        "PUBLIC",
        ["Private email alice@example.com"],
        ["Alice Secret"],
    )
    assert not sampled
    encoded = json.dumps(body)
    for value in (
        "Alice",
        "PRIVATE",
        "private",
        "reviewer_id",
        "comments",
        source["assignments"][0]["id"],
    ):
        assert value not in encoded
    assert body["feedback"]["groups"][2]["count"] is None
    assert body["kpis"][0]["reference"] == "KPI-01"


def test_private_redaction_sampling_and_determinism():
    comments = [
        f"Alice Secret alice@example.com https://example.com +84 912 345 678 comment {n}"
        for n in range(25)
    ]
    source = snapshot()
    args = (source, {}, {"final_score": "87.00"}, "HR_PRIVATE")
    first, sampled = build_payload(*args, comments, ["Alice Secret"])
    second, _ = build_payload(*args, list(reversed(comments)), ["Alice Secret"])
    assert first == second and sampled and len(first["comments"]) == 20
    assert all(len(c) <= 500 for c in first["comments"])
    assert "Alice Secret" not in json.dumps(first) and "@example" not in json.dumps(first)
    assert "https://" not in json.dumps(first) and "912 345" not in json.dumps(first)
    assert redact("A\u200blice Secret", ["Alice Secret"]) == "[REDACTED]"
    changed = deepcopy(source)
    changed["items"] = changed["items"] * 100
    for item in changed["items"]:
        item["actual"] = "9" * 1000
    with pytest.raises(ValueError, match="payload"):
        build_payload(changed, {}, {}, "PUBLIC", [], [])
