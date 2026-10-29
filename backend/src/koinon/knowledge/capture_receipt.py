# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Per-call native observations; no current-source lookup or historical enrichment."""

from asyncio import current_task
from collections.abc import Awaitable, Callable
from dataclasses import replace
from hashlib import sha256
from typing import Any

from pyfly.kernel import ServiceUnavailableException

from koinon.catalog.errors import AccessDenied
from koinon.evidence.dtos import SourceReference
from koinon.knowledge.capture_dtos import (
    DocumentExtractionRead,
    DocumentRead,
    NativeCaptureLimits,
    NativeDatabaseContext,
    NativeReadFingerprint,
    NativeReadOrigin,
    NativeSqlAttempt,
    NativeTableSnapshot,
    SnapshotRead,
)
from koinon.knowledge.capture_limits import NativeCaptureBudget, NativeCaptureBudgetExceeded


def _native_page(value) -> int | None:
    # Native chunk pages use PostgreSQL INTEGER; never parse unbounded metadata integers.
    if type(value) is int:
        page = value
    elif isinstance(value, str) and len(value) <= 16:
        raw = value.strip()
        digits = raw[1:] if raw[:1] in {"+", "-"} else raw
        if not digits or len(digits) > 10 or not digits.isascii() or not digits.isdecimal():
            return None
        page = int(raw)
    else:
        return None
    return page if 1 <= page <= 2147483647 else None


class NativeEvidenceReceipt:
    def __init__(
        self, subject: str, tenant_id: str, *, limits: NativeCaptureLimits | None = None, operation=None
    ):
        self.explicit_limits = limits is not None
        self.limits = limits or NativeCaptureLimits()
        self.budget = NativeCaptureBudget(self.limits)
        self.operation = operation
        self.subject, self.tenant_id, self.owner = subject, tenant_id, current_task()
        self.documents: dict[str, DocumentRead] = {}
        self.knowledge_sources: dict[str, SourceReference] = {}
        self.knowledge_proofs: dict[str, tuple] = {}
        self.document_extractions: dict[tuple[str, str], DocumentExtractionRead] = {}
        self.canonical_documents: dict[tuple[str, str], str] = {}
        self.document_origins: dict[tuple[str, str], tuple[str, str, str, str]] = {}
        self.snapshots: list[SnapshotRead] = []
        self.native_reads: list[NativeReadFingerprint] = []
        self.document_contexts: dict[str, NativeDatabaseContext] = {}
        self.source_contexts: dict[str, NativeDatabaseContext] = {}
        self.source_origins: dict[str, NativeReadOrigin] = {}
        self.model_snapshots: list[SnapshotRead] = []
        self.resolved_snapshots: list[SnapshotRead] = []
        self._attempts: list[NativeSqlAttempt] = []
        self.authorize_model: Callable[[], Awaitable[Any]] | None = None
        self.verify_structured: Callable[[Any, dict], Awaitable[bool | NativeDatabaseContext]] | None = None
        self.complete = True
        self.observed = False
        self.closed = False

    def scope(self, tenant_id, workspace_id, actor):
        if (
            self.closed
            or current_task() is not self.owner
            or actor != self.subject
            or tenant_id != self.tenant_id
            or not workspace_id
        ):
            raise AccessDenied("Native evidence scope is unavailable", code="EVIDENCE_UNAVAILABLE")
        self.observed = True

    def admit_documents(self, tenant_id, workspace_id, actor, admitted):
        self.scope(tenant_id, workspace_id, actor)
        for native_id, (asset, source) in admitted.items():
            key = (str(workspace_id), str(native_id))
            self.canonical_documents[key] = asset.id
            self.document_origins[key] = (asset.id, asset.workspace_id, source.id, asset.name)

    def knowledge_read(
        self, tenant_id, workspace_id, actor, canonical_workspace_id, hit, content_sha256, database=None
    ):
        import json

        self.scope(tenant_id, workspace_id, actor)
        metadata = hit.metadata
        values = dict(
            asset_id=metadata["canonical_knowledge_item_id"],
            knowledge_item_id=metadata["canonical_knowledge_item_id"],
            knowledge_version_id=metadata["knowledge_version_id"],
            knowledge_version=hit.knowledge_version,
            title=metadata["source_title"],
            kind="knowledge_version",
            used_revision="knowledge-content-sha256:" + content_sha256,
            chunk_id=hit.chunk_id,
            quote=hit.content,
        )
        identifier = sha256(
            json.dumps(values, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
        source = SourceReference.model_validate({"id": identifier, **values})
        database = database or NativeDatabaseContext()
        proof = (
            canonical_workspace_id,
            workspace_id,
            hit.source_id,
            sha256(hit.content.encode()).hexdigest(),
            source,
            database,
        )
        if hit.chunk_id in self.knowledge_proofs and self.knowledge_proofs[hit.chunk_id] != proof:
            raise ServiceUnavailableException(
                "The admitted knowledge body changed", code="EVIDENCE_UNAVAILABLE"
            )
        read = NativeReadFingerprint(
            stage="retrieval",
            domain="knowledge",
            tenant_id=tenant_id,
            workspace_id=canonical_workspace_id,
            entity_id=source.asset_id,
            content_sha256=proof[3],
            source_ids=(source.asset_id,),
            snapshot_ids=(),
            read_kind="knowledge_version",
            knowledge_item_id=source.knowledge_item_id,
            knowledge_version_id=source.knowledge_version_id,
            knowledge_version=source.knowledge_version,
            engine=database.engine,
            database=database.database,
            catalog=database.catalog,
            schema=database.schema,
        )
        self.budget.check(self, knowledge_sources=[source], reads=[read])
        self.knowledge_sources[hit.chunk_id], self.knowledge_proofs[hit.chunk_id] = source, proof
        self.native_reads.append(read)

    def knowledge_model(self, stage, prompt, hits, scope):
        self.scope(scope.tenant_id, scope.workspace_id, scope.actor)
        reads = []
        for hit in hits:
            proof = self.knowledge_proofs.get(hit.chunk_id)
            if (
                proof is None
                or proof[1] != scope.workspace_id
                or proof[2] != hit.source_id
                or proof[3] != sha256(hit.content.encode()).hexdigest()
            ):
                raise ServiceUnavailableException(
                    "Exact knowledge provenance is required", code="EVIDENCE_UNAVAILABLE"
                )
            workspace, _, _, _, source, database = proof
            reads.append(
                NativeReadFingerprint(
                    stage=stage,
                    domain="knowledge",
                    tenant_id=scope.tenant_id,
                    workspace_id=workspace,
                    entity_id=source.asset_id,
                    content_sha256=sha256(prompt.encode()).hexdigest(),
                    source_ids=(source.asset_id,),
                    snapshot_ids=(),
                    read_kind="knowledge_version",
                    knowledge_item_id=source.knowledge_item_id,
                    knowledge_version_id=source.knowledge_version_id,
                    knowledge_version=source.knowledge_version,
                    engine=database.engine,
                    database=database.database,
                    catalog=database.catalog,
                    schema=database.schema,
                )
            )
        self.budget.check(self, reads=reads)
        self.native_reads.extend(reads)

    def search(self, tenant_id, workspace_id, actor, hits):
        self.scope(tenant_id, workspace_id, actor)
        for hit in hits:
            identifier, source, content = hit.get("chunk_id"), hit.get("source_id"), hit.get("content")
            if identifier in self.knowledge_proofs:
                proof = self.knowledge_proofs[identifier]
                if (
                    source != proof[2]
                    or not isinstance(content, str)
                    or sha256(content.encode()).hexdigest() != proof[3]
                ):
                    raise ServiceUnavailableException(
                        "Knowledge read differs from its immutable receipt", code="EVIDENCE_UNAVAILABLE"
                    )
                continue
            if not identifier or not source or not isinstance(content, str):
                self.complete = False
                continue
            page = hit.get("page")
            section = hit.get("section_path")
            metadata = hit.get("metadata") or {}
            part = (
                metadata.get("source_part_sha256") is not None
                or metadata.get("page_basis") == "recorded_loader"
            )
            if part and (
                not all(
                    isinstance(metadata.get(key), str) and 0 < len(metadata[key]) <= 64
                    for key in ("source_version_id", "extraction_id", "source_part_id")
                )
                or metadata.get("source_part_id") != str(identifier)
                or metadata.get("page_basis") != "recorded_loader"
                or not isinstance(metadata.get("source_part_sha256"), str)
                or len(metadata["source_part_sha256"]) != 64
                or any(char not in "0123456789abcdef" for char in metadata["source_part_sha256"])
            ):
                raise ServiceUnavailableException(
                    "Exact recorded document part provenance is required", code="EVIDENCE_UNAVAILABLE"
                )
            value = DocumentRead(
                workspace_id=str(workspace_id),
                source_id=str(source),
                chunk_id=str(identifier),
                digest=sha256(content.encode()).hexdigest(),
                quote=content[:8000],
                page=None if part else _native_page(page),
                section=str(section)[:512] if section else None,
                source_version_id=metadata["source_version_id"] if part else None,
                extraction_id=metadata["extraction_id"] if part else None,
                source_part_id=metadata["source_part_id"] if part else None,
                source_part_sha256=metadata["source_part_sha256"] if part else None,
                recorded_page=_native_page(metadata.get("recorded_page")) if part else None,
            )
            if identifier in self.documents and self.documents[identifier] != value:
                self.complete = False
            self.budget.check(self, documents=[value])
            self.documents[identifier] = value

    def query(self, tenant_id, workspace_id, actor, dataset_id, result):
        self.scope(tenant_id, workspace_id, actor)
        pins = result.get("snapshot_pins")
        if (
            result.get("execution_status") not in {"OK", "REFINED_OK"}
            or not result.get("query_id")
            or not isinstance(pins, dict)
            or not pins
            or len(pins) > 500
        ):
            self.complete = False
            return
        sql = result.get("sql")
        if not isinstance(sql, str) or not any(
            row.executed
            and row.outcome == "executed"
            and row.snapshot_pins == pins
            and row.statement_sha256 == sha256(sql.encode()).hexdigest()
            and row.row_count == result.get("row_count")
            for row in self.sql_attempts
        ):
            self.complete = False
            return
        for name, snapshot in pins.items():
            if not isinstance(name, str) or not isinstance(snapshot, str):
                self.complete = False
                continue
            self.record_snapshot(
                self.snapshots,
                SnapshotRead(
                    str(workspace_id), str(dataset_id), None, name, snapshot, str(result["query_id"])
                ),
            )

    def schema(self, tenant_id, workspace_id, actor, dataset_id, table, objects):
        self.scope(tenant_id, workspace_id, actor)
        snapshot = table.get("current_snapshot_id")
        if (
            not snapshot
            or not objects
            or any(str(row.get("snapshot_id")) != str(snapshot) for row in objects)
        ):
            self.complete = False
            return
        self.record_snapshot(
            self.snapshots,
            SnapshotRead(
                str(workspace_id), str(dataset_id), str(table["id"]), str(table["name"]), str(snapshot), None
            ),
        )

    async def authorize(self):
        if self.closed or self.authorize_model is None:
            raise ServiceUnavailableException(
                "Current canonical provenance authority is required", code="EVIDENCE_UNAVAILABLE"
            )
        await self.authorize_model()

    async def structured_model(self, stage, prompt, bundle, scope):
        self.scope(scope.tenant_id, scope.workspace_id, scope.actor)
        objects, sources = {}, set()
        snapshots = []
        for key in ("schema_objects", "schema_inventory", "column_catalog"):
            for hit in bundle.get(key) or []:
                metadata = hit if isinstance(hit, dict) else hit.metadata
                identifier = metadata.get("id") if isinstance(hit, dict) else str(hit.id)
                table, snapshot = metadata.get("table_id"), metadata.get("snapshot_id")
                if not identifier or not table or not snapshot:
                    raise ServiceUnavailableException(
                        "Native schema provenance is missing; refresh the indexed schema",
                        code="EVIDENCE_UNAVAILABLE",
                    )
                objects[str(identifier)] = (str(table), str(snapshot))
                sources.add(str(identifier))
                snapshots.append(
                    SnapshotRead(scope.workspace_id, scope.dataset_id, str(table), None, str(snapshot), None)
                )
        for key in ("examples", "metrics", "glossary", "relations"):
            for hit in bundle.get(key) or []:
                identifier = getattr(hit, "id", None)
                if not identifier:
                    raise ServiceUnavailableException(
                        "Native context provenance is missing", code="EVIDENCE_UNAVAILABLE"
                    )
                sources.add(str(identifier))
        verified = (
            await self.verify_structured(scope, objects) if self.verify_structured and objects else False
        )
        if not verified:
            raise ServiceUnavailableException(
                "Native schema provenance is unavailable", code="EVIDENCE_UNAVAILABLE"
            )
        if len(sources) > 5000 or len({row.snapshot_id for row in snapshots}) > 500:
            raise NativeCaptureBudgetExceeded()
        await self.authorize()
        database = verified if isinstance(verified, NativeDatabaseContext) else NativeDatabaseContext()
        pending_reads = []
        for offset in range(0, len(sources), self.limits.ids_per_read):
            pending_reads.append(
                NativeReadFingerprint(
                    stage,
                    "structured",
                    scope.tenant_id,
                    scope.workspace_id,
                    scope.dataset_id,
                    sha256(prompt.encode()).hexdigest(),
                    tuple(sorted(sources)[offset : offset + self.limits.ids_per_read]),
                    tuple(sorted({row.snapshot_id for row in snapshots})),
                    engine=database.engine,
                    database=database.database,
                    catalog=database.catalog,
                    schema=database.schema,
                    read_kind="metadata",
                )
            )
        self.budget.check(
            self,
            snapshots=snapshots,
            reads=pending_reads,
            minimum_attempts=1 if stage in {"generation", "critic"} else 0,
        )
        self.model_snapshots.extend(row for row in snapshots if row not in self.model_snapshots)
        self.native_reads.extend(pending_reads)

    def record_snapshot(self, collection, row):
        self.budget.check(self, snapshots=[row])
        collection.append(row)

    def structured_resolved(self, rows, scope):
        for row in rows:
            if not row.get("snapshot_id") or not row.get("table_id"):
                raise ServiceUnavailableException(
                    "Native execution provenance is missing", code="EVIDENCE_UNAVAILABLE"
                )
            self.record_snapshot(
                self.resolved_snapshots,
                SnapshotRead(
                    scope.workspace_id,
                    scope.dataset_id,
                    str(row["table_id"]),
                    str(row["name"]),
                    str(row["snapshot_id"]),
                    None,
                ),
            )

    @property
    def sql_attempts(self):
        return tuple(self._attempts)

    def sql_begin(self, stage, sql):
        if len(sql) > 32768:
            self.complete = False
        identifier = len(self._attempts) + 1
        pending = NativeSqlAttempt(
            identifier,
            stage,
            sha256(sql.encode()).hexdigest(),
            None,
            "pending",
            False,
            {},
            statement=sql if len(sql) <= 32768 else None,
        )
        self.budget.check(self, attempts=[pending])
        self._attempts.append(pending)
        return identifier

    def sql_pins(self, identifier, pins):
        if any(not pin for pin in pins.values()):
            raise ServiceUnavailableException(
                "Native SQL snapshot provenance is missing", code="EVIDENCE_UNAVAILABLE"
            )
        self._attempts[identifier - 1] = replace(self._attempts[identifier - 1], snapshot_pins=dict(pins))

    def sql_classified(self, identifier, classification):
        self._attempts[identifier - 1] = replace(
            self._attempts[identifier - 1], classification=classification
        )

    def sql_dataset(self, identifier, dataset):
        self._attempts[identifier - 1] = replace(
            self._attempts[identifier - 1], native_dataset_id=str(dataset)
        )

    def sql_tables(self, identifier, rows):
        tables = tuple(
            NativeTableSnapshot(str(row["table_id"]), str(row["name"]), str(row["snapshot_id"]))
            for row in rows
        )
        updated = replace(self._attempts[identifier - 1], tables=tables)
        self.budget.check(self, attempt_updates={identifier - 1: updated})
        self._attempts[identifier - 1] = updated

    def sql_engine(self, identifier, context, *, executed):
        attempt = self._attempts[identifier - 1]
        self._attempts[identifier - 1] = replace(
            attempt,
            engine=context.get("engine"),
            database=context.get("database"),
            catalog=context.get("catalog"),
            schema=context.get("schema"),
            execution_kind=("imported_snapshot" if attempt.tables else "computed") if context else None,
            executed=executed,
        )

    def sql_started(self, identifier):
        self._attempts[identifier - 1] = replace(self._attempts[identifier - 1], executed=True)

    def sql_executed(self, identifier, result):
        from flyquery.core.services.execution.duckdb_executor import ExecutionResult

        success = isinstance(result, ExecutionResult)
        self._attempts[identifier - 1] = replace(
            self._attempts[identifier - 1],
            outcome="executed" if success else "failed",
            row_count=result.row_count if success else None,
            truncated=result.truncated if success else None,
            reason_code=None if success else "SQL_EXECUTION_FAILED",
        )

    def sql_candidate(self, identifier, status, classification):
        attempt = self._attempts[identifier - 1]
        reason = {
            "firewall": "SQL_FUNCTION_FIREWALL",
            "scope": "SQL_SCOPE_DENIED",
            "error": "SQL_VALIDATION_FAILED",
        }
        self._attempts[identifier - 1] = replace(
            attempt,
            classification=classification,
            outcome=attempt.outcome if attempt.outcome != "pending" else "blocked",
            reason_code=attempt.reason_code
            if attempt.outcome != "pending"
            else reason.get(status, "SQL_NOT_EXECUTED"),
        )

    def sql_failed(self, identifier, cancelled):
        self._attempts[identifier - 1] = replace(
            self._attempts[identifier - 1],
            outcome="cancelled" if cancelled else "failed",
            reason_code="SQL_ATTEMPT_CANCELLED" if cancelled else "SQL_ATTEMPT_FAILED",
        )

    def document_read_hits(self, hits, scope):
        for hit in hits:
            self.document_model("retrieval", hit.content, [hit], scope)

    def document_model(self, stage, prompt, hits, scope):
        self.scope(scope.tenant_id, scope.workspace_id, scope.actor)
        knowledge = [hit for hit in hits if hit.metadata.get("source_kind") == "knowledge_version"]
        if knowledge:
            self.knowledge_model(stage, prompt, knowledge, scope)
            hits = [hit for hit in hits if hit not in knowledge]
            if not hits:
                return
        rows = []
        for hit in hits:
            if (
                not hit.chunk_id
                or not hit.source_id
                or not isinstance(hit.content, str)
                or (scope.allowed_sources is not None and str(hit.source_id) not in scope.allowed_sources)
            ):
                raise ServiceUnavailableException(
                    "Native document provenance is missing", code="EVIDENCE_UNAVAILABLE"
                )
            database = self.document_contexts.get(str(hit.chunk_id))
            if database is not None:
                self.source_contexts[str(hit.source_id)] = database
            self.document_origin(str(hit.source_id), hit.metadata.get("_observed_source_filename"))
            rows.append(
                {
                    "chunk_id": hit.chunk_id,
                    "source_id": hit.source_id,
                    "content": hit.content,
                    "page": hit.metadata.get("page"),
                    "section_path": hit.metadata.get("section_path"),
                    "metadata": hit.metadata,
                }
            )
        if not rows:
            raise ServiceUnavailableException(
                "Native document provenance is missing", code="EVIDENCE_UNAVAILABLE"
            )
        self.search(scope.tenant_id, scope.workspace_id, scope.actor, rows)
        self.document_sync(stage, prompt, tuple(sorted({str(row["source_id"]) for row in rows})), scope)

    def document_view_parts(self, meta, read, scope):
        from koinon.knowledge.rlm_provenance import document_view_parts

        document_view_parts(self, meta, read, scope)

    def document_extraction(self, source_id, source_version_id, extraction_id, scope):
        from flycanon.core.services.query.provenance import current

        if (
            current() is not scope
            or scope is None
            or self.closed
            or not scope.active
            or scope.observer is not self
            or scope.task is not self.owner
            or scope.tenant_id != self.tenant_id
            or scope.actor != self.subject
            or not all(
                isinstance(value, str) and 0 < len(value) <= 64
                for value in (source_id, source_version_id, extraction_id)
            )
            or scope.allowed_sources is not None
            and source_id not in scope.allowed_sources
        ):
            raise ServiceUnavailableException(
                "Native document extraction scope mismatch", code="EVIDENCE_UNAVAILABLE"
            )
        key = (scope.workspace_id, source_id)
        value = DocumentExtractionRead(scope.workspace_id, source_id, source_version_id, extraction_id)
        previous = self.document_extractions.get(key)
        if previous is not None and previous != value:
            raise ServiceUnavailableException(
                "The recorded document view changed within this run", code="EVIDENCE_UNAVAILABLE"
            )
        if previous is None and len(self.document_extractions) >= min(self.limits.sources, self.limits.reads):
            raise NativeCaptureBudgetExceeded()
        self.document_extractions[key] = value

    def document_sync(self, stage, content, sources, scope):
        # Only the trusted domain observer can grant a live RLM worker-thread lease.
        if (
            self.closed
            or not scope.active
            or scope.observer is not self
            or scope.tenant_id != self.tenant_id
            or scope.actor != self.subject
        ):
            raise ServiceUnavailableException(
                "Native document provenance scope mismatch", code="EVIDENCE_UNAVAILABLE"
            )
        if not sources or len(sources) > 5000:
            raise NativeCaptureBudgetExceeded()
        pending_reads = []
        for source in sources:
            database = self.source_contexts.get(source, NativeDatabaseContext())
            extraction = (
                self.document_extractions.get((scope.workspace_id, source))
                if stage.startswith("rlm.") and stage != "rlm.corpus"
                else None
            )
            pending_reads.append(
                NativeReadFingerprint(
                    stage,
                    "canon",
                    scope.tenant_id,
                    scope.workspace_id,
                    source,
                    sha256(content.encode()).hexdigest(),
                    (source,),
                    (),
                    engine=database.engine,
                    database=database.database,
                    catalog=database.catalog,
                    schema=database.schema,
                    read_kind="document_extraction"
                    if extraction
                    else "metadata"
                    if stage == "rlm.corpus"
                    else "indexed_document"
                    if not stage.startswith("rlm.")
                    else None,
                    origin=self.source_origins.get(source),
                    source_version_id=extraction.source_version_id if extraction else None,
                    extraction_id=extraction.extraction_id if extraction else None,
                )
            )
        self.budget.check(self, reads=pending_reads)
        self.native_reads.extend(pending_reads)

    def document_database(self, context, rows):
        database = NativeDatabaseContext(**context)
        for row in rows:
            self.document_contexts[str(row.id)] = database

    def document_origin(self, source, filename):
        if isinstance(filename, str) and 0 < len(filename) <= 512:
            self.source_origins[source] = NativeReadOrigin(original_filename=filename)

    def structured_result(self, execution, scope):
        self.scope(scope.tenant_id, scope.workspace_id, scope.actor)
        digest = sha256(execution["sql"].encode()).hexdigest()
        result = execution["result"]
        self.check_result_bytes({"preview": result.rows[:50]})
        successful = [
            row
            for row in self.sql_attempts
            if row.statement_sha256 == digest
            and row.executed
            and row.outcome == "executed"
            and row.snapshot_pins
            and row.row_count == result.row_count
            and row.truncated == result.truncated
        ]
        if not successful:
            raise ServiceUnavailableException(
                "Native execution provenance is missing; a table-backed result is required",
                code="EVIDENCE_UNAVAILABLE",
            )

    def check_result_bytes(self, value):
        from koinon.knowledge.adapters import _json

        self.budget.check(self, data=_json(value))
