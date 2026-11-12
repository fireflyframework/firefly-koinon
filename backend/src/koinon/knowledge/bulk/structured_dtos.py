# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from typing import Annotated, Literal, Self
from uuid import UUID

from flyquery.core.services.ingestion.reader import ProposedTable
from flyquery.core.services.ingestion.stages.reconcile import DeferredReconcileChanges
from pydantic import BaseModel, ConfigDict, Field, model_validator


class NativeValue(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid", frozen=True)


PARSER_FINGERPRINT = "koinon.source-member-locators.v1"


class SourceReplacementTableEvidence(NativeValue, frozen=True):
    name: str = Field(min_length=1, max_length=255)
    sheet_or_json_path: str | None = Field(default=None, max_length=2048)
    n_columns: int = Field(strict=True, ge=0, le=10000)
    n_rows_estimate: int = Field(strict=True, ge=0)

    @model_validator(mode="after")
    def bounded_names(self) -> Self:
        if len(self.name.encode("utf-8")) > 255 or (
            self.sheet_or_json_path is not None and len(self.sheet_or_json_path.encode("utf-8")) > 2048
        ):
            raise ValueError("Discovery names exceed their UTF-8 byte bounds")
        return self


class SourceReplacementDiscovery(NativeValue, frozen=True):
    file_format: str = Field(min_length=1, max_length=32)
    compression: str = Field(min_length=1, max_length=32)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    parser_fingerprint: Literal["koinon.source-member-locators.v1"] = PARSER_FINGERPRINT
    locator_set_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    proposed: tuple[SourceReplacementTableEvidence, ...] = Field(min_length=1, max_length=16)

    @classmethod
    def capture(
        cls,
        *,
        filename: str,
        file_format: str,
        compression: str,
        content_sha256: str,
        proposed: tuple[ProposedTable, ...],
    ) -> Self:
        from koinon.knowledge.bulk.structured_replacement import discover_members, locator_digest

        discovered = discover_members(file_format, proposed)
        root = len(discovered) == 1 and discovered[0].locator == "root"
        return cls(
            file_format=file_format,
            compression=compression,
            content_sha256=content_sha256,
            locator_set_sha256=locator_digest(discovered),
            proposed=tuple(
                SourceReplacementTableEvidence(
                    name=Path(filename).stem if root else value.name,
                    sheet_or_json_path=value.sheet_or_json_path,
                    n_columns=value.n_columns,
                    n_rows_estimate=value.n_rows_estimate,
                )
                for value in proposed
            ),
        )


class ReplacementMemberPlan(NativeValue, frozen=True):
    schema_name: Literal["koinon.dataset-replacement-member.v1"] = Field(
        default="koinon.dataset-replacement-member.v1", alias="schema"
    )
    member_key: str = Field(min_length=1, max_length=2048)
    action: Literal["retain", "add", "remove"]
    table_id: UUID
    catalog_table_id: str = Field(min_length=1, max_length=64)
    snapshot_id: UUID
    ordinal: int | None = Field(default=None, strict=True, ge=0, le=15)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    parser_fingerprint: Literal["koinon.source-member-locators.v1"] = PARSER_FINGERPRINT

    @model_validator(mode="after")
    def live_member_identity(self) -> Self:
        if self.action == "remove":
            if self.ordinal is not None or self.name is not None:
                raise ValueError("Removed members retain historical identity without a live ordinal")
        elif self.ordinal is None or self.name is None:
            raise ValueError("Live members require an ordinal and name")
        return self


class ReplacementBaselineMember(NativeValue, frozen=True):
    member_key: str = Field(min_length=1, max_length=2048)
    table_id: UUID
    catalog_table_id: str = Field(min_length=1, max_length=64)
    snapshot_id: UUID
    source_file_id: UUID
    local_revision: str = Field(min_length=1, max_length=128)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class DatasetReplacementBaseline(NativeValue, frozen=True):
    schema_name: Literal["koinon.dataset-replacement-baseline.v1"] = Field(
        default="koinon.dataset-replacement-baseline.v1", alias="schema"
    )
    dataset_id: UUID
    catalog_dataset_id: str = Field(min_length=1, max_length=64)
    source_attempt_id: str = Field(min_length=1, max_length=64)
    imported_version_id: str = Field(min_length=1, max_length=64)
    catalog_file_version_id: str = Field(min_length=1, max_length=64)
    policy_id: str = Field(min_length=1, max_length=64)
    local_revision: str = Field(pattern=r"^cpv1:[a-f0-9]{64}$")
    source_generation: int = Field(strict=True, ge=1, le=2147483647)
    policy_revision: int = Field(strict=True, ge=1, le=2147483647)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    native_file_id: UUID
    members: tuple[ReplacementBaselineMember, ...] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def exact_original_members(self) -> Self:
        if (
            self.imported_version_id != self.source_attempt_id
            or any(member.source_file_id != self.native_file_id for member in self.members)
            or any(
                len({getattr(member, field) for member in self.members}) != len(self.members)
                for field in ("member_key", "table_id", "catalog_table_id", "snapshot_id")
            )
        ):
            raise ValueError("The replacement requires the complete unique original member set")
        return self


class StructuredOperationIdentity(NativeValue, frozen=True):
    operation_id: UUID
    tenant_id: str = Field(min_length=1, max_length=512)
    workspace_id: UUID
    dataset_id: UUID
    file_id: UUID
    actor: str = Field(min_length=1, max_length=512)
    catalog_source_id: str = Field(min_length=1, max_length=64)
    catalog_dataset_id: str = Field(min_length=1, max_length=64)
    catalog_file_version_id: str = Field(min_length=1, max_length=64)
    filename: str = Field(min_length=1, max_length=255)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(strict=True, ge=1, le=134217728)


class StructuredTablePlan(NativeValue, frozen=True):
    ordinal: int = Field(strict=True, ge=0, le=15)
    table_id: UUID
    snapshot_id: UUID
    name: str = Field(min_length=1, max_length=255)
    catalog_table_id: str | None = Field(default=None, min_length=1, max_length=64)
    member_key: str | None = Field(default=None, min_length=1, max_length=2048)
    parser_fingerprint: str | None = Field(default=None, min_length=1, max_length=128)


class PreparedStructuredTable(StructuredTablePlan, frozen=True):
    catalog_table_id: str = Field(min_length=1, max_length=64)
    lineage_run_id: UUID
    n_columns: int = Field(strict=True, ge=1, le=10000)
    n_rows_actual: int = Field(strict=True, ge=0)
    parquet_key: str = Field(min_length=1, max_length=2048, repr=False)
    parquet_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    parquet_byte_size: int = Field(strict=True, ge=1, le=64 * 1024 * 1024)
    schema_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    reconcile_changes: DeferredReconcileChanges | None = None
    qualified_name: str | None = Field(
        default=None, min_length=1, max_length=2048, exclude_if=lambda value: value is None
    )
    sheet_or_json_path: str | None = Field(
        default=None, max_length=2048, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def matching_reconcile_target(self) -> Self:
        if any(
            value is not None and len(value.encode("utf-8")) > 2048
            for value in (self.qualified_name, self.sheet_or_json_path)
        ):
            raise ValueError("Prepared parser metadata exceeds its UTF-8 byte bounds")
        changes = self.reconcile_changes
        if changes is not None and (
            changes.table_id != self.table_id or changes.next_snapshot_id != self.snapshot_id
        ):
            raise ValueError("Deferred changes must belong to the exact prepared table and snapshot")
        return self


class StructuredCommitReceipt(NativeValue, frozen=True):
    file_id: UUID
    dataset_id: UUID
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(strict=True, ge=1, le=134217728)
    object_key: str = Field(min_length=1, max_length=2048, repr=False)
    tables: tuple[PreparedStructuredTable, ...] = Field(min_length=1, max_length=16)
    source_attempt_id: str | None = Field(default=None, min_length=1, max_length=64)
    source_publication_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class StructuredOperationState(NativeValue, frozen=True):
    identity: StructuredOperationIdentity
    status: Literal["admitted", "prepared", "committed"]
    operation_kind: Literal["initial", "replace"] = "initial"
    baseline: DatasetReplacementBaseline | None = None
    baseline_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    replacement_plan: tuple[ReplacementMemberPlan, ...] = ()
    plan: tuple[StructuredTablePlan, ...] = ()
    prepared: tuple[PreparedStructuredTable, ...] = ()
    receipt: StructuredCommitReceipt | None = Field(default=None, repr=False)
    source_attempt_id: str | None = Field(default=None, min_length=1, max_length=64)
    source_publication_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


TablePlans = Annotated[tuple[StructuredTablePlan, ...], Field(min_length=1, max_length=16)]
