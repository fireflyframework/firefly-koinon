# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Remembered source provenance survives native publication and current source revocation."""

from types import SimpleNamespace

import pytest
from test_curated_intents import curated as curated
from test_curated_intents import input_for
from test_curated_native_commit import transaction_fixture
from test_curated_native_events import native_lifecycle as native_lifecycle


async def test_remembered_basis_and_source_roots_survive_published_native_version(curated, native_lifecycle):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import infrastructure_unit

    from koinon.catalog.errors import AccessDenied
    from koinon.catalog.repositories import MembershipRepository
    from koinon.evidence.dtos import SourceReference
    from koinon.knowledge.curated.acknowledgement import CatalogAcknowledgement
    from koinon.knowledge.curated.authority import digest
    from koinon.knowledge.curated.dtos import StructuredEvidence
    from koinon.knowledge.curated.ports import NativeCatalogProjection, NativeKnowledgeOperation
    from koinon.knowledge.curated.reads import CuratedKnowledgeReads
    from koinon.knowledge.entities import DomainBinding

    service, destination, unit = await transaction_fixture(curated, native_lifecycle)
    catalog, context = curated[1], curated[3]
    source_workspace = await catalog.create("issuer|owner", "north", kind="workspace", name="Source bounds")
    dataset = source_workspace
    for kind in ("project", "collection", "source", "dataset"):
        dataset = await catalog.create("issuer|owner", "north", kind=kind, name=kind, parent_id=dataset.id)
    reference = SourceReference(
        id="retained-query",
        asset_id=dataset.id,
        source_id=dataset.parent_id,
        kind="dataset",
        title="Remembered snapshot",
        query_id="recorded-query",
        snapshot_id="recorded-snapshot",
        used_revision="snapshot:recorded-snapshot",
        current_revision="snapshot:recorded-snapshot",
        availability="available",
    )

    class Sources:
        async def resolve(self, subject, tenant_id, sources):
            for source in sources:
                await catalog.get(subject, tenant_id, source.asset_id)
            return sources

    service.authority.sources = SimpleNamespace(get=lambda: Sources())
    preview = await service.preview(
        "issuer|owner", "north", input_for(destination, action="create_published")
    )
    evidence = StructuredEvidence(source=reference, basis="remembered_context")
    preview = preview.model_copy(
        update={
            "evidence": (evidence,),
            "remembered_context_present": True,
            "authorization_digest": digest(
                {"reviewed": preview.authorization_digest, "evidence": evidence.model_dump(mode="json")}
            ),
        }
    )
    receipt = await unit.commit(NativeKnowledgeOperation(preview, ()), native_workspace_id="owned")
    primary = context.get_bean(DataSourceRegistry).get("primary")
    async with infrastructure_unit(primary) as session:
        session.add(
            DomainBinding(
                id="memory-workspace-alias",
                tenant_id="north",
                catalog_id=destination.workspace_id,
                workspace_id=destination.workspace_id,
                domain="canon",
                entity_kind="workspace",
                native_id="owned",
                native_workspace_id="owned",
                created_by="issuer|owner",
            )
        )
    await context.get_bean(CatalogAcknowledgement).apply(
        preview,
        receipt,
        NativeCatalogProjection(
            native_workspace_id="owned",
            title=preview.after.title,
            serving_version_id=receipt.native_version_id,
            serving_operation_id=receipt.operation_id,
            source_asset_ids=(dataset.id,),
        ),
    )
    reads = context.get_bean(CuratedKnowledgeReads)
    reads.native = SimpleNamespace(datasource=lambda: native_lifecycle[1])
    published = await reads.version("issuer|reader", "north", receipt.item_id)
    assert published.selected_version.evidence[0].basis == "remembered_context"
    assert published.selected_version.evidence_sha256 == digest([evidence.model_dump(mode="json")])
    memberships = context.get_bean(MembershipRepository)
    reader = await memberships.find_by_id("reader")
    reader.workspace_id = destination.workspace_id
    await memberships.save(reader)
    with pytest.raises(AccessDenied):
        await reads.version("issuer|reader", "north", receipt.item_id)
