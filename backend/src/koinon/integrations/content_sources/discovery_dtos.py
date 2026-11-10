# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Account-bound discovery pages, separate from drive-scoped change cursors."""

from dataclasses import dataclass, field
from typing import Literal

from koinon.integrations.content_sources.dtos import Account, bounded


@dataclass(frozen=True, slots=True)
class DiscoveryCursor:
    account: Account
    operation: str
    token: str = field(repr=False)

    def __post_init__(self):
        bounded(self.operation, limit=2048)
        bounded(self.token, limit=16384)


@dataclass(frozen=True, slots=True)
class SourceLocation:
    id: str
    name: str
    kind: Literal["site", "drive"]


@dataclass(frozen=True, slots=True)
class LocationPage:
    items: tuple[SourceLocation, ...]
    next_cursor: DiscoveryCursor | None
