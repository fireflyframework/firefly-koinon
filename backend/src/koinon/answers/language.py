# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""One bounded language decision for server-rendered text; quotations remain exact."""

from collections.abc import Mapping
from typing import Literal

AnswerLanguage = Literal["en", "es"]


def effective_language(preferences: Mapping, *, turn: AnswerLanguage | None = None) -> AnswerLanguage:
    if turn is not None:
        return turn
    recorded = preferences.get("effective_language")
    if recorded in {"en", "es"}:
        return recorded
    preferred = preferences.get("response_language", "auto")
    value = preferences.get("locale", "en-US") if preferred == "auto" else preferred
    return "es" if isinstance(value, str) and value.lower().startswith("es") else "en"
