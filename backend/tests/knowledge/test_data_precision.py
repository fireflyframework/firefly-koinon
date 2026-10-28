# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass
from decimal import Decimal

import numpy as np
import pytest
from pydantic import BaseModel

from koinon.knowledge.adapters import _json


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (2**53 - 1, 2**53 - 1),
        (2**53, "9007199254740992"),
        (2**53 + 1, "9007199254740993"),
        (-(2**53 - 1), -(2**53 - 1)),
        (-(2**53), "-9007199254740992"),
        (np.int64(2**53 + 1), "9007199254740993"),
        (np.int64(-(2**53) - 1), "-9007199254740993"),
        (np.uint64(2**64 - 1), "18446744073709551615"),
        (np.int32(12), 12),
        (True, True),
        (False, False),
        (np.bool_(True), True),
        (np.bool_(False), False),
        (Decimal("-9007199254740993.12345678901234567890"), "-9007199254740993.12345678901234567890"),
        (1.25, 1.25),
        (np.float64(-1.25), -1.25),
    ],
)
def test_exact_data_wire_boundaries(value, expected):
    actual = _json(value)
    assert actual == expected and type(actual) is type(expected)


def test_models_dataclasses_and_arrays_keep_nested_exact_values_and_bounded_counters():
    class Result(BaseModel):
        row_count: int
        preview: list[dict]

    result = Result(
        row_count=1,
        preview=[{"count": 2**53 + 1, "amount": Decimal("1.00000000000000000001"), "eligible": True}],
    )

    @dataclass
    class Envelope:
        result: Result
        values: object

    wire = _json(Envelope(result, np.array([[2**53 + 1, -(2**53 + 1)]], dtype=np.int64)))
    assert wire == {
        "result": {
            "row_count": 1,
            "preview": [{"count": "9007199254740993", "amount": "1.00000000000000000001", "eligible": True}],
        },
        "values": [["9007199254740993", "-9007199254740993"]],
    }
    assert type(wire["result"]["row_count"]) is int
