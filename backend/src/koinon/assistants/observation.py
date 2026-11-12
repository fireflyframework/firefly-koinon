# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Explicit safe forensic projections for interrupted native work."""

import re

_STAGES = {"retrieval", "reranking", "query", "schema", "rlm.root", "rlm.child", "metadata", "answer"}
_STATES = {"ok", "error", "ready", "completed", "rejected", "failed", "halted", "cancelled", "denied"}


def source_identity(source):
    value = source.model_dump(
        mode="json",
        include={
            "id",
            "asset_id",
            "source_id",
            "kind",
            "knowledge_item_id",
            "knowledge_version_id",
            "knowledge_version",
            "source_version_id",
            "extraction_id",
            "source_part_id",
            "source_part_sha256",
            "page_basis",
            "snapshot_id",
            "query_id",
            "chunk_id",
        },
        exclude_none=True,
    )
    revision = source.used_revision
    if revision and re.fullmatch(r"[a-z-]+-sha256:[a-f0-9]{64}", revision):
        value["used_revision"] = revision
    # A fixed redaction preserves the historical DTO shape without copying its title.
    value.update(title="Unavailable source", availability="unverified")
    return value


def native_receipts(reads, attempts, tools, *, include_tools):
    output = {
        "native_reads": [
            {
                **row.model_dump(
                    mode="json",
                    include={
                        "result_id",
                        "generation_id",
                        "domain",
                        "tenant_id",
                        "workspace_id",
                        "entity_id",
                        "content_sha256",
                        "source_ids",
                        "snapshot_ids",
                        "read_kind",
                        "source_version_id",
                        "extraction_id",
                        "knowledge_item_id",
                        "knowledge_version_id",
                        "knowledge_version",
                    },
                ),
                "stage": row.stage if row.stage in _STAGES else "unavailable",
            }
            for row in reads
        ],
        "sql_attempts": [
            {
                **row.model_dump(
                    mode="json",
                    include={
                        "result_id",
                        "generation_id",
                        "ordinal",
                        "statement_sha256",
                        "executed",
                        "row_count",
                        "truncated",
                        "execution_kind",
                        "dataset_id",
                        "native_dataset_id",
                    },
                ),
                "stage": row.stage if row.stage in _STAGES else "unavailable",
                "outcome": row.outcome if row.outcome in _STATES else "failed",
                "snapshot_pins": {table.table_id: table.snapshot_id for table in row.tables},
            }
            for row in attempts
        ],
    }
    if include_tools:
        output["rlm_tools"] = [
            {
                **row.model_dump(
                    mode="json",
                    include={
                        "result_id",
                        "generation_id",
                        "tenant_id",
                        "workspace_id",
                        "source_ids",
                        "knowledge_item_ids",
                        "tool_call_id",
                        "tool_name",
                        "request_sha256",
                        "schema_sha256",
                        "arguments_sha256",
                        "result_sha256",
                        "result_kind",
                        "execution_sha256",
                        "outcome",
                    },
                ),
                "execution_status": row.execution_status if row.execution_status in _STATES else "failed",
                "execution_state": row.execution_state if row.execution_state in _STATES else "failed",
            }
            for row in tools
        ]
    return output
