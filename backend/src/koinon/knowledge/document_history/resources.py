# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from collections.abc import Callable
from dataclasses import dataclass

from flycanon.core.services.sources.lineage.service import DocumentLineage


@dataclass(frozen=True)
class DocumentHistoryResources:
    """Lazy native resources let disabled domains start without opening storage."""

    lineage: Callable[[], DocumentLineage]
