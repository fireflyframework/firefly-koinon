# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Admit immutable serving versions and coordinate native read-only repositories."""

from flycanon.interfaces.knowledge_corpus import CuratedRlmReader
from pyfly.container import service
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.data.transaction import Isolation, Propagation, infrastructure_unit
from pyfly.kernel import InvalidRequestException

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.adapters import native_scope
from koinon.knowledge.curated.authority import CuratedAuthority
from koinon.knowledge.curated.body_repository import CuratedBodyProjectionRepository
from koinon.knowledge.curated.corpus_dtos import ServingVersion
from koinon.knowledge.curated.ports import CuratedCorpusPort
from koinon.knowledge.curated.query_context import database_context
from koinon.knowledge.curated.reads import CuratedKnowledgeReads
from koinon.knowledge.curated.release import CuratedReleaseFence
from koinon.knowledge.curated.rlm_binding import BoundCuratedRlmReader
from koinon.knowledge.curated.whole import CuratedWholeVersionReader
from koinon.security.authority import PRIMARY_POLICY_UNIT


@service(name="knowledge.curated.corpus")
class CuratedBodyCorpus(CuratedCorpusPort):
    def __init__(
        self,
        reads: CuratedKnowledgeReads,
        projections: CuratedBodyProjectionRepository,
        whole: CuratedWholeVersionReader,
        authority: CuratedAuthority,
        release: CuratedReleaseFence,
    ):
        self.reads, self.projections, self.whole, self.authority, self.release = (
            reads,
            projections,
            whole,
            authority,
            release,
        )

    async def admit(self, subject, tenant_id, item_ids):
        admitted = []
        for item_id in dict.fromkeys(item_ids):
            entry, state = await self.reads.scope(subject, tenant_id, item_id)
            await self.authority.catalog.authorize(subject, tenant_id, "knowledge:search", entry.workspace_id)
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
            await self.authority.catalog.authorize(subject, tenant_id, "knowledge:search", entry.workspace_id)
            if (
                state.native_item_id,
                state.native_workspace_id,
                state.serving_version_id,
                state.serving_version,
            ) != (selection.native_item_id, native_workspace_id, selection.version_id, selection.version):
                raise AccessDenied("The admitted serving version changed", code="KNOWLEDGE_VERSION_CONFLICT")
            value = await self.reads.version(subject, tenant_id, selection.item_id, selection.version)
            selected[selection.version_id] = selection, value.selected_version
        if not selected:
            return []
        with native_scope("canon", tenant_id, native_workspace_id, subject):
            async with infrastructure_unit(self.reads.native.datasource(), read_only=True) as session:
                hits = await self.ranked(session, tenant_id, native_workspace_id, selected, query, limit)
                database = await database_context(session)
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
        return await self.projections.ranked(session, tenant_id, workspace_id, selected, query, limit)

    async def rlm(
        self, subject: str, tenant_id: str, native_workspace_id: str, admitted: tuple[ServingVersion, ...]
    ) -> CuratedRlmReader:
        if len(admitted) > 128:
            raise InvalidRequestException("Narrow the curated corpus", code="INVALID_KNOWLEDGE_SEARCH")
        metas = tuple(
            [await self.whole.pin(subject, tenant_id, native_workspace_id, value) for value in admitted]
        )
        await self.whole.authorize(subject, tenant_id, metas)
        return BoundCuratedRlmReader(self.whole, subject, tenant_id, metas)
