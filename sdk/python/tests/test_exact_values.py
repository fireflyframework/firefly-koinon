# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from decimal import Decimal

import pytest

from koinon_sdk import exact_decimal, exact_integer


@pytest.mark.parametrize(
    "value,expected",
    [
        (0, 0),
        (9007199254740991, 9007199254740991),
        (-9007199254740991, -9007199254740991),
        (9007199254740992, "9007199254740992"),
        (-9007199254740992, "-9007199254740992"),
        (18446744073709551615, "18446744073709551615"),
    ],
)
def test_integer_safe_boundaries(value, expected):
    assert exact_integer(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [("1.2300", "1.2300"), ("-0.1234567890123456789", "-0.1234567890123456789"), ("1E+3", "1000")],
)
def test_decimal_scale_and_exact_fraction(value, expected):
    assert exact_decimal(Decimal(value)) == expected


@pytest.mark.parametrize("value", [True, False, 1.5, "42"])
def test_integer_rejects_boolean_or_coercion(value):
    with pytest.raises(TypeError):
        exact_integer(value)


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_decimal_rejects_nonfinite(value):
    with pytest.raises(ValueError):
        exact_decimal(value)
