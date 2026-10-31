# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded presentation claims selected by deployment policy, never access grants."""

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from pyfly.core import config_properties
from pyfly.security.context import SecurityContext

from koinon.organization_people.dtos import OrganizationProfileFields

DEFAULT_PRESENTATION_CLAIMS = (
    "job_title",
    "title",
    "unit_external_key",
    "department",
    "manager_external_subject",
)


@config_properties(prefix="koinon.identity.presentation_claims")
@dataclass
class PresentationClaimSettings:
    extra_names: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.extra_names, list) or len(self.extra_names) > 32:
            raise ValueError("Choose at most 32 additional presentation claims")
        for name in self.extra_names:
            if (
                not isinstance(name, str)
                or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,79}", name)
                or name.casefold().startswith("koinon_")
                or name.casefold() in {"name", "locale", "picture", "sid", "iat", "auth_time", "amr"}
            ):
                raise ValueError("Choose a flat presentation claim without identity or credential fields")
            OrganizationProfileFields.presentation_only(name)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*DEFAULT_PRESENTATION_CLAIMS, *self.extra_names)))


class VerifiedProfileObserver(Protocol):
    async def observe_bearer(self, context: SecurityContext) -> None: ...


def bounded_presentation_claims(claims: dict[str, Any], names: tuple[str, ...]) -> dict[str, Any]:
    result = dict(claims)
    for name in names:
        if name not in result:
            continue
        value = result[name]
        if value is not None and not (
            isinstance(value, str)
            and len(value) <= 512
            and all(ord(char) >= 32 and ord(char) != 127 for char in value)
        ):
            result[name] = {"invalid": True}
    return result
