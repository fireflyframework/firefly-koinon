# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from koinon.knowledge.bulk.recovery_intent import NativeFailureProof

if TYPE_CHECKING:
    from koinon.knowledge.bulk.entities import BulkItem
    from koinon.knowledge.bulk.queue import BulkLease


@dataclass(frozen=True, slots=True)
class SourceIntakeItem:
    object_id: str
    generation: int
    remote_version: str
    observation_id: str
    work_id: str
    page_sequence: int
    item_sequence: int
    event_sha256: str


@dataclass(frozen=True, slots=True)
class SourceIntakeAdmission:
    tenant_id: str
    owner: str
    mapping_id: str
    mapping_revision: int
    connection_revision: int
    run_id: str
    destination: tuple[str, str, str]
    items: tuple[SourceIntakeItem, ...]


@dataclass(frozen=True, slots=True)
class SourcePublicationBinding:
    attempt_id: str
    descriptor_sha256: str


class SourceIntakeGuard(ABC):
    @abstractmethod
    async def admit(self, admission: SourceIntakeAdmission) -> None: ...

    @abstractmethod
    async def bind(self, admission: SourceIntakeAdmission, ordinal: int, item: BulkItem) -> None: ...


class SourceIntakeWriter(ABC):
    """Private source producer boundary; proofs and write permits are never client input."""

    @abstractmethod
    def is_run_execution(self, execution: object) -> bool: ...

    @abstractmethod
    async def admission_for(self, execution: BulkLease) -> SourceIntakeAdmission | None: ...

    @abstractmethod
    def prepare(
        self, admission: SourceIntakeAdmission, *, execution: object
    ) -> AbstractAsyncContextManager: ...

    @abstractmethod
    def fence(self, admission: SourceIntakeAdmission) -> AbstractAsyncContextManager: ...

    @abstractmethod
    def require_fence(self, admission: SourceIntakeAdmission) -> None: ...

    @abstractmethod
    async def validate_intake(self, admission: SourceIntakeAdmission, manifest) -> None: ...

    @abstractmethod
    async def pin_table_targets(
        self, admission: SourceIntakeAdmission, execution: BulkLease, identifiers: tuple[str, ...]
    ) -> None: ...

    @abstractmethod
    async def freeze_publication(
        self, admission: SourceIntakeAdmission, *, execution: BulkLease, members: tuple = ()
    ) -> SourcePublicationBinding: ...

    @abstractmethod
    def structured_producer(
        self, admission: SourceIntakeAdmission, *, execution, operation, publication
    ) -> AbstractAsyncContextManager: ...

    @abstractmethod
    def creation_operations(self, entries: tuple) -> tuple: ...

    @abstractmethod
    def open(self, admission: SourceIntakeAdmission, operations: tuple) -> AbstractAsyncContextManager: ...

    @abstractmethod
    async def publication_plan(
        self, admission: SourceIntakeAdmission, execution: BulkLease, receipt: NativeCommit
    ) -> tuple[tuple, tuple]: ...

    @abstractmethod
    async def replay_publication(self, admission, execution, receipt) -> bool: ...

    @abstractmethod
    def completion(
        self, admission: SourceIntakeAdmission, execution: BulkLease, receipt: NativeCommit
    ) -> AbstractAsyncContextManager: ...


class SourcePublicationFence(ABC):
    @abstractmethod
    async def check(self, lease: BulkLease) -> None: ...

    @abstractmethod
    async def reconcile(self, lease: BulkLease) -> None: ...

    @abstractmethod
    async def committed(self, lease: BulkLease, receipt: NativeCommit) -> None: ...

    @abstractmethod
    async def settle(self, lease: BulkLease, receipt: NativeCommit) -> None: ...


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
    source_attempt_id: str | None = None
    source_publication_sha256: str | None = None


@dataclass(frozen=True)
class NativeObservation:
    status: Literal["absent", "admitted", "failed", "prepared", "committed"]
    receipt: NativeCommit | None = None
    failure: NativeFailureProof | None = None


class BulkIntakePort(ABC):
    @abstractmethod
    async def reserve(self, lease: BulkLease) -> None: ...
    @abstractmethod
    async def inspect(self, lease: BulkLease) -> NativeObservation: ...
    async def inspect_committed(self, lease: BulkLease) -> NativeObservation:
        from pyfly.kernel import ConflictException

        raise ConflictException(
            "Safe receipt inspection is unavailable", code="BULK_NATIVE_OUTCOME_UNRESOLVED"
        )

    @abstractmethod
    async def execute(self, lease: BulkLease, content: bytes) -> NativeCommit: ...
    async def execute_file(self, lease: BulkLease, path) -> NativeCommit:
        from pyfly.kernel import ConflictException

        raise ConflictException(
            "This native intake does not support file transport", code="BULK_FILE_INTAKE_REQUIRED"
        )

    async def finalize_prepared(self, lease: BulkLease) -> NativeCommit:
        from pyfly.kernel import ConflictException

        raise ConflictException("Prepared publication is unavailable", code="BULK_NATIVE_OUTCOME_UNRESOLVED")

    @abstractmethod
    async def acknowledge(self, lease: BulkLease, receipt: NativeCommit) -> None: ...

    @abstractmethod
    async def acknowledge_committed(self, lease: BulkLease, receipt: NativeCommit) -> None: ...

    async def settle_source_receipt(self, lease: BulkLease, receipt: NativeCommit) -> None:
        from pyfly.kernel import ConflictException

        raise ConflictException("Source receipt settlement is unavailable", code="SOURCE_PUBLICATION_DENIED")
