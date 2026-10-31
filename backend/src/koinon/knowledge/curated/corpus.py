# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Lexical native-version body projection constrained by exact primary acknowledgements."""

from dataclasses import dataclass
from hashlib import sha256

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.data.transaction import Isolation, Propagation, infrastructure_unit
from pyfly.kernel import InvalidRequestException
from sqlalchemy import func, literal_column, select, text

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.adapters import native_scope
from koinon.knowledge.capture_dtos import NativeDatabaseContext
from koinon.knowledge.curated.domain_entities import (
    CuratedCommitRow,
    CuratedEvidenceRow,
    CuratedHeadRow,
    CuratedVersionChunkRow,
)
from koinon.knowledge.curated.ports import CuratedCorpusPort
from koinon.knowledge.curated.reads import CuratedKnowledgeReads
from koinon.knowledge.curated.release import CuratedReleaseFence
from koinon.security.authority import PRIMARY_POLICY_UNIT


@dataclass(frozen=True)
class ServingVersion:
    item_id: str
    workspace_id: str
    native_item_id: str
    native_workspace_id: str
    version_id: str
    version: int


@service(name="knowledge.curated.corpus")
class CuratedBodyCorpus(CuratedCorpusPort):
    def __init__(self, reads: CuratedKnowledgeReads, release: CuratedReleaseFence):
        self.reads, self.release = reads, release

    async def admit(self, subject, tenant_id, item_ids):
        admitted = []
        for item_id in dict.fromkeys(item_ids):
            entry, state = await self.reads.scope(subject, tenant_id, item_id)
            await self.reads.authority.catalog.authorize(
                subject, tenant_id, "knowledge:search", entry.workspace_id
            )
            if state.serving_version is not None and state.serving_version_id:
                admitted.append(
                    ServingVersion(
                        item_id,
                        entry.workspace_id,
                        state.native_item_id,
                        state.native_workspace_id,
                        state.serving_version_id,
                        state.serving_version,
                    )
                )
        return tuple(admitted)

    async def search(self, subject, tenant_id, native_workspace_id, admitted, *, query, limit, _capture=None):
        admitted = tuple(admitted)
        if not query.strip() or not 1 <= limit <= 300 or len(admitted) > 128:
            raise InvalidRequestException("Narrow the curated search", code="INVALID_KNOWLEDGE_SEARCH")
        item_ids = tuple(selection.item_id for selection in admitted)
        stamp = await self.release.observe(subject, tenant_id, item_ids)
        selected = {}
        for selection in admitted:
            entry, state = await self.reads.scope(subject, tenant_id, selection.item_id)
            await self.reads.authority.catalog.authorize(
                subject, tenant_id, "knowledge:search", entry.workspace_id
            )
            if (
                state.native_item_id,
                state.native_workspace_id,
                state.serving_version_id,
                state.serving_version,
            ) != (selection.native_item_id, native_workspace_id, selection.version_id, selection.version):
                raise AccessDenied("The admitted serving version changed", code="KNOWLEDGE_VERSION_CONFLICT")
            value = await self.reads.version(subject, tenant_id, selection.item_id, selection.version)
            selected[selection.version_id] = (selection, value.selected_version)
        if not selected:
            return []
        with native_scope("canon", tenant_id, native_workspace_id, subject):
            async with infrastructure_unit(self.reads.native.datasource(), read_only=True) as session:
                hits = await self.ranked(session, tenant_id, native_workspace_id, selected, query, limit)
                if _capture is not None:
                    engine = session.get_bind().dialect.name
                    identity = (
                        (
                            await session.execute(
                                text(
                                    "SELECT current_database() AS database, current_catalog AS catalog, "
                                    "current_schema() AS schema"
                                )
                            )
                        )
                        .mappings()
                        .one()
                        if engine == "postgresql"
                        else {}
                    )
                    database = NativeDatabaseContext(
                        engine, identity.get("database"), identity.get("catalog"), identity.get("schema")
                    )
        policy = await self._validate_release(subject, tenant_id, native_workspace_id, admitted)
        if policy != stamp:
            raise AccessDenied(
                "Knowledge authority changed during this read; retry in the current scope",
                code="KNOWLEDGE_AUTHORITY_CHANGED",
            )
        await self.release.require_unchanged(subject, tenant_id, item_ids, stamp)
        if _capture is not None:
            for hit in hits:
                selection, version = selected[hit.metadata["knowledge_version_id"]]
                _capture.knowledge_read(
                    tenant_id,
                    native_workspace_id,
                    subject,
                    selection.workspace_id,
                    hit,
                    version.content_sha256,
                    database,
                )
        return hits

    @transactional(
        datasource="primary",
        name=PRIMARY_POLICY_UNIT,
        propagation=Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE,
        read_only=True,
        read_from_primary=True,
    )
    async def _validate_release(self, subject, tenant_id, native_workspace_id, admitted):
        # The native query can yield while access, bindings, or the serving head change.
        for selection in admitted:
            expected_workspace = (
                selection.native_workspace_id if native_workspace_id is None else native_workspace_id
            )
            current = await self.reads.version(subject, tenant_id, selection.item_id, selection.version)
            entry, state = await self.reads.scope(subject, tenant_id, selection.item_id)
            await self.reads.authority.catalog.authorize(
                subject, tenant_id, "knowledge:search", entry.workspace_id
            )
            if (
                entry.workspace_id,
                state.native_item_id,
                state.native_workspace_id,
                state.serving_version_id,
                state.serving_version,
            ) != (
                selection.workspace_id,
                selection.native_item_id,
                expected_workspace,
                selection.version_id,
                selection.version,
            ) or (
                selection.native_workspace_id != expected_workspace
                or current.selected_version.version_id != selection.version_id
                or current.selected_version.version != selection.version
                or not current.selected_version.serving
                or current.selected_version.publication != "published"
            ):
                raise AccessDenied("The admitted serving version changed", code="KNOWLEDGE_VERSION_CONFLICT")
        return await self.release.observe_bound(
            subject, tenant_id, tuple(selection.item_id for selection in admitted)
        )

    async def authorize_release(self, subject, tenant_id, admitted) -> None:
        admitted = tuple(admitted)
        item_ids = tuple(selection.item_id for selection in admitted)
        stamp = await self.release.observe(subject, tenant_id, item_ids)
        policy = await self._validate_release(subject, tenant_id, None, admitted)
        if policy != stamp:
            raise AccessDenied(
                "Knowledge authority changed during this read; retry in the current scope",
                code="KNOWLEDGE_AUTHORITY_CHANGED",
            )
        await self.release.require_unchanged(subject, tenant_id, item_ids, stamp)

    async def ranked(self, session, tenant_id, workspace_id, selected, query, limit):
        from flycanon.core.services.retrieval.retrieval_service import Hit
        from flycanon.models.entities.knowledge_item import KnowledgeItemRow
        from flycanon.models.entities.knowledge_version import KnowledgeVersionRow

        chunk, version, head, evidence, commit = (
            CuratedVersionChunkRow,
            KnowledgeVersionRow,
            CuratedHeadRow,
            CuratedEvidenceRow,
            CuratedCommitRow,
        )
        statement = (
            select(chunk, version)
            .join(version, version.id == chunk.native_version_id)
            .join(
                head,
                (head.native_item_id == version.knowledge_item_id)
                & (head.serving_version == version.version),
            )
            .join(KnowledgeItemRow, KnowledgeItemRow.id == head.native_item_id)
            .join(evidence, (evidence.native_version_id == version.id) & (evidence.ordinal == 1))
            .join(commit, commit.operation_id == evidence.operation_id)
            .where(
                chunk.tenant_id == tenant_id,
                chunk.workspace_id == workspace_id,
                version.tenant_id == tenant_id,
                version.workspace_id == workspace_id,
                head.tenant_id == tenant_id,
                head.workspace_id == workspace_id,
                evidence.tenant_id == tenant_id,
                evidence.workspace_id == workspace_id,
                commit.tenant_id == tenant_id,
                commit.workspace_id == workspace_id,
                KnowledgeItemRow.tenant_id == tenant_id,
                KnowledgeItemRow.workspace_id == workspace_id,
                KnowledgeItemRow.status != "retired",
                version.status == "published",
                commit.receipt_json.is_not(None),
                chunk.native_version_id.in_(tuple(selected)),
            )
        )
        if session.get_bind().dialect.name == "postgresql":
            vector = literal_column("canon_knowledge_version_chunks.tsv")
            parsed = func.plainto_tsquery("simple", query)
            statement = statement.where(vector.op("@@")(parsed)).order_by(
                func.ts_rank_cd(vector, parsed).desc(), chunk.id
            )
        else:
            statement = statement.where(
                func.lower(chunk.content).contains(query.lower(), autoescape=True)
            ).order_by(chunk.id)
        rows = (await session.execute(statement.limit(limit))).all()
        hits = []
        for ordinal, (part, native_version) in enumerate(rows, 1):
            selection, receipt = selected[part.native_version_id]
            body = receipt.content
            if (
                part.canonical_item_id != selection.item_id
                or native_version.knowledge_item_id != selection.native_item_id
                or part.content != body.body[part.char_start : part.char_end]
                or part.sha256 != sha256(part.content.encode()).hexdigest()
            ):
                raise AccessDenied(
                    "Version body projection failed integrity validation", code="KNOWLEDGE_PROJECTION_INVALID"
                )
            hits.append(
                Hit(
                    chunk_id=part.id,
                    source_id=selection.native_item_id,
                    knowledge_item_id=selection.native_item_id,
                    knowledge_version=selection.version,
                    content=part.content,
                    score=1 / (60 + ordinal),
                    bm25_rank=None,
                    vector_rank=None,
                    metadata={
                        "source_kind": "knowledge_version",
                        "source_title": body.title,
                        "knowledge_version_id": selection.version_id,
                        "knowledge_content_sha256": receipt.content_sha256,
                        "canonical_knowledge_item_id": selection.item_id,
                        "_knowledge_status": "published",
                        "_knowledge_domain": body.domain,
                        "_knowledge_tags": ",".join(body.tags),
                    },
                )
            )
        return hits
