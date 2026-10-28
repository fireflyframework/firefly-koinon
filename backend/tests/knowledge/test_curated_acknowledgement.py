# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

import pytest
from test_curated_intents import curated as curated
from test_curated_intents import input_for


async def test_committed_projection_is_atomic_monotonic_and_keeps_published_metadata(curated):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import infrastructure_unit
    from sqlalchemy import select

    from koinon.catalog.entities import AuditEvent, CatalogEntry
    from koinon.knowledge.curated.acknowledgement import CatalogAcknowledgement
    from koinon.knowledge.curated.authority import digest
    from koinon.knowledge.curated.dtos import KnowledgeCommitReceipt
    from koinon.knowledge.curated.entities import CuratedCatalogState
    from koinon.knowledge.curated.ports import NativeCatalogProjection
    from koinon.knowledge.entities import DomainBinding

    service, _, destination, context = curated
    preview = await service.preview(
        "issuer|owner", "north", input_for(destination, action="create_published")
    )
    source = context.get_bean(DataSourceRegistry).get("primary")
    async with infrastructure_unit(source) as session:
        session.add(
            DomainBinding(
                id="workspace-alias",
                tenant_id="north",
                catalog_id=destination.workspace_id,
                workspace_id=destination.workspace_id,
                domain="canon",
                entity_kind="workspace",
                native_id="native-space",
                native_workspace_id="native-space",
                created_by="issuer|owner",
            )
        )
    receipt = KnowledgeCommitReceipt(
        operation_id=preview.id,
        intent_id=preview.id,
        intent_revision=1,
        authorization_digest=preview.authorization_digest,
        item_id=preview.target_item_id,
        native_item_id="native-item",
        native_version_id="v1",
        version=1,
        serving_version=1,
        action=preview.action,
        content_sha256=digest(preview.after.model_dump(mode="json")),
        evidence_sha256=digest([item.model_dump(mode="json") for item in preview.evidence]),
        committed_at=datetime.now(UTC),
        retrieval_state="lexical_ready",
    )
    projection = NativeCatalogProjection(
        native_workspace_id="native-space",
        title="Published title",
        serving_version_id="v1",
        serving_operation_id=preview.id,
    )
    projector = context.get_bean(CatalogAcknowledgement)
    with pytest.raises(RuntimeError, match="after-ack"):
        async with infrastructure_unit(source):
            await projector.apply(preview, receipt, projection)
            raise RuntimeError("after-ack")
    async with infrastructure_unit(source, read_only=True) as session:
        assert await session.get(CatalogEntry, receipt.item_id) is None
    await projector.apply(preview, receipt, projection)
    draft = receipt.model_copy(
        update={"version": 2, "native_version_id": "v2", "operation_id": "draft-op", "action": "update_draft"}
    )
    await projector.apply(preview, draft, projection)
    await projector.apply(preview, receipt, projection)
    async with infrastructure_unit(source, read_only=True) as session:
        state = await session.get(CuratedCatalogState, receipt.item_id)
        item = await session.get(CatalogEntry, receipt.item_id)
        assert state.head_version == 2 and state.head_version_id == "v2"
        assert state.serving_version_id == "v1" and item.name == "Published title"
        assert item.status == "published" and item.metadata_json["head_version"] == 2
        events = list(await session.scalars(select(AuditEvent).where(AuditEvent.resource_id == item.id)))
        assert len(events) == 2
