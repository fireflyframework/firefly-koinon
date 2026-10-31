# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private optimistic authority stamps; no credential or source content is retained."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CuratedReleaseStamp:
    identity_sha256: str
    material_sha256: str
    row_count: int
