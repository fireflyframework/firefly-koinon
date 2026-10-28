# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Safe immutable constructor metadata, separate from credentials and model traffic."""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Literal

from httpx import Timeout


def _settings_value(value):
    if isinstance(value, Timeout):
        return {"$type": "httpx.Timeout", "values": value.as_dict()}
    raise TypeError("Model setting has no qualified canonical encoding")


def settings_digest(settings: Mapping[str, Any]) -> str | None:
    try:
        payload = json.dumps(
            dict(settings), sort_keys=True, ensure_ascii=False, allow_nan=False, default=_settings_value
        ).encode()
    except (TypeError, ValueError, OverflowError, RecursionError):
        return None
    if len(payload) > 65536:
        return None
    return sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class ModelBindingProvenance:
    mode: Literal["provider", "current_agent"]
    assignment_id: str | None = None
    assignment_revision: int | None = None
    provider_id: str | None = None
    provider_revision: int | None = None
    selected_model_id: str | None = None
    model_options_sha256: str | None = None
    agent_id: str | None = None
    agent_revision: int | None = None

    def __post_init__(self):
        if self.mode not in {"provider", "current_agent"}:
            raise ValueError("Unsupported binding provenance mode")
        for value in (self.assignment_revision, self.provider_revision, self.agent_revision):
            if value is not None and (type(value) is not int or value < 1):
                raise ValueError("Recorded revisions must be positive integers")
        for value in (self.assignment_id, self.provider_id, self.agent_id):
            if value is not None and (not isinstance(value, str) or not 1 <= len(value) <= 64):
                raise ValueError("Recorded identities must be bounded identifiers")
        if self.selected_model_id is not None and not 1 <= len(self.selected_model_id) <= 255:
            raise ValueError("Recorded model identity exceeds its limit")
        if self.model_options_sha256 is not None and not re.fullmatch(
            r"[a-f0-9]{64}", self.model_options_sha256
        ):
            raise ValueError("Recorded model options require a SHA256 digest")

    @property
    def complete(self) -> bool:
        base = bool(
            self.assignment_id
            and self.provider_id
            and self.selected_model_id
            and type(self.assignment_revision) is int
            and self.assignment_revision > 0
            and type(self.provider_revision) is int
            and self.provider_revision > 0
            and re.fullmatch(r"[a-f0-9]{64}", self.model_options_sha256 or "")
        )
        return base and (
            self.mode == "provider"
            or bool(self.agent_id and type(self.agent_revision) is int and self.agent_revision > 0)
        )


@dataclass(frozen=True, slots=True)
class AgentConstruction:
    role: str
    provenance: ModelBindingProvenance | None
    provider: str
    model_name: str
    model_class: str
    api: str
    output_mode: Literal["text", "native", "default"]
    instructions_sha256: str
    applied_model_settings_sha256: str | None
