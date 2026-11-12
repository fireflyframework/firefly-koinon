# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Identity-only native lineage reads, closed before remote source authorization."""

from types import SimpleNamespace
from uuid import UUID

from pyfly.container import service
from pyfly.data.transaction import infrastructure_unit
from sqlalchemy import func, select

from koinon.integrations.content_sources.errors import SourceError


@service(name="content_sources.read_native")
class SourceReadNative:
    async def curated_version(self, actor, tenant, state, version):
        from flycanon.models.entities.knowledge_version import KnowledgeVersionRow

        from koinon.knowledge.adapters import native_scope

        with native_scope("canon", tenant, state.native_workspace_id, actor):
            async with infrastructure_unit("canon", read_only=True) as session:
                identifier = await session.scalar(
                    select(KnowledgeVersionRow.id).where(
                        KnowledgeVersionRow.tenant_id == tenant,
                        KnowledgeVersionRow.workspace_id == state.native_workspace_id,
                        KnowledgeVersionRow.knowledge_item_id == state.native_item_id,
                        KnowledgeVersionRow.version == version,
                    )
                )
        if identifier is None:
            raise SourceError("access_denied")
        return identifier

    async def document_extraction(self, actor, tenant, pin, ingestion):
        from flycanon.models.entities.source_lineage import source_extractions, source_parts

        from koinon.knowledge.adapters import native_scope

        def scoped(table):
            return (
                table.c.tenant_id == tenant,
                table.c.workspace_id == pin.native_workspace_id,
                table.c.source_id == pin.native_source_id,
            )

        with native_scope("canon", tenant, pin.native_workspace_id, actor):
            async with infrastructure_unit("canon", read_only=True) as session:
                extraction = source_extractions
                rows = (
                    (
                        await session.execute(
                            select(
                                extraction.c.id,
                                extraction.c.version_id,
                                extraction.c.purpose,
                                extraction.c.normalized_artifact_id,
                                extraction.c.projection,
                            ).where(*scoped(extraction), extraction.c.id.in_({pin.extraction_id, ingestion}))
                        )
                    )
                    .mappings()
                    .all()
                )
                values = {row["id"]: row for row in rows}
                initial, selected = values.get(ingestion), values.get(pin.extraction_id)
                if (
                    initial is None
                    or selected is None
                    or initial["purpose"] != "ingestion"
                    or any(row["version_id"] != pin.version_id for row in (initial, selected))
                ):
                    raise SourceError("access_denied")
                if pin.extraction_id != ingestion and (
                    selected["purpose"] != "whole_document_read"
                    or selected["projection"].get("input_extraction_id") != ingestion
                    or selected["normalized_artifact_id"] != initial["normalized_artifact_id"]
                ):
                    raise SourceError("access_denied")
                if (
                    pin.part_id
                    and await session.scalar(
                        select(source_parts.c.id).where(
                            *scoped(source_parts),
                            source_parts.c.id == pin.part_id,
                            source_parts.c.extraction_id == pin.extraction_id,
                        )
                    )
                    is None
                ):
                    raise SourceError("access_denied")

    async def query_snapshots(self, actor, tenant, binding, query_id):
        from flyquery.models.entities.queries import Query

        from koinon.knowledge.adapters import native_scope

        try:
            identifier, workspace, dataset = (
                UUID(query_id),
                UUID(binding.native_workspace_id),
                UUID(binding.native_id),
            )
        except (ValueError, TypeError):
            raise SourceError("access_denied") from None
        with native_scope("structured", tenant, binding.native_workspace_id, actor):
            async with infrastructure_unit("structured", read_only=True) as session:
                pins = await session.scalar(
                    select(Query.table_id_snapshot_pins_json).where(
                        Query.id == identifier,
                        Query.tenant_id == tenant,
                        Query.workspace_id == workspace,
                        Query.dataset_id == dataset,
                        Query.execution_status.in_(("OK", "REFINED_OK")),
                    )
                )
        if not isinstance(pins, dict) or not pins or len(pins) > 500:
            raise SourceError("unavailable")
        return frozenset(str(value) for value in pins.values())

    async def terminal_query_manifest(self, actor, tenant, binding, query_id):
        """Project terminal display authority separately from successful source reuse."""
        from flyquery.models.entities.queries import Query

        from koinon.knowledge.adapters import native_scope

        try:
            identifier = UUID(query_id)
            workspace, dataset = UUID(binding.native_workspace_id), UUID(binding.native_id)
        except (TypeError, ValueError):
            raise SourceError("access_denied") from None
        with native_scope("structured", tenant, binding.native_workspace_id, actor):
            async with infrastructure_unit("structured", read_only=True) as session:
                row = (
                    (
                        await session.execute(
                            select(
                                Query.id.label("query_id"),
                                Query.execution_status,
                                Query.table_id_snapshot_pins_json.label("source_manifest"),
                                func.public.koinon_json_sha256(Query.table_id_snapshot_pins_json).label(
                                    "manifest_sha256"
                                ),
                            ).where(
                                Query.id == identifier,
                                Query.tenant_id == tenant,
                                Query.workspace_id == workspace,
                                Query.dataset_id == dataset,
                                Query.finalised_at.is_not(None),
                                Query.execution_status.in_(
                                    ("OK", "REFINED_OK", "FAILED", "REJECTED_BY_FIREWALL")
                                ),
                            )
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
        if row is None or not isinstance(row["source_manifest"], dict) or len(row["source_manifest"]) > 500:
            raise SourceError("unavailable")
        try:
            if any(
                str(UUID(key)) != key or str(UUID(pin)) != pin for key, pin in row["source_manifest"].items()
            ):
                raise ValueError("Noncanonical manifest")
        except (TypeError, ValueError, AttributeError):
            raise SourceError("unavailable") from None
        return SimpleNamespace(**dict(row))

    async def curated_sources(self, actor, tenant, workspace, item, version):
        from koinon.knowledge.adapters import native_scope
        from koinon.knowledge.curated.domain_entities import CuratedCommitRow, CuratedEvidenceRow

        fields = (
            "id",
            "asset_id",
            "kind",
            "source_version_id",
            "extraction_id",
            "source_part_id",
            "snapshot_id",
            "query_id",
            "knowledge_version_id",
        )
        row = CuratedEvidenceRow
        with native_scope("canon", tenant, workspace, actor):
            async with infrastructure_unit("canon", read_only=True) as session:
                values = (
                    (
                        await session.execute(
                            select(
                                *(
                                    row.evidence_json["source"][name].as_string().label(name)
                                    for name in fields
                                )
                            )
                            .join(CuratedCommitRow, CuratedCommitRow.operation_id == row.operation_id)
                            .where(
                                row.tenant_id == tenant,
                                row.workspace_id == workspace,
                                CuratedCommitRow.tenant_id == tenant,
                                CuratedCommitRow.canonical_item_id == item,
                                row.native_version_id == version,
                                row.kind.in_(("document_passage", "structured_snapshot")),
                            )
                            .order_by(row.ordinal)
                            .limit(501)
                        )
                    )
                    .mappings()
                    .all()
                )
        if len(values) > 500:
            raise SourceError("size_exceeded")
        return tuple(SimpleNamespace(**dict(value)) for value in values)
