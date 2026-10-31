# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Resolve current native provenance only after all canonical source ancestors are admitted."""

import json
from hashlib import sha256
from uuid import UUID

from pyfly.container import Provider, service
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit
from pyfly.kernel import PayloadTooLargeException, ServiceUnavailableException
from sqlalchemy import select

from koinon.catalog.errors import AccessDenied
from koinon.evidence.ports import SourceResolverPort
from koinon.knowledge.adapters import NativeDomains, native_scope
from koinon.knowledge.curated.reads import CuratedKnowledgeReads
from koinon.knowledge.service import KnowledgeFacade


def unavailable():
    return AccessDenied("This source is unavailable in the selected context", code="EVIDENCE_UNAVAILABLE")


@service(name="knowledge.evidence_sources")
class NativeSourceResolver(SourceResolverPort):
    def __init__(
        self,
        knowledge: KnowledgeFacade,
        domains: NativeDomains,
        datasources: DataSourceRegistry,
        curated: Provider[CuratedKnowledgeReads | None] | None = None,
    ):
        self.knowledge, self.domains, self.datasources = knowledge, domains, datasources
        self.curated = curated

    async def resolve_for_write(self, subject, tenant_id, sources):
        return await self.resolve(subject, tenant_id, sources, _lock_parts=True)

    async def resolve(self, subject, tenant_id, sources, *, _lock_parts=False):
        if len(sources) > 500:
            raise PayloadTooLargeException("Select fewer source references", code="EVIDENCE_TOO_LARGE")
        admitted = []
        for reference in sources:
            chain = await self.knowledge._chain(subject, tenant_id, reference.asset_id)
            if reference.kind == "knowledge_version":
                if chain[0].kind != "knowledge_item":
                    raise unavailable()
                admitted.append((reference, chain, None))
                continue
            if (
                chain[0].kind != reference.kind
                or reference.kind not in {"document", "dataset"}
                or len(chain) < 2
                or reference.source_id is not None
                and reference.source_id != chain[1].id
            ):
                raise unavailable()
            domain = "canon" if reference.kind == "document" else "structured"
            binding = await self.knowledge.binding(tenant_id, reference.asset_id, domain, entry=chain[0])
            admitted.append((reference, chain, binding))
        from koinon.knowledge.document_part_receipts import verify_part_sources

        async def authorize_parts(values):
            for reference, binding in values:
                chain = await self.knowledge._chain(subject, tenant_id, reference.asset_id)
                current = await self.knowledge.binding(tenant_id, reference.asset_id, "canon", entry=chain[0])
                if (
                    chain[0].kind != "document"
                    or reference.source_id is not None
                    and reference.source_id != chain[1].id
                    or (current.native_id, current.native_workspace_id)
                    != (binding.native_id, binding.native_workspace_id)
                ):
                    raise unavailable()

        parts = await verify_part_sources(
            self.domains,
            subject,
            tenant_id,
            [
                (reference, binding)
                for reference, _, binding in admitted
                if reference.source_part_id is not None
            ],
            current=True,
            lock=_lock_parts,
            authorize=authorize_parts,
        )
        result = []
        for reference, _chain, binding in admitted:
            if binding is None:
                result.append(await self.knowledge_version(subject, tenant_id, reference))
                continue
            if reference.source_part_id is not None:
                result.append(parts[reference.id])
                continue
            if reference.kind == "document":
                resolved = await self.document(subject, tenant_id, reference, binding)
            else:
                resolved = await self.dataset(subject, tenant_id, reference, binding)
            result.append(reference.model_copy(update={
                "availability": resolved["availability"], "current_revision": resolved["current_revision"],
            }))
        for reference in sources:
            await self.knowledge._chain(subject, tenant_id, reference.asset_id)
        return tuple(result)

    async def knowledge_version(self, subject, tenant_id, reference):
        reader = self.curated.get() if self.curated is not None else None
        if reader is None:
            raise ServiceUnavailableException(
                "Committed knowledge provenance is unavailable", code="KNOWLEDGE_UNAVAILABLE"
            )
        used = (
            await reader.version(subject, tenant_id, reference.asset_id, reference.knowledge_version)
        ).selected_version
        if (
            used.version_id != reference.knowledge_version_id
            or "knowledge-content-sha256:" + used.content_sha256 != reference.used_revision
            or reference.quote is not None
            and reference.quote not in used.content.body
        ):
            raise unavailable()
        current = (await reader.version(subject, tenant_id, reference.asset_id)).selected_version
        return reference.model_copy(
            update={
                "availability": "available" if current.version_id == used.version_id else "changed",
                "current_revision": "knowledge-content-sha256:" + current.content_sha256,
            }
        )

    async def document(self, subject, tenant_id, reference, binding):
        if reference.source_part_id is not None:
            from koinon.knowledge.document_part_receipts import verify_part

            resolved = await verify_part(self.domains, subject, tenant_id, binding, reference, current=True)
            return {"availability": resolved.availability, "current_revision": resolved.current_revision}
        from flycanon.models.repositories import ChunkRepository, SourceRepository

        result = {
            "availability": "unverified",
            "current_revision": None,
            "quote": reference.quote,
            "page": reference.page,
            "section": reference.section,
        }
        with native_scope("canon", tenant_id, binding.native_workspace_id, subject):
            source = await self.domains._resolve(SourceRepository).get(
                binding.native_id, tenant_id=tenant_id, workspace_id=binding.native_workspace_id
            )
            if source is None:
                return result
            if (reference.used_revision or "").startswith("chunk-sha256:"):
                if not reference.chunk_id:
                    raise unavailable()
                chunks = await self.domains._resolve(ChunkRepository).get_many([reference.chunk_id])
                if not chunks:
                    return {
                        **result,
                        "availability": "changed",
                        "quote": reference.quote,
                        "page": reference.page,
                        "section": reference.section,
                    }
                if len(chunks) != 1:
                    raise unavailable()
                chunk = chunks[0]
                if (chunk.tenant_id, chunk.workspace_id, chunk.source_id) != (
                    tenant_id,
                    binding.native_workspace_id,
                    binding.native_id,
                ):
                    raise unavailable()
                current = "chunk-sha256:" + sha256(chunk.content.encode()).hexdigest()
                changed = current != reference.used_revision
                if not changed and reference.quote is not None and reference.quote not in chunk.content:
                    raise unavailable()
                return {
                    **result,
                    "current_revision": current,
                    "availability": "changed" if changed else "available",
                    "quote": reference.quote,
                    "page": reference.page,
                    "section": reference.section,
                }
            current = ((source.metadata_json or {}).get("_persisted_original") or {}).get(
                "sha256"
            ) or source.content_sha256
            result["current_revision"] = current
            changed = (
                reference.used_revision is not None
                and current is not None
                and reference.used_revision != current
            )
            result["availability"] = "changed" if changed else "unverified"
            if reference.chunk_id:
                chunks = await self.domains._resolve(ChunkRepository).get_many([reference.chunk_id])
                if len(chunks) != 1:
                    return result
                chunk = chunks[0]
                if (chunk.tenant_id, chunk.workspace_id, chunk.source_id) != (
                    tenant_id,
                    binding.native_workspace_id,
                    binding.native_id,
                ):
                    raise unavailable()
                if reference.quote is not None and reference.quote not in chunk.content:
                    return result
                result.update(
                    availability="changed" if changed else "available",
                )
            elif reference.quote is None and current is not None:
                result["availability"] = "changed" if changed else "available"
            return result

    async def dataset(self, subject, tenant_id, reference, binding):
        from flyquery.core.services.query.query_repository import QueryRepository
        from flyquery.models.entities.schema import SchemaSnapshot
        from flyquery.models.entities.table import Table

        if reference.chunk_id is not None:
            raise unavailable()
        try:
            dataset, workspace = UUID(binding.native_id), UUID(binding.native_workspace_id)
            snapshot = UUID(reference.snapshot_id) if reference.snapshot_id else None
            query_id = UUID(reference.query_id) if reference.query_id else None
        except ValueError as error:
            raise unavailable() from error
        with native_scope("structured", tenant_id, binding.native_workspace_id, subject):
            if query_id:
                query = await self.domains._resolve(QueryRepository).get_query(
                    query_id, tenant_id=tenant_id, workspace_id=workspace
                )
                if (
                    not query
                    or str(query.get("dataset_id")) != binding.native_id
                    or query.get("execution_status") not in {"OK", "REFINED_OK"}
                ):
                    raise unavailable()
            try:
                datasource = self.datasources.get("structured")
            except KeyError as error:
                raise ServiceUnavailableException(
                    "Enable the structured knowledge data source and its retained migrations",
                    code="DOMAIN_PREREQUISITE_REQUIRED",
                ) from error
            async with infrastructure_unit(datasource) as session:
                tables = list(
                    await session.scalars(
                        select(Table).where(
                            Table.tenant_id == tenant_id,
                            Table.workspace_id == workspace,
                            Table.dataset_id == dataset,
                            Table.is_active.is_(True),
                        )
                    )
                )
                current = sorted((str(row.id), str(row.current_snapshot_id)) for row in tables)
                revision = (
                    sha256(json.dumps(current, separators=(",", ":")).encode()).hexdigest()
                    if current
                    else None
                )
                availability = "available" if current and reference.quote is None else "unverified"
                if snapshot:
                    pinned = await session.scalar(
                        select(SchemaSnapshot).where(
                            SchemaSnapshot.id == snapshot,
                            SchemaSnapshot.tenant_id == tenant_id,
                            SchemaSnapshot.workspace_id == workspace,
                            SchemaSnapshot.dataset_id == dataset,
                        )
                    )
                    if pinned is None:
                        raise unavailable()
                    table = next((row for row in tables if row.id == pinned.table_id), None)
                    if table is None:
                        availability = "changed"
                    else:
                        revision = str(table.current_snapshot_id)
                        availability = (
                            "available"
                            if table.current_snapshot_id == snapshot and pinned.status == "READY"
                            else "changed"
                        )
                elif reference.used_revision is not None and revision != reference.used_revision:
                    availability = "changed" if revision else "unverified"
        return {
            "availability": availability,
            "current_revision": revision,
            "quote": None,
            "page": None,
            "section": None,
        }
