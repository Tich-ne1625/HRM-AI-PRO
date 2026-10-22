from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.performance.schemas import CalculateInput, FinalizeInput


@pytest.mark.parametrize("version", [True, 0, -1, 1.0, "1", None])
def test_calculation_requires_strict_positive_evidence(version):
    with pytest.raises(ValidationError):
        CalculateInput.model_validate(
            {"cycle_id": str(uuid4()), "expected_evidence_version": version}
        )


@pytest.mark.parametrize("count", [True, -1, 1.0, "0", None, 101])
def test_finalization_acknowledgement_is_explicit_strict_count(count):
    with pytest.raises(ValidationError):
        FinalizeInput.model_validate(
            {
                "expected_evidence_version": 2,
                "expected_calculation_version": 1,
                "acknowledge_open_optional_count": count,
            }
        )


def test_forged_scores_and_missing_acknowledgement_rejected():
    with pytest.raises(ValidationError):
        CalculateInput.model_validate(
            {"cycle_id": str(uuid4()), "expected_evidence_version": 2, "final_score": "100"}
        )
    with pytest.raises(ValidationError):
        FinalizeInput.model_validate(
            {"expected_evidence_version": 2, "expected_calculation_version": 1}
        )
