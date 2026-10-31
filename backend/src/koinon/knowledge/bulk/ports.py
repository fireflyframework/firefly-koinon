# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

from koinon.knowledge.bulk.queue import BulkLease


@dataclass(frozen=True)
class NativeTableCommit:
    catalog_table_id: str
    table_id: str
    snapshot_id: str
    n_columns: int
    n_rows_actual: int


@dataclass(frozen=True)
class NativeCommit:
    domain: Literal["canon", "structured"]
    native_workspace_id: str
    native_source_id: str
    native_asset_id: str
    sha256: str
    size_bytes: int
    source_version_id: str | None = None
    extraction_id: str | None = None
    n_chunks: int = 0
    object_key: str = field(default="", repr=False)
    file_version_id: str | None = None
    native_file_id: str | None = None
    tables: tuple[NativeTableCommit, ...] = ()


@dataclass(frozen=True)
class NativeObservation:
    status: Literal["absent", "admitted", "prepared", "committed"]
    receipt: NativeCommit | None = None


class BulkIntakePort(ABC):
    @abstractmethod
    async def reserve(self, lease: BulkLease) -> None: ...
    @abstractmethod
    async def inspect(self, lease: BulkLease) -> NativeObservation: ...
    @abstractmethod
    async def execute(self, lease: BulkLease, content: bytes) -> NativeCommit: ...
    async def finalize_prepared(self, lease: BulkLease) -> NativeCommit:
        from pyfly.kernel import ConflictException

        raise ConflictException("Prepared publication is unavailable", code="BULK_NATIVE_OUTCOME_UNRESOLVED")

    @abstractmethod
    async def acknowledge(self, lease: BulkLease, receipt: NativeCommit) -> None: ...

    @abstractmethod
    async def acknowledge_committed(self, lease: BulkLease, receipt: NativeCommit) -> None: ...
