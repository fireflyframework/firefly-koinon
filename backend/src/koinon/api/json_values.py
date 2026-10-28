# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Preserve exact values across clients with different JSON number limits."""

from decimal import Decimal
from typing import Any

from pydantic import JsonValue

SAFE_INTEGER_LIMIT = (1 << 53) - 1


def portable_json(value: Any) -> JsonValue:
    if value is None or isinstance(value, (str, bool, float)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, int):
        return str(value) if abs(value) > SAFE_INTEGER_LIMIT else value
    if isinstance(value, dict):
        return {str(key): portable_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [portable_json(item) for item in value]
    raise TypeError(f"Unsupported JSON value type: {type(value).__name__}")
