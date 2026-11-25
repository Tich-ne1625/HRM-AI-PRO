from copy import deepcopy

import pytest

from app.modules.progress.aggregation import aggregate, canonical_source


def source(value, **extra):
    return {
        "payload": {"value": value},
        "measurement_id": str(value),
        "occurred_at": "2026-11-25T10:00:00+00:00",
        **extra,
    }


def test_delta_and_snapshot_have_different_meanings():
    rows = [
        source("20"),
        source("35", occurred_at="2026-11-25T11:00:00+00:00"),
        source("50", occurred_at="2026-11-25T12:00:00+00:00"),
    ]
    assert aggregate({"method": "SUM"}, rows)["actual"] == "105.0000"
    assert aggregate({"method": "LAST"}, rows)["actual"] == "50.0000"


@pytest.mark.parametrize(
    "pairs, expected",
    [
        ([("9", "10"), ("1", "2")], "83.33"),
        ([("30", "40"), ("90", "100")], "85.71"),
        ([("0", "0")], None),
        ([], None),
    ],
)
def test_ratios_use_totals_and_distinguish_missing(pairs, expected):
    rows = [{"payload": {"numerator": n, "denominator": d}} for n, d in pairs]
    assert aggregate({"method": "RATIO"}, rows)["actual"] == expected


def test_zero_is_not_missing_and_results_are_exact():
    assert aggregate({"method": "SUM"}, [source("0")])["actual"] == "0.0000"
    assert aggregate({"method": "SUM"}, [])["actual"] is None
    result = aggregate({"method": "RATIO"}, [{"payload": {"numerator": "1", "denominator": "3"}}])
    assert (result["exact_numerator"], result["exact_denominator"]) == ("100", "3")


def test_milestones_and_input_immutability():
    spec = {"method": "MILESTONE", "milestones": [{"weight": "30"}, {"weight": "70"}]}
    rows = [{"milestone": 0}]
    before = deepcopy(rows)
    assert aggregate(spec, rows)["actual"] == "30.00"
    assert rows == before
    with pytest.raises(ValueError):
        aggregate(spec, rows + rows)


def test_canonical_source_is_bounded_and_does_not_drop_zeroes():
    assert canonical_source("  CASE-001 ") == canonical_source("case-001")
    assert canonical_source("case-001") != canonical_source("case-1")
    with pytest.raises(ValueError):
        canonical_source("bad\x00key")


def test_overflow_is_not_silently_truncated():
    with pytest.raises(ValueError):
        aggregate({"method": "SUM"}, [source("1" + "0" * 24)])
