"""Deterministic exact arithmetic. Inputs are effective, verified source revisions only."""

import hashlib
import json
import unicodedata
from decimal import ROUND_HALF_UP, Decimal, localcontext
from fractions import Fraction
from typing import Any

ALGORITHM = "measurements-v1"


def canonical_source(value: str) -> str:
    result = unicodedata.normalize("NFKC", value).strip().casefold()
    if (
        not result
        or len(result) > 120
        or any(unicodedata.category(c).startswith("C") for c in result)
    ):
        raise ValueError("Invalid source key")
    return result


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def validate_rule(spec: dict[str, Any]) -> None:
    if spec["method"] in {"RATIO", "MILESTONE"} and (
        str(spec["definition"]["unit"]).strip().casefold() not in {"%", "percent", "phần trăm"}
        or Decimal(str(spec["target"])) > 100
    ):
        raise ValueError("Percentage rules require a percentage unit and target <= 100")


def aggregate(spec: dict[str, Any], sources: list[dict[str, Any]]) -> dict[str, Any]:
    method = spec["method"]
    numerator = Fraction(0)
    denominator = Fraction(1)
    enough = bool(sources)
    if method == "SUM":
        numerator = sum((Fraction(s["payload"]["value"]) for s in sources), Fraction(0))
    elif method == "LAST":
        if sources:
            latest = max(sources, key=lambda s: (s["occurred_at"], s["measurement_id"]))
            numerator = Fraction(latest["payload"]["value"])
    elif method == "RATIO":
        numerator = sum((Fraction(s["payload"]["numerator"]) for s in sources), Fraction(0))
        denominator = sum((Fraction(s["payload"]["denominator"]) for s in sources), Fraction(0))
        enough = denominator > 0
        if enough:
            numerator *= 100
    elif method == "MILESTONE":
        seen: set[int] = set()
        for source in sources:
            index = source["milestone"]
            if (
                index in seen
                or not isinstance(index, int)
                or not 0 <= index < len(spec["milestones"])
            ):
                raise ValueError("Duplicate or unknown milestone")
            seen.add(index)
            numerator += Fraction(spec["milestones"][index]["weight"])
    else:
        raise ValueError("Unsupported measurement algorithm")
    exact = numerator / denominator if enough else None
    with localcontext() as ctx:
        ctx.prec = 70
        value = (
            (Decimal(exact.numerator) / Decimal(exact.denominator)) if exact is not None else None
        )
        if value is not None and value >= Decimal("1e24"):
            raise ValueError("Aggregate exceeds supported range")
        display = (
            str(
                value.quantize(
                    Decimal("0.01") if method in {"RATIO", "MILESTONE"} else Decimal("0.0001"),
                    rounding=ROUND_HALF_UP,
                )
            )
            if value is not None
            else None
        )
    return {
        "actual": display,
        "data_status": "VERIFIED" if enough else "NO_DATA",
        "exact_numerator": str(exact.numerator) if exact is not None else None,
        "exact_denominator": str(exact.denominator) if exact is not None else None,
        "source_count": len(sources),
    }
