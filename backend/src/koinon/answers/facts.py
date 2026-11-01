# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Serialize server-created factual units outside untrusted native result data."""

import json
from typing import cast

from pydantic import JsonValue, TypeAdapter

from koinon.knowledge.answer_evidence import AnswerFact

_FACT = TypeAdapter(AnswerFact)


def fact_value(fact: AnswerFact) -> dict[str, JsonValue]:
    return cast(dict[str, JsonValue], json.loads(_FACT.dump_json(fact)))


def recorded_facts(value: object) -> tuple[AnswerFact, ...]:
    if not isinstance(value, dict) or value.get("version") != 1 or not isinstance(value.get("items"), list):
        return ()
    return tuple(_FACT.validate_python(item) for item in value["items"])
