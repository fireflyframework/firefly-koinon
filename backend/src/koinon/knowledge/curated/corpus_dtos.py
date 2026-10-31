# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private primary admission pins and native projection facts."""

from dataclasses import dataclass, field

from koinon.knowledge.capture_dtos import NativeDatabaseContext


@dataclass(frozen=True, slots=True)
class ServingVersion:
    item_id: str
    workspace_id: str
    native_item_id: str
    native_workspace_id: str
    version_id: str
    version: int


@dataclass(frozen=True, slots=True)
class CuratedPartRecord:
    id: str
    tenant_id: str
    workspace_id: str
    canonical_item_id: str
    native_item_id: str
    native_version_id: str
    ordinal: int
    content: str = field(repr=False)
    sha256: str
    char_start: int
    char_end: int


@dataclass(frozen=True, slots=True)
class CuratedProjection:
    parts: tuple[CuratedPartRecord, ...]
    database: NativeDatabaseContext
