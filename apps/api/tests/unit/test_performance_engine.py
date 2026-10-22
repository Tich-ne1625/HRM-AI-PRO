from decimal import Decimal, localcontext
from fractions import Fraction
from random import Random

import pytest

from app.modules.performance.engine import compute, money


def item(actual="90", target="100", weight="100", direction="HIGHER_IS_BETTER"):
    return dict(id="kpi", actual=actual, target=target, weight=weight, direction=direction)


def policy(cap="100.00", kpi="70.00", feedback="30.00"):
    return dict(kpi_cap=cap, kpi_weight=kpi, feedback_weight=feedback)


def test_golden_unrounded_components():
    rows = [item(weight="60"), {**item(actual="100", weight="40"), "id": "second"}]
    result = compute(rows, [4, 4, 4, 4], policy())
    assert result["kpi_score"] == "94.00"
    assert result["feedback_score"] == "80.00"
    assert result["final_score"] == "89.80"


def test_exact_half_up_without_decimal_context_dependence():
    assert money(Fraction(225, 200)) == "1.13"
    for precision in (6, 28, 60):
        with localcontext() as context:
            context.prec = precision
            assert (
                compute([item(actual="1", target="3")], [1, 2, 2], policy())["final_score"]
                == "33.33"
            )


def test_cap_zero_actual_lower_and_uncapped_maximum():
    assert (
        compute([item(actual="0", direction="LOWER_IS_BETTER")], [5], policy(cap="150"))[
            "kpi_score"
        ]
        == "150.00"
    )
    assert (
        compute([item(actual="9999999999.9999", target="0.0001")], [5], policy(cap=None))[
            "kpi_score"
        ]
        == "9999999999999900.00"
    )
    assert (
        compute([item(actual="2", target="1")], [5], policy(cap="150"))["final_score"] == "135.00"
    )


@pytest.mark.parametrize(
    "row",
    [
        item(actual=None),
        item(actual="NaN"),
        item(actual="Infinity"),
        item(target="0"),
        item(actual="-1"),
        item(weight="99.99"),
        item(direction="INVALID"),
        item(actual=True),
        item(actual="1.00001"),
    ],
)
def test_invalid_evidence_rejected(row):
    with pytest.raises(ValueError):
        compute([row], [4], policy())


@pytest.mark.parametrize("ratings", [[], [0], [6], [True], [1.0], ["4"]])
def test_invalid_ratings_rejected_even_when_component_weight_zero(ratings):
    with pytest.raises(ValueError):
        compute([item()], ratings, policy(kpi="100", feedback="0"))


def test_lower_without_cap_and_duplicate_kpis_rejected():
    with pytest.raises(ValueError):
        compute([item(direction="LOWER_IS_BETTER")], [4], policy(cap=None))
    with pytest.raises(ValueError):
        compute([item(weight="50"), item(weight="50")], [4], policy())


def test_randomized_oracle_using_high_precision_decimal():
    rng = Random(6)
    for _ in range(100):
        actual, target = rng.randint(0, 10000), rng.randint(1, 10000)
        ratings = [rng.randint(1, 5) for _ in range(rng.randint(1, 100))]
        with localcontext() as context:
            context.prec = 100
            expected = min(Decimal(actual) / Decimal(target) * 100, Decimal(100)) * Decimal(
                "0.7"
            ) + Decimal(sum(ratings)) / len(ratings) * 20 * Decimal("0.3")
            expected = format(expected.quantize(Decimal("0.01"), rounding="ROUND_HALF_UP"), ".2f")
        assert (
            compute([item(actual=str(actual), target=str(target))], ratings, policy())[
                "final_score"
            ]
            == expected
        )
