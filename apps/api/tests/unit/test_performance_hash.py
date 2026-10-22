from copy import deepcopy

from app.modules.performance.evidence import Evidence
from app.modules.performance.schemas import HRReadiness


def evidence():
    return Evidence(
        snapshot={
            "evidence_version": 4,
            "items": [{"id": "b", "actual": "1.0000"}, {"id": "a", "actual": "2.0000"}],
            "assignments": [{"id": "y", "rating": 4}, {"id": "x", "rating": 5}],
        },
        policy={"kpi_weight": "70.00"},
        readiness=HRReadiness(
            ready=True,
            issue_count=0,
            issues=[],
            pending_assignment_ids=[],
            blocked_assignment_ids=[],
        ),
    )


def test_hash_ignores_query_order_and_readiness_but_covers_exact_inputs():
    original = evidence()
    reordered = deepcopy(original)
    reordered.snapshot["items"].reverse()
    reordered.snapshot["assignments"].reverse()
    reordered.readiness.ready = False
    assert original.digest == reordered.digest
    assert original.digest != original.digest_for("2")
    for field, value in (("evidence_version", 5), ("items", [{"id": "a", "actual": "3.0000"}])):
        changed = deepcopy(original)
        changed.snapshot[field] = value
        assert original.digest != changed.digest
    changed = deepcopy(original)
    changed.policy["kpi_weight"] = "60.00"
    assert original.digest != changed.digest
