# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Read-only exact published views with current primary/native acknowledgement and ACLs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flycanon.interfaces.dtos.knowledge_corpus import KnowledgeVersionMeta, WholeKnowledgeRead
from pyfly.container import service
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.data.transaction import Isolation, Propagation
from pyfly.kernel import ConflictException

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.curated.authority import CuratedAuthority
from koinon.knowledge.curated.corpus_dtos import ServingVersion
from koinon.knowledge.curated.corpus_mappers import version_meta, whole_view
from koinon.knowledge.curated.dtos import KnowledgeItemView
from koinon.knowledge.curated.reads import CuratedKnowledgeReads
from koinon.knowledge.curated.release import CuratedReleaseFence
from koinon.knowledge.curated.release_dtos import CuratedReleaseStamp
from koinon.knowledge.curated.whole_repository import CuratedWholePartRepository
from koinon.security.authority import PRIMARY_POLICY_UNIT

if TYPE_CHECKING:
    from koinon.catalog.entities import CatalogEntry
    from koinon.knowledge.curated.entities import CuratedCatalogState


def changed() -> ConflictException:
    return ConflictException(
        "The admitted published knowledge version changed", code="KNOWLEDGE_VERSION_CONFLICT"
    )


@service(name="knowledge.curated.whole_reader")
class CuratedWholeVersionReader:
    def __init__(
        self,
        reads: CuratedKnowledgeReads,
        parts: CuratedWholePartRepository,
        authority: CuratedAuthority,
        release: CuratedReleaseFence,
    ):
        self.reads, self.parts, self.authority, self.release = reads, parts, authority, release

    @staticmethod
    def _ack(
        entry: CatalogEntry,
        state: CuratedCatalogState,
        tenant_id: str,
        native_workspace_id: str,
        selected: ServingVersion,
        operation_id: str | None = None,
    ) -> None:
        if (
            entry.kind != "knowledge_item"
            or getattr(entry, "status", "active") == "archived"
            or (
                entry.id,
                entry.workspace_id,
                state.tenant_id,
                state.workspace_id,
                state.item_id,
                state.native_item_id,
                state.native_workspace_id,
                state.serving_version_id,
                state.serving_version,
            )
            != (
                selected.item_id,
                selected.workspace_id,
                tenant_id,
                selected.workspace_id,
                selected.item_id,
                selected.native_item_id,
                native_workspace_id,
                selected.version_id,
                selected.version,
            )
            or operation_id is not None
            and state.serving_operation_id != operation_id
        ):
            raise changed()

    async def _current(
        self, subject: str, tenant_id: str, native_workspace_id: str, selected: ServingVersion
    ) -> tuple[KnowledgeItemView, KnowledgeVersionMeta]:
        entry, state = await self.reads.scope(subject, tenant_id, selected.item_id)
        self._ack(entry, state, tenant_id, native_workspace_id, selected)
        await self.authority.catalog.authorize(subject, tenant_id, "knowledge:search", entry.workspace_id)
        value = await self.reads.version(subject, tenant_id, selected.item_id, selected.version)
        meta = version_meta(value, selected, tenant_id=tenant_id, native_workspace_id=native_workspace_id)
        entry, state = await self.reads.scope(subject, tenant_id, selected.item_id)
        self._ack(entry, state, tenant_id, native_workspace_id, selected, meta.operation_id)
        await self.authority.catalog.authorize(subject, tenant_id, "knowledge:search", entry.workspace_id)
        return value, meta

    async def pin(
        self, subject: str, tenant_id: str, native_workspace_id: str, selected: ServingVersion
    ) -> KnowledgeVersionMeta:
        _, meta = await self._current(subject, tenant_id, native_workspace_id, selected)
        await self.parts.assert_serving(meta, subject=subject)
        _, following = await self._current(subject, tenant_id, native_workspace_id, selected)
        if following != meta:
            raise changed()
        return meta

    async def authorize(self, subject: str, tenant_id: str, metas: tuple[KnowledgeVersionMeta, ...]) -> None:
        item_ids = tuple(meta.item_id for meta in metas)
        stamp = await self.release.observe(subject, tenant_id, item_ids)
        policy = await self._authorize_current(subject, tenant_id, metas)
        if policy != stamp:
            raise AccessDenied(
                "Knowledge authority changed during this read; retry in the current scope",
                code="KNOWLEDGE_AUTHORITY_CHANGED",
            )
        await self.release.require_unchanged(subject, tenant_id, item_ids, stamp)

    @transactional(
        datasource="primary",
        name=PRIMARY_POLICY_UNIT,
        propagation=Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE,
        read_only=True,
        read_from_primary=True,
    )
    async def _authorize_current(
        self, subject: str, tenant_id: str, metas: tuple[KnowledgeVersionMeta, ...]
    ) -> CuratedReleaseStamp:
        for meta in metas:
            selected = ServingVersion(
                meta.item_id,
                meta.canonical_workspace_id,
                meta.native_item_id,
                meta.workspace_id,
                meta.version_id,
                meta.version,
            )
            following = await self.pin(subject, tenant_id, meta.workspace_id, selected)
            if following != meta:
                raise changed()
        return await self.release.observe_bound(subject, tenant_id, tuple(meta.item_id for meta in metas))

    async def read(self, subject: str, tenant_id: str, meta: KnowledgeVersionMeta) -> WholeKnowledgeRead:
        selected = ServingVersion(
            meta.item_id,
            meta.canonical_workspace_id,
            meta.native_item_id,
            meta.workspace_id,
            meta.version_id,
            meta.version,
        )
        value, current = await self._current(subject, tenant_id, meta.workspace_id, selected)
        if current != meta:
            raise changed()
        projection = await self.parts.read(meta, subject=subject)
        result = whole_view(meta, value.selected_version.content.body, projection.parts, projection.database)
        await self.authorize(subject, tenant_id, (meta,))
        return result
