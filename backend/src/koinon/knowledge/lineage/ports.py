# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from abc import ABC, abstractmethod

from koinon.knowledge.lineage.dtos import LineagePage, SnapshotLineage


class StructuredSnapshotLineagePort(ABC):
    """Internal native IDs only; caller first authorizes canonical ancestors and PAT bounds."""

    @abstractmethod
    async def read_snapshots(
        self,
        *,
        actor: str,
        tenant_id: str,
        workspace_id: str,
        dataset_id: str,
        snapshot_ids: tuple[str, ...],
    ) -> tuple[SnapshotLineage, ...]: ...

    @abstractmethod
    async def read_table_history(
        self,
        *,
        actor: str,
        tenant_id: str,
        workspace_id: str,
        dataset_id: str,
        table_id: str,
        page: int = 1,
        page_size: int = 25,
    ) -> LineagePage: ...
