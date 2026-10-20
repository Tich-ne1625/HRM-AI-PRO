"""Exact, bounded decimal strings for the public domain API."""

import re
from decimal import Decimal
from typing import Annotated

from pydantic import BeforeValidator, Field, PlainSerializer, StrictInt


def decimal_string(value: object, scale: int) -> Decimal:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value):
        raise ValueError("Use a finite nonnegative decimal string without exponent or whitespace")
    # Bound work before Decimal parsing; accepted columns need at most 15 chars.
    if len(value) > 32:
        raise ValueError("Decimal string is too long")
    if "." in value and len(value.split(".")[1]) > scale:
        raise ValueError("Too many fractional digits")
    return Decimal(value)


def two_places(value: Decimal) -> str:
    return format(value, ".2f")


def four_places(value: Decimal) -> str:
    return format(value, ".4f")


Percentage = Annotated[
    Decimal,
    BeforeValidator(lambda value: decimal_string(value, 2)),
    Field(ge=0, le=100, max_digits=5, decimal_places=2),
    PlainSerializer(two_places, return_type=str, when_used="json"),
]
PositiveWeight = Annotated[Percentage, Field(gt=0)]
Quantity = Annotated[
    Decimal,
    BeforeValidator(lambda value: decimal_string(value, 4)),
    Field(ge=0, le=Decimal("9999999999.9999"), max_digits=14, decimal_places=4),
    PlainSerializer(four_places, return_type=str, when_used="json"),
]
PositiveQuantity = Annotated[Quantity, Field(gt=0)]
Cap = Annotated[
    Decimal,
    BeforeValidator(lambda value: decimal_string(value, 2)),
    Field(gt=0, le=Decimal("99999.99"), max_digits=7, decimal_places=2),
    PlainSerializer(two_places, return_type=str, when_used="json"),
]
Version = Annotated[StrictInt, Field(ge=1)]
