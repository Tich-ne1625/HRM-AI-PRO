"""Exact rational intermediates; ROUND_HALF_UP only at the storage/display boundary."""

from fractions import Fraction
from typing import Any

from app.core.decimal_types import decimal_string

ENGINE_VERSION = "1"
MAX_SCORE_CENTS = 10**20 - 1


def money(value: Fraction) -> str:
    if value < 0:
        raise ValueError("Negative score")
    cents = (value.numerator * 200 + value.denominator) // (2 * value.denominator)
    if cents > MAX_SCORE_CENTS:
        raise ValueError("Score out of range")
    return f"{cents // 100}.{cents % 100:02d}"


def quantity(value: object, *, scale: int = 4, maximum: str = "9999999999.9999") -> Fraction:
    parsed = decimal_string(value, scale)
    from decimal import Decimal

    if parsed > Decimal(maximum):
        raise ValueError("Out of range")
    return Fraction(parsed)


def compute(
    items: list[dict[str, Any]], ratings: list[int], policy: dict[str, Any]
) -> dict[str, Any]:
    if not 1 <= len(items) <= 100 or len({row["id"] for row in items}) != len(items):
        raise ValueError("A complete unique allocation is required")
    if not 1 <= len(ratings) <= 100 or any(type(r) is not int or not 1 <= r <= 5 for r in ratings):
        raise ValueError("Valid submitted feedback is required")
    kw = quantity(policy["kpi_weight"], scale=2, maximum="100")
    fw = quantity(policy["feedback_weight"], scale=2, maximum="100")
    if kw + fw != 100:
        raise ValueError("Invalid policy weights")
    cap = (
        None
        if policy["kpi_cap"] is None
        else quantity(policy["kpi_cap"], scale=2, maximum="99999.99")
    )
    if cap is not None and cap <= 0:
        raise ValueError("Cap must be positive")
    total, weights = Fraction(0), Fraction(0)
    lines = []
    for item in items:
        target, actual = quantity(item["target"]), quantity(item["actual"])
        weight = quantity(item["weight"], scale=2, maximum="100")
        if target <= 0 or weight <= 0:
            raise ValueError("Positive target/weight required")
        direction = item["direction"]
        if direction == "LOWER_IS_BETTER":
            if cap is None:
                raise ValueError("Lower-is-better requires a finite cap")
            raw = target / actual * 100 if actual else cap
        elif direction == "HIGHER_IS_BETTER":
            raw = actual / target * 100
        else:
            raise ValueError("Invalid direction")
        normalized = min(raw, cap) if cap is not None else raw
        weighted = normalized * weight / 100
        total += weighted
        weights += weight
        lines.append(
            {
                **item,
                "raw_score": money(raw),
                "normalized_score": money(normalized),
                "weighted_score": money(weighted),
            }
        )
    if weights != 100:
        raise ValueError("Allocation must total exactly 100.00")
    feedback = Fraction(sum(ratings), len(ratings)) * 20
    return {
        "kpi_score": money(total),
        "feedback_score": money(feedback),
        "final_score": money(total * kw / 100 + feedback * fw / 100),
        "items": lines,
    }
