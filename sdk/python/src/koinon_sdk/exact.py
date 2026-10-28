# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Explicit exact JSON cells; no automatic coercion of opaque application data."""

from decimal import Decimal

SAFE_INTEGER = 9007199254740991


def exact_decimal(value: Decimal) -> str:
    if type(value) is not Decimal:
        raise TypeError("Supply Decimal, never a binary floating-point approximation")
    if not value.is_finite():
        raise ValueError("An exact JSON decimal must be finite")
    return format(value, "f")


def exact_integer(value: int) -> int | str:
    if type(value) is not int:
        raise TypeError("Supply an integer; boolean and implicit coercion are not supported")
    return value if -SAFE_INTEGER <= value <= SAFE_INTEGER else str(value)
