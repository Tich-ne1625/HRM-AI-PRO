from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError


def test_default_policy_and_exact_decimal_roundtrip():
    from app.modules.settings.schemas import ScoringPolicy

    policy = ScoringPolicy()
    assert policy.kpi_weight == Decimal("70.00")
    assert policy.model_dump(mode="json") == {
        "schema_version": 1,
        "kpi_weight": "70.00",
        "feedback_weight": "30.00",
        "kpi_cap": "100.00",
    }


@pytest.mark.parametrize("value", [True, 70, 70.0, "NaN", "Infinity", "-1", "70.001", "1e2"])
def test_policy_rejects_non_decimal_strings_and_out_of_scale(value):
    from app.modules.settings.schemas import ScoringPolicy

    with pytest.raises(ValidationError):
        ScoringPolicy(kpi_weight=value)


@pytest.mark.parametrize(
    "changes",
    [
        {"kpi_weight": "80.00"},
        {"kpi_cap": "0.00"},
        {"kpi_cap": "100000.00"},
        {"schema_version": True},
        {"schema_version": 2},
        {"unexpected": True},
    ],
)
def test_policy_invalid_configuration(changes):
    from app.modules.settings.schemas import ScoringPolicy

    with pytest.raises(ValidationError):
        ScoringPolicy(**changes)


def test_policy_allows_uncapped_or_above_hundred():
    from app.modules.settings.schemas import ScoringPolicy

    assert ScoringPolicy(kpi_cap=None).kpi_cap is None
    assert ScoringPolicy(kpi_cap="150.00").kpi_cap == Decimal("150")


def test_full_allocation_requires_unique_definitions_and_exact_total():
    from app.modules.kpis.schemas import AllocationReplace

    identifier = str(uuid4())
    first = {"definition_id": identifier, "target": "10.0000", "weight": "60.00"}
    second = {"definition_id": str(uuid4()), "target": "1.0000", "weight": "40.00"}
    assert len(AllocationReplace(expected_evidence_version=2, items=[first, second]).items) == 2
    for items in ([], [first], [first, {**second, "definition_id": identifier}], [second] * 101):
        with pytest.raises(ValidationError):
            AllocationReplace(expected_evidence_version=2, items=items)


@pytest.mark.parametrize(
    "value", [True, 1, 0.2, "NaN", "Infinity", "-1", "1.00001", "10000000000", "1e2", " 1.0 "]
)
def test_actual_rejects_invalid_numeric_values(value):
    from app.modules.kpis.schemas import ActualUpdate

    with pytest.raises(ValidationError):
        ActualUpdate(expected_evidence_version=2, actual=value)


def test_actual_zero_and_null_are_distinct_and_other_fields_forbidden():
    from app.modules.kpis.schemas import ActualUpdate

    assert ActualUpdate(expected_evidence_version=2, actual="0.0000").actual == Decimal(0)
    assert ActualUpdate(expected_evidence_version=2, actual=None).actual is None
    for changes in ({"expected_evidence_version": True}, {"target": "1.0"}, {}):
        body = {"expected_evidence_version": 2, "actual": None, **changes}
        if not changes:
            body.pop("actual")
        with pytest.raises(ValidationError):
            ActualUpdate(**body)


def test_cycle_dates_and_versioned_patch():
    from app.modules.review_cycles.schemas import CycleCreate, CycleUpdate, Enrollment

    data = {"name": " Q4 ", "start_date": "2026-10-01", "end_date": "2026-12-31"}
    assert CycleCreate(**data).name == "Q4"
    for changes in ({"end_date": "2026-09-30"}, {"name": "bad\x00name"}, {"status": "ACTIVE"}):
        with pytest.raises(ValidationError):
            CycleCreate(**{**data, **changes})
    for data in (
        {"expected_version": 1},
        {"expected_version": 1, "name": None},
        {"expected_version": True, "name": "New"},
    ):
        with pytest.raises(ValidationError):
            CycleUpdate(**data)
    identifier = str(uuid4())
    with pytest.raises(ValidationError):
        Enrollment(expected_version=1, employee_ids=[identifier, identifier])


def test_definition_normalization_and_text_controls():
    from app.modules.kpis.schemas import DefinitionCreate, DefinitionUpdate

    data = {"code": " sales ", "name": " Sales ", "unit": " VND ", "direction": "HIGHER_IS_BETTER"}
    result = DefinitionCreate(**data)
    assert (result.code, result.name, result.unit) == ("SALES", "Sales", "VND")
    assert DefinitionCreate(**data, description="Line 1\nLine 2\tend").description
    for changes in ({"unit": " "}, {"description": "bad\x00text"}, {"name": "bad\x7fname"}):
        with pytest.raises(ValidationError):
            DefinitionCreate(**{**data, **changes})
    with pytest.raises(ValidationError):
        DefinitionUpdate(expected_version=1)
