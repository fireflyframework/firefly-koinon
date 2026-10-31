# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from koinon.knowledge.bulk_queries.dtos import BatchQueryOutcome


class NativeValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class QueryOperationIdentity(NativeValue):
    operation_id: UUID
    tenant_id: str = Field(min_length=1, max_length=64)
    subject: str = Field(min_length=1, max_length=512)
    workspace_id: UUID
    dataset_id: UUID
    catalog_workspace_id: str = Field(min_length=1, max_length=64)
    catalog_dataset_id: str = Field(min_length=1, max_length=64)
    question: str = Field(min_length=1, max_length=8000)
    policy_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    connections_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class QuerySnapshotReference(NativeValue):
    table_id: UUID
    snapshot_id: UUID
    qualified_name: str = Field(min_length=1, max_length=512)


class QueryOperationReceipt(NativeValue):
    identity: QueryOperationIdentity
    result: BatchQueryOutcome
    snapshots: tuple[QuerySnapshotReference, ...] = Field(max_length=128)
