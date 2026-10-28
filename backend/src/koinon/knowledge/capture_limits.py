# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Conservative private audit reservations before native model or SQL entry."""

import json
from dataclasses import asdict

from pyfly.kernel import ServiceUnavailableException

from koinon.api.json_values import portable_json
from koinon.knowledge.capture_dtos import NativeCaptureLimits


class NativeCaptureBudgetExceeded(ServiceUnavailableException):
    def __init__(self):
        super().__init__(
            "Narrow the selected sources or question; the native evidence budget is exhausted",
            code="EVIDENCE_BUDGET_EXCEEDED",
        )


def source_value(
    *,
    kind,
    asset_id,
    source_id,
    title,
    used_revision=None,
    snapshot_id=None,
    query_id=None,
    chunk_id=None,
    quote=None,
    page=None,
    section=None,
):
    return {
        "id": "0" * 64,
        "asset_id": asset_id,
        "source_id": source_id,
        "title": title,
        "kind": kind,
        "knowledge_item_id": None,
        "knowledge_version_id": None,
        "knowledge_version": None,
        "source_version_id": None,
        "extraction_id": None,
        "source_part_id": None,
        "source_part_sha256": None,
        "recorded_page": None,
        "page_basis": None,
        "used_revision": used_revision,
        "snapshot_id": snapshot_id,
        "query_id": query_id,
        "chunk_id": chunk_id,
        "quote": quote,
        "page": page,
        "section": section,
        "current_revision": None,
        "availability": "unverified",
    }


class NativeCaptureBudget:
    def __init__(self, limits: NativeCaptureLimits):
        self.limits = limits

    def check(
        self,
        receipt,
        *,
        documents=(),
        knowledge_sources=(),
        snapshots=(),
        reads=(),
        attempts=(),
        data=None,
        minimum_reads=0,
        minimum_attempts=0,
        minimum_sources=0,
        attempt_updates=None,
    ):
        recorded = {**receipt.documents, **{row.chunk_id: row for row in documents}}
        snapshot_ids = {
            row.snapshot_id
            for row in [*receipt.snapshots, *receipt.model_snapshots, *receipt.resolved_snapshots, *snapshots]
        }
        prospective_reads = [*receipt.native_reads, *reads]
        prospective_attempts = [*receipt.sql_attempts]
        for index, value in (attempt_updates or {}).items():
            prospective_attempts[index] = value
        prospective_attempts.extend(attempts)
        sources = [
            source.model_dump(mode="json")
            for source in {
                **getattr(receipt, "knowledge_sources", {}),
                **{source.chunk_id: source for source in knowledge_sources},
            }.values()
        ]
        for row in recorded.values():
            origin = receipt.document_origins.get((row.workspace_id, row.source_id))
            asset, workspace, source, title = origin or ("0" * 64, "0" * 64, "0" * 64, "x" * 255)
            sources.append(
                source_value(
                    kind="document",
                    asset_id=asset,
                    source_id=source,
                    title=title,
                    used_revision="chunk-sha256:" + row.digest,
                    chunk_id=row.chunk_id,
                    quote=row.quote,
                    page=row.page,
                    section=row.section,
                )
            )
            if row.source_part_id:
                sources[-1].update(
                    source_version_id=row.source_version_id,
                    extraction_id=row.extraction_id,
                    source_part_id=row.source_part_id,
                    source_part_sha256=row.source_part_sha256,
                    recorded_page=row.recorded_page,
                    page_basis="recorded_loader",
                    chunk_id=None,
                    used_revision="source-part-sha256:" + (row.source_part_sha256 or ""),
                )
        for snapshot in snapshot_ids:
            for query_id in [None] if receipt.operation == "schema" else [None, "0" * 64]:
                sources.append(
                    source_value(
                        kind="dataset",
                        asset_id="0" * 64,
                        source_id="0" * 64,
                        title="x" * 255,
                        used_revision=snapshot,
                        snapshot_id=snapshot,
                        query_id=query_id,
                    )
                )
        if (
            len(prospective_reads) + minimum_reads > self.limits.reads
            or len(prospective_attempts) + minimum_attempts > self.limits.attempts
            or len(sources) + minimum_sources > self.limits.sources
            or any(len(row.source_ids) > self.limits.ids_per_read for row in prospective_reads)
        ):
            raise NativeCaptureBudgetExceeded()
        self._bytes(data or {}, sources, prospective_reads, prospective_attempts)

    def envelope(self, capture):
        if (
            len(capture.native_reads) > self.limits.reads
            or len(capture.sql_attempts) > self.limits.attempts
            or len(capture.sources) > self.limits.sources
        ):
            raise NativeCaptureBudgetExceeded()
        self._bytes(
            capture.data,
            [row.model_dump(mode="json") for row in capture.sources],
            capture.native_reads,
            capture.sql_attempts,
        )

    def _bytes(self, data, sources, reads, attempts):
        def wire(row):
            return {**asdict(row), "result_id": "0" * 64, "generation_id": "0" * 64}

        payload = {
            "data": portable_json(data),
            "asset_ids": ["0" * 64 for _ in sources],
            "origin_token_id": "0" * 64,
            "generation_id": "0" * 64,
            "source_manifest": {"version": 1, "complete": False, "sources": sources},
            "native_reads": [wire(row) for row in reads],
            "sql_attempts": [wire(row) for row in attempts],
        }
        # Queue identities/envelope and not-yet-observed engine identifiers are reserved before entry.
        size = len(json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(", ", ": ")).encode())
        size += 2048 + 256 * (len(reads) + len(attempts)) + 1536 * len(attempts)
        if size > self.limits.receipt_bytes or len(json.dumps(data)) > self.limits.receipt_bytes:
            raise NativeCaptureBudgetExceeded()
