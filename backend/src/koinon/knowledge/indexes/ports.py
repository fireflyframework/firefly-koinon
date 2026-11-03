# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Optional parent workflow authority, enforced within the primary publication unit."""

from typing import Protocol, runtime_checkable

from koinon.knowledge.indexes.entities import KnowledgeIndex


@runtime_checkable
class IndexParentAuthority(Protocol):
    async def check(
        self, parent_id: str, tenant_id: str, index_record: KnowledgeIndex | None = None
    ) -> None: ...
