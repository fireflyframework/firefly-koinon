# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from abc import ABC, abstractmethod

from koinon.knowledge.lineage.coordinate_dtos import (
    CellPosition,
    ColumnBindingPage,
    CoordinateManifest,
    CoordinateSelection,
    RowRangePage,
)


class StructuredCoordinatesPort(ABC):
    """Exact native snapshot input coordinates; canonical authority is checked by caller."""

    @abstractmethod
    async def read_manifest(
        self,
        *,
        actor: str,
        tenant_id: str,
        workspace_id: str,
        dataset_id: str,
        table_id: str,
        snapshot_id: str,
    ) -> CoordinateManifest: ...

    @abstractmethod
    async def read_cells(
        self,
        *,
        actor: str,
        tenant_id: str,
        workspace_id: str,
        dataset_id: str,
        table_id: str,
        snapshot_id: str,
        cells: tuple[CellPosition, ...],
    ) -> CoordinateSelection: ...

    @abstractmethod
    async def read_row_ranges(
        self,
        *,
        actor: str,
        tenant_id: str,
        workspace_id: str,
        dataset_id: str,
        table_id: str,
        snapshot_id: str,
        page: int = 1,
        page_size: int = 25,
    ) -> RowRangePage: ...

    @abstractmethod
    async def read_column_bindings(
        self,
        *,
        actor: str,
        tenant_id: str,
        workspace_id: str,
        dataset_id: str,
        table_id: str,
        snapshot_id: str,
        page: int = 1,
        page_size: int = 25,
    ) -> ColumnBindingPage: ...
