# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Capture actual native tool reads; historical results are never enriched with current versions."""

import json
from asyncio import CancelledError
from dataclasses import replace
from hashlib import sha256
from uuid import UUID

from pyfly.container import service
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit
from pyfly.kernel import ForbiddenException, ServiceUnavailableException
from sqlalchemy import select

from koinon.catalog.errors import AccessDenied
from koinon.evidence.dtos import SourceReference
from koinon.knowledge.adapters import native_scope
from koinon.knowledge.capture_dtos import CapturedEvidence, NativeCaptureLimits
from koinon.knowledge.capture_limits import NativeCaptureBudgetExceeded
from koinon.knowledge.capture_receipt import NativeEvidenceReceipt
from koinon.knowledge.service import KnowledgeFacade


class NativeEvidenceFailure(Exception):
    """Audit-only attempted native work; never factual tool evidence."""

    capture: CapturedEvidence
    denied: bool


class NativeEvidenceDenied(AccessDenied, NativeEvidenceFailure):
    pass


class NativeEvidenceUnavailable(ServiceUnavailableException, NativeEvidenceFailure):
    pass


def failure_capture(error: BaseException) -> CapturedEvidence | None:
    if isinstance(error, NativeEvidenceFailure):
        return error.capture
    capture = getattr(error, "native_evidence_capture", None) if isinstance(error, CancelledError) else None
    return capture if isinstance(capture, CapturedEvidence) else None


def canonical_dataset_attempts(receipt, chain, binding):
    attempts = []
    for attempt in receipt.sql_attempts:
        if attempt.native_dataset_id is not None and attempt.native_dataset_id != binding.native_id:
            raise unavailable()
        attempts.append(replace(attempt, dataset_id=chain[0].id))
    return tuple(attempts)


def canonical_dataset_reads(receipt, tenant_id, chain, binding):
    reads = []
    for read in receipt.native_reads:
        if (
            read.domain != "structured"
            or read.tenant_id != tenant_id
            or read.workspace_id != binding.native_workspace_id
            or read.entity_id != binding.native_id
        ):
            raise unavailable()
        reads.append(replace(read, entity_id=chain[0].id, workspace_id=chain[0].workspace_id))
    return tuple(reads)


def failed_receipt(error, receipt, tenant_id, chain=None, binding=None):
    sources, reads = {}, []
    if chain is not None and binding is not None:
        reads = list(canonical_dataset_reads(receipt, tenant_id, chain, binding))
        observed = receipt.snapshots + receipt.model_snapshots + receipt.resolved_snapshots
        for row in observed:
            if row.workspace_id != binding.native_workspace_id or row.dataset_id != binding.native_id:
                continue
            value = reference(
                asset_id=chain[0].id,
                source_id=chain[1].id,
                kind="dataset",
                title=chain[0].name,
                used_revision=row.snapshot_id,
                snapshot_id=row.snapshot_id,
                query_id=row.query_id,
            )
            sources[value.id] = value
        if not sources and not receipt.explicit_limits:
            value = reference(
                asset_id=chain[0].id, source_id=chain[1].id, kind="dataset", title=chain[0].name
            )
            sources[value.id] = value
    else:
        from koinon.knowledge.rlm_provenance import execution_views

        used = (
            execution_views(receipt)
            if any(row.stage.startswith("rlm.") for row in receipt.native_reads)
            else None
        )
        from koinon.knowledge.curated.rlm_receipts import execution_views as knowledge_execution_views

        knowledge_used = knowledge_execution_views(receipt) if used is not None else None
        sources.update(
            {
                source.id: source
                for source in receipt.knowledge_sources.values()
                if knowledge_used is None
                or any(
                    meta.item_id == source.asset_id and (meta.workspace_id, meta.item_id) in knowledge_used
                    for meta in receipt.curated_rlm.metadata.values()
                )
            }
        )
        for row in receipt.documents.values():
            if used is not None and (row.workspace_id, row.source_id) not in used:
                continue
            origin = receipt.document_origins.get((row.workspace_id, row.source_id))
            if origin is None:
                continue
            asset, workspace, source, title = origin
            value = document_reference(row, asset_id=asset, source_id=source, title=title)
            sources[value.id] = value
        for read in receipt.native_reads:
            if read.domain == "knowledge" and read.tenant_id == tenant_id:
                reads.append(read)
                continue
            for source in read.source_ids:
                origin = receipt.document_origins.get((read.workspace_id, source))
                if origin is not None and read.domain == "canon" and read.tenant_id == tenant_id:
                    reads.append(
                        replace(read, domain="documents", entity_id=origin[0], workspace_id=origin[1])
                    )
    failure_type = (
        NativeEvidenceDenied if isinstance(error, ForbiddenException) else NativeEvidenceUnavailable
    )
    budget_failure = getattr(error, "code", None) == "EVIDENCE_BUDGET_EXCEEDED"
    failure = failure_type(
        "Narrow the selected sources or question; the native evidence budget is exhausted"
        if budget_failure
        else "Native evidence could not be authorized or completed",
        code="EVIDENCE_BUDGET_EXCEEDED" if budget_failure else "EVIDENCE_UNAVAILABLE",
    )
    failure.capture = CapturedEvidence(
        {},
        tuple(sources.values()),
        False,
        tuple(reads),
        canonical_dataset_attempts(receipt, chain, binding) if chain is not None else receipt.sql_attempts,
        tuple(receipt.rlm_tools) if receipt.rlm_tools is not None else None,
    )
    failure.denied = isinstance(error, ForbiddenException)
    return failure


def checked_capture(receipt, *arguments):
    capture = CapturedEvidence(
        *arguments,
        rlm_tools=(tuple(receipt.rlm_tools) if receipt.rlm_tools is not None else None),
        query_results=tuple(receipt.query_results),
    )
    receipt.budget.envelope(capture)
    return capture


def unavailable():
    return AccessDenied("Native evidence does not match this authorized read", code="EVIDENCE_UNAVAILABLE")


def reference(**values):
    identifier = sha256(
        json.dumps(values, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
    return SourceReference(id=identifier, **values)


def document_reference(observed, *, asset_id, source_id, title):
    values: dict = dict(
        asset_id=asset_id,
        source_id=source_id,
        title=title,
        kind="document",
        used_revision="chunk-sha256:" + observed.digest,
        chunk_id=observed.chunk_id,
        quote=observed.quote,
        page=observed.page,
        section=observed.section,
    )
    if observed.source_part_id:
        values.update(
            source_version_id=observed.source_version_id,
            extraction_id=observed.extraction_id,
            source_part_id=observed.source_part_id,
            source_part_sha256=observed.source_part_sha256,
            recorded_page=observed.recorded_page,
            page_basis="recorded_loader",
            chunk_id=None,
            used_revision="source-part-sha256:" + (observed.source_part_sha256 or ""),
            page=None,
        )
    return reference(**values)


@service(name="knowledge.evidence_capture")
class NativeKnowledgeEvidence:
    def __init__(self, knowledge: KnowledgeFacade, datasources: DataSourceRegistry):
        self.knowledge, self.datasources = knowledge, datasources

    async def entry(self, subject, tenant_id, asset_id, kind):
        chain = await self.knowledge._chain(subject, tenant_id, asset_id)
        if len(chain) < 2 or chain[0].kind != kind:
            raise unavailable()
        binding = await self.knowledge.binding(
            tenant_id, asset_id, "canon" if kind == "document" else "structured", entry=chain[0]
        )
        return chain, binding

    async def search(
        self, subject, tenant_id, *, _limits: NativeCaptureLimits | None = None, **arguments
    ) -> CapturedEvidence:
        receipt = NativeEvidenceReceipt(subject, tenant_id, limits=_limits, operation="search")
        try:
            receipt.budget.check(receipt, minimum_reads=1, minimum_sources=1)
            data = await self.knowledge.search(subject, tenant_id, **arguments, _capture=receipt)
            from koinon.knowledge.rlm_provenance import execution_views

            complete = receipt.complete and receipt.observed
            admitted = {}
            for hit in data.get("hits", []):
                known = receipt.knowledge_sources.get(str(hit.get("id")))
                if known is not None:
                    chain = await self.knowledge._chain(
                        subject, tenant_id, hit["asset_id"], "knowledge:search"
                    )
                    if (
                        chain[0].kind != "knowledge_item"
                        or known.asset_id != chain[0].id
                        or hit.get("source_id") is not None
                        or hit.get("text") != known.quote
                        or hit.get("knowledge_version_id") != known.knowledge_version_id
                    ):
                        raise unavailable()
                    continue
                observed = receipt.documents.get(str(hit.get("id")))
                if observed is None:
                    complete = False
                    continue
                chain, binding = await self.entry(subject, tenant_id, hit["asset_id"], "document")
                if (
                    observed.workspace_id != binding.native_workspace_id
                    or observed.source_id != binding.native_id
                    or hit.get("source_id") != chain[1].id
                    or not isinstance(hit.get("text"), str)
                    or sha256(hit["text"].encode()).hexdigest() != observed.digest
                ):
                    raise unavailable()
                admitted[(observed.workspace_id, observed.source_id)] = (chain, binding)
            sources = {source.id: source for source in receipt.knowledge_sources.values()}
            for observed in receipt.documents.values():
                key = (observed.workspace_id, observed.source_id)
                if key not in admitted:
                    canonical_id = receipt.canonical_documents.get(key)
                    if canonical_id is None:
                        complete = False
                        continue
                    admitted[key] = await self.entry(subject, tenant_id, canonical_id, "document")
                chain, binding = admitted[key]
                if (
                    observed.workspace_id != binding.native_workspace_id
                    or observed.source_id != binding.native_id
                ):
                    raise unavailable()
                value = document_reference(
                    observed, asset_id=chain[0].id, source_id=chain[1].id, title=chain[0].name[:255]
                )
                sources[value.id] = value
            reads = []
            for read in receipt.native_reads:
                if read.domain == "knowledge":
                    matches = [
                        source
                        for source in receipt.knowledge_sources.values()
                        if source.asset_id == read.entity_id
                        and source.knowledge_version_id == read.knowledge_version_id
                        and source.knowledge_version == read.knowledge_version
                    ]
                    if read.stage.startswith("rlm."):
                        from koinon.knowledge.curated.rlm_verification import metadata_for_read

                        metadata_for_read(receipt, read)
                    elif read.tenant_id != tenant_id or not matches:
                        raise unavailable()
                    chain = await self.knowledge._chain(
                        subject, tenant_id, read.entity_id, "knowledge:search"
                    )
                    if chain[0].kind != "knowledge_item" or chain[0].workspace_id != read.workspace_id:
                        raise unavailable()
                    reads.append(read)
                    continue
                if read.domain != "canon" or read.tenant_id != tenant_id:
                    raise unavailable()
                for native_id in read.source_ids:
                    key = (read.workspace_id, native_id)
                    bound = admitted.get(key)
                    if bound is None:
                        canonical_id = receipt.canonical_documents.get(key)
                        if canonical_id is None:
                            raise unavailable()
                        bound = await self.entry(subject, tenant_id, canonical_id, "document")
                        if (bound[1].native_workspace_id, bound[1].native_id) != key:
                            raise unavailable()
                        admitted[key] = bound
                    chain, _ = bound
                    reads.append(
                        replace(
                            read,
                            domain="documents",
                            entity_id=chain[0].id,
                            workspace_id=chain[0].workspace_id,
                        )
                    )
            part_sources = [source for source in sources.values() if source.source_part_id is not None]
            if part_sources:
                from koinon.knowledge.document_part_receipts import verify_part_sources

                bindings = {chain[0].id: binding for chain, binding in admitted.values()}
                verified = await verify_part_sources(
                    self.knowledge.domains,
                    subject,
                    tenant_id,
                    [(source, bindings[source.asset_id]) for source in part_sources],
                )
                sources.update(verified)
            if arguments.get("answer", False):
                from koinon.knowledge.rlm_provenance import verified_rlm_answer

                rlm = any(row.stage.startswith("rlm.") for row in receipt.native_reads)
                complete = complete and (
                    verified_rlm_answer(receipt, data, admitted)
                    if rlm
                    else receipt.verified_document_answer(data)
                )
                if rlm:
                    used = execution_views(receipt)
                    used_assets = {chain[0].id for key, (chain, _) in admitted.items() if key in used}
                    from koinon.knowledge.curated.rlm_receipts import (
                        execution_views as knowledge_execution_views,
                    )

                    knowledge_used = knowledge_execution_views(receipt)
                    knowledge_assets = {item for _, item in knowledge_used}
                    sources = {
                        identifier: source
                        for identifier, source in sources.items()
                        if source.kind == "document"
                        and source.asset_id in used_assets
                        or source.kind == "knowledge_version"
                        and source.asset_id in knowledge_assets
                    }
                    data = {
                        **data,
                        "hits": [
                            hit
                            for hit in data.get("hits", [])
                            if str(hit.get("id")) in receipt.knowledge_sources
                            and receipt.knowledge_sources[str(hit["id"])].asset_id in knowledge_assets
                            or str(hit.get("id")) in receipt.documents
                            and receipt.document_origins.get(
                                (
                                    receipt.documents[str(hit["id"])].workspace_id,
                                    receipt.documents[str(hit["id"])].source_id,
                                ),
                                (None,),
                            )[0]
                            in used_assets
                        ],
                    }
            for authorize in receipt.curated_rlm.authorizers:
                await authorize()
            if receipt.authorize_knowledge is not None:
                await receipt.authorize_knowledge()
            return checked_capture(
                receipt,
                data,
                tuple(sources.values()),
                bool(complete),
                tuple(reads),
                receipt.sql_attempts,
            )
        except CancelledError as error:
            if receipt.document_origins or receipt.knowledge_sources:
                error.__dict__["native_evidence_capture"] = failed_receipt(error, receipt, tenant_id).capture
            raise
        except Exception as error:
            if isinstance(error, NativeCaptureBudgetExceeded) or (
                (receipt.document_origins or receipt.knowledge_sources)
                and (receipt.documents or receipt.native_reads)
            ):
                failure = failed_receipt(error, receipt, tenant_id)
                if getattr(error, "code", None) == "RLM_DOCUMENT_VIEWS_REQUIRED":
                    failure.code = "RLM_DOCUMENT_VIEWS_REQUIRED"
                raise failure from None
            raise
        finally:
            receipt.closed = True

    async def query(
        self, subject, tenant_id, *, _limits: NativeCaptureLimits | None = None, **arguments
    ) -> CapturedEvidence:
        return await self.dataset("query", subject, tenant_id, arguments, _limits)

    async def schema(
        self, subject, tenant_id, dataset_id, *, _limits: NativeCaptureLimits | None = None
    ) -> CapturedEvidence:
        return await self.dataset("schema", subject, tenant_id, {"dataset_id": dataset_id}, _limits)

    async def dataset(self, operation, subject, tenant_id, arguments, limits=None):
        receipt = NativeEvidenceReceipt(subject, tenant_id, limits=limits, operation=operation)
        chain = binding = None
        try:
            chain, binding = await self.entry(subject, tenant_id, arguments["dataset_id"], "dataset")
            receipt.budget.check(
                receipt,
                minimum_reads=1 if operation == "query" and arguments.get("sql") is None else 0,
                minimum_attempts=1 if operation == "query" else 0,
                minimum_sources=2 if operation == "query" else 1,
            )
            method = getattr(self.knowledge, operation)
            data = await method(subject, tenant_id, **arguments, _capture=receipt)
            if not receipt.snapshots:
                return checked_capture(
                    receipt,
                    data,
                    (),
                    False,
                    canonical_dataset_reads(receipt, tenant_id, chain, binding),
                    canonical_dataset_attempts(receipt, chain, binding),
                )
            valid = await self.validate_snapshots(subject, tenant_id, binding, receipt.snapshots)
            complete = receipt.complete and receipt.observed and valid
            if operation == "query":
                observed_pins = {row.table_name: row.snapshot_id for row in receipt.snapshots}
                if data.get("snapshot_pins") != observed_pins or any(
                    row.query_id != str(data.get("query_id")) for row in receipt.snapshots
                ):
                    raise unavailable()
            else:
                reported = sorted(str(row.get("snapshot_id")) for row in data.get("tables", []))
                if reported != sorted(row.snapshot_id for row in receipt.snapshots):
                    complete = False
            all_snapshots = list(
                dict.fromkeys(receipt.snapshots + receipt.model_snapshots + receipt.resolved_snapshots)
            )
            if not await self.validate_snapshots(subject, tenant_id, binding, all_snapshots):
                complete = False
            sources = {}
            for observed in all_snapshots:
                value = reference(
                    asset_id=chain[0].id,
                    source_id=chain[1].id,
                    title=chain[0].name,
                    kind="dataset",
                    used_revision=observed.snapshot_id,
                    snapshot_id=observed.snapshot_id,
                    query_id=observed.query_id,
                )
                sources[value.id] = value
            await self.knowledge._chain(subject, tenant_id, arguments["dataset_id"])
            reads = canonical_dataset_reads(receipt, tenant_id, chain, binding)
            return checked_capture(
                receipt,
                data,
                tuple(sources.values()),
                bool(complete and len(all_snapshots) <= 500),
                tuple(reads),
                canonical_dataset_attempts(receipt, chain, binding),
            )
        except CancelledError as error:
            if chain is not None and binding is not None:
                capture = failed_receipt(error, receipt, tenant_id, chain, binding).capture
                error.__dict__["native_evidence_capture"] = capture
            raise
        except Exception as error:
            if isinstance(error, NativeCaptureBudgetExceeded) or (
                chain is not None and binding is not None and (receipt.native_reads or receipt.sql_attempts)
            ):
                raise failed_receipt(error, receipt, tenant_id, chain, binding) from None
            raise
        finally:
            receipt.closed = True

    async def validate_snapshots(self, subject, tenant_id, binding, observations):
        from flyquery.models.entities.queries import Query
        from flyquery.models.entities.schema import SchemaSnapshot
        from flyquery.models.entities.table import Table

        if len(observations) > 500:
            return False
        if any(
            row.dataset_id != binding.native_id or row.workspace_id != binding.native_workspace_id
            for row in observations
        ):
            raise unavailable()
        try:
            dataset, workspace = UUID(binding.native_id), UUID(binding.native_workspace_id)
            identifiers = {UUID(row.snapshot_id) for row in observations}
            queries = {UUID(row.query_id) for row in observations if row.query_id}
        except (TypeError, ValueError) as error:
            raise unavailable() from error
        with native_scope("structured", tenant_id, binding.native_workspace_id, subject):
            async with infrastructure_unit(self.datasources.get("structured"), read_only=True) as session:
                rows = (
                    await session.execute(
                        select(SchemaSnapshot, Table)
                        .join(Table, Table.id == SchemaSnapshot.table_id)
                        .where(
                            SchemaSnapshot.id.in_(identifiers),
                            SchemaSnapshot.tenant_id == tenant_id,
                            SchemaSnapshot.workspace_id == workspace,
                            SchemaSnapshot.dataset_id == dataset,
                            Table.tenant_id == tenant_id,
                            Table.workspace_id == workspace,
                            Table.dataset_id == dataset,
                        )
                    )
                ).all()
                by_id = {str(snapshot.id): (snapshot, table) for snapshot, table in rows}
                if len(by_id) != len(identifiers):
                    raise unavailable()
                if queries:
                    found = list(
                        await session.scalars(
                            select(Query.id).where(
                                Query.id.in_(queries),
                                Query.tenant_id == tenant_id,
                                Query.workspace_id == workspace,
                                Query.dataset_id == dataset,
                                Query.execution_status.in_(["OK", "REFINED_OK"]),
                            )
                        )
                    )
                    if set(found) != queries:
                        raise unavailable()
                for observation in observations:
                    snapshot, table = by_id[observation.snapshot_id]
                    if observation.table_id is not None and str(table.id) != observation.table_id:
                        raise unavailable()
                    if snapshot.status != "READY":
                        return False
        return True
