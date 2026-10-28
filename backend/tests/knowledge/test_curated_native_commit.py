# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace

import pytest
from test_curated_intents import curated as curated
from test_curated_intents import input_for
from test_curated_native_events import native_lifecycle as native_lifecycle


async def transaction_fixture(curated, native_lifecycle):
    from koinon.knowledge.curated.domain_entities import (
        CuratedCommitRow,
        CuratedEvidenceRow,
        CuratedHeadRow,
        CuratedVersionChunkRow,
    )
    from koinon.knowledge.curated.native_unit import NativeKnowledgeTransaction

    service, _, destination, _ = curated
    lifecycle, source, publisher, _ = native_lifecycle
    async with source.engine.begin() as connection:
        for entity in (CuratedHeadRow, CuratedCommitRow, CuratedEvidenceRow, CuratedVersionChunkRow):
            await connection.run_sync(entity.__table__.create)

    async def authorize(operation):
        await service.authority.destination("issuer|owner", "north", destination.id)
        await service.authority.evidence("issuer|owner", "north", operation.preview.evidence)

    return service, destination, NativeKnowledgeTransaction(source, lifecycle, publisher, authorize)


async def test_native_commit_idempotent_real_body_projection_without_fake_sources(curated, native_lifecycle):
    from pyfly.data.transaction import infrastructure_unit
    from sqlalchemy import func, select

    from koinon.knowledge.curated.domain_entities import (
        CuratedCommitRow,
        CuratedEvidenceRow,
        CuratedHeadRow,
        CuratedVersionChunkRow,
    )
    from koinon.knowledge.curated.ports import NativeKnowledgeOperation

    service, destination, unit = await transaction_fixture(curated, native_lifecycle)
    preview = await service.preview(
        "issuer|owner", "north", input_for(destination, action="create_published")
    )
    operation = NativeKnowledgeOperation(preview, ())
    first = await unit.commit(operation, native_workspace_id="owned")
    second = await unit.commit(operation, native_workspace_id="owned")
    assert first == second and first.version == 1 and first.serving_version == 1
    assert first.retrieval_state == "lexical_ready"
    async with infrastructure_unit(native_lifecycle[1], read_only=True) as session:
        for entity in (CuratedCommitRow, CuratedHeadRow, CuratedEvidenceRow, CuratedVersionChunkRow):
            assert await session.scalar(select(func.count()).select_from(entity)) == 1
        chunk = await session.scalar(select(CuratedVersionChunkRow))
        assert chunk.content == preview.after.body and chunk.char_start == 0
        assert chunk.char_end == len(preview.after.body)


async def test_draft_preserves_serving_version_then_explicit_publication_swaps(curated, native_lifecycle):
    from koinon.knowledge.curated.ports import NativeKnowledgeOperation

    service, destination, unit = await transaction_fixture(curated, native_lifecycle)
    first = await service.preview("issuer|owner", "north", input_for(destination, action="create_published"))
    receipt = await unit.commit(NativeKnowledgeOperation(first, ()), native_workspace_id="owned")

    class Reader:
        async def head(self, subject, tenant, identifier):
            return await unit.head(tenant, "owned", identifier)

    service.native = SimpleNamespace(get=lambda: Reader())
    draft_input = input_for(
        destination,
        action="update_draft",
        target_item_id=first.target_item_id,
        expected_version=receipt.version,
        content={"title": "New draft", "body": "The threshold is 99."},
    )
    draft = await service.preview("issuer|owner", "north", draft_input)
    result = await unit.commit(NativeKnowledgeOperation(draft, ()), native_workspace_id="owned")
    assert result.version == 2 and result.serving_version == 1
    assert result.retrieval_state == "not_published"
    publish_input = input_for(
        destination,
        action="publish_draft",
        target_item_id=first.target_item_id,
        expected_version=2,
        content=draft.after.model_dump(mode="json"),
    )
    publish = await service.preview("issuer|owner", "north", publish_input)
    result = await unit.commit(NativeKnowledgeOperation(publish, ()), native_workspace_id="owned")
    assert result.version == 3 and result.serving_version == 3


async def test_failure_after_native_events_rolls_back_content_receipts_and_projection(
    curated, native_lifecycle
):
    from flycanon.models.entities.audit_event import AuditEventRow
    from flycanon.models.entities.knowledge_version import KnowledgeVersionRow
    from pyfly.data.transaction import infrastructure_unit
    from sqlalchemy import func, select

    from koinon.knowledge.curated.domain_entities import (
        CuratedCommitRow,
        CuratedEvidenceRow,
        CuratedHeadRow,
        CuratedVersionChunkRow,
    )
    from koinon.knowledge.curated.ports import NativeKnowledgeOperation

    service, destination, unit = await transaction_fixture(curated, native_lifecycle)
    publisher = unit.publisher

    class FailureAfterOutbox:
        async def publish(self, **values):
            await publisher.publish(**values)
            if values["event_type"] == "KnowledgeCommitted":
                raise RuntimeError("controlled-final-outbox-failure")

    unit.publisher = FailureAfterOutbox()
    preview = await service.preview(
        "issuer|owner", "north", input_for(destination, action="create_published")
    )
    with pytest.raises(RuntimeError, match="controlled-final-outbox-failure"):
        await unit.commit(NativeKnowledgeOperation(preview, ()), native_workspace_id="owned")
    async with infrastructure_unit(native_lifecycle[1], read_only=True) as session:
        for entity in (
            CuratedCommitRow,
            CuratedEvidenceRow,
            CuratedHeadRow,
            CuratedVersionChunkRow,
            KnowledgeVersionRow,
            AuditEventRow,
        ):
            assert await session.scalar(select(func.count()).select_from(entity)) == 0
        assert await session.scalar(select(func.count()).select_from(native_lifecycle[3].events)) == 0


async def test_authorized_null_summary_is_cleared_without_changing_partial_update_semantics(
    curated, native_lifecycle
):
    from flycanon.interfaces.dtos.knowledge import UpdateKnowledgeRequest
    from pyfly.data.transaction import infrastructure_unit

    from koinon.knowledge.curated.authority import digest
    from koinon.knowledge.curated.ports import NativeKnowledgeOperation

    service, destination, unit = await transaction_fixture(curated, native_lifecycle)
    first = await service.preview(
        "issuer|owner",
        "north",
        input_for(
            destination,
            action="create_published",
            content={"title": "Policy", "body": "Threshold47", "summary": "Existing summary"},
        ),
    )
    receipt = await unit.commit(NativeKnowledgeOperation(first, ()), native_workspace_id="owned")

    class Reader:
        async def head(self, subject, tenant, identifier):
            return await unit.head(tenant, "owned", identifier)

    service.native = SimpleNamespace(get=lambda: Reader())
    draft = await service.preview(
        "issuer|owner",
        "north",
        input_for(
            destination,
            action="update_draft",
            target_item_id=first.target_item_id,
            expected_version=1,
            content={"title": "Policy", "body": "Threshold48", "summary": None},
        ),
    )
    result = await unit.commit(NativeKnowledgeOperation(draft, ()), native_workspace_id="owned")
    _, observed = await unit.head("north", "owned", first.target_item_id)
    assert observed.summary is None
    assert digest(observed.model_dump(mode="json")) == result.content_sha256

    # Standalone partial updates retain an omitted/null summary by default.
    async with infrastructure_unit(native_lifecycle[1]):
        kept = await native_lifecycle[0].update(
            receipt.native_item_id,
            UpdateKnowledgeRequest(summary="Standalone summary"),
            tenant_id="north",
            workspace_id="owned",
            event_publisher=unit.publisher,
        )
        patched = await native_lifecycle[0].update(
            receipt.native_item_id,
            UpdateKnowledgeRequest(summary=None),
            tenant_id="north",
            workspace_id="owned",
            event_publisher=unit.publisher,
        )
    assert kept.summary == patched.summary == "Standalone summary"


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", "Unauthorized title"),
        ("body", "Unauthorized body"),
        ("summary", "Unauthorized summary"),
        ("domain", "security"),
        ("tags_json", ["unauthorized"]),
    ],
)
async def test_real_persisted_content_mismatch_rolls_back_every_native_effect(
    curated, native_lifecycle, field, value
):
    from flycanon.models.entities.audit_event import AuditEventRow
    from flycanon.models.entities.knowledge_item import KnowledgeItemRow
    from flycanon.models.entities.knowledge_version import KnowledgeVersionRow
    from pyfly.data.transaction import infrastructure_unit
    from pyfly.kernel import ConflictException
    from sqlalchemy import func, select, update

    from koinon.knowledge.curated.domain_entities import (
        CuratedCommitRow,
        CuratedEvidenceRow,
        CuratedHeadRow,
        CuratedVersionChunkRow,
    )
    from koinon.knowledge.curated.ports import NativeKnowledgeOperation

    service, destination, unit = await transaction_fixture(curated, native_lifecycle)
    lifecycle = unit.lifecycle

    class RewriteStoredContent:
        async def create(self, *args, **kwargs):
            version = await lifecycle.create(*args, **kwargs)
            async with infrastructure_unit(native_lifecycle[1]) as session:
                # Simulates a repository/trigger change without modifying the returned ORM instance.
                await session.execute(
                    update(KnowledgeVersionRow)
                    .where(KnowledgeVersionRow.id == version.id)
                    .values(**{field: value}),
                    execution_options={"synchronize_session": False},
                )
            return version

    unit.lifecycle = RewriteStoredContent()
    preview = await service.preview(
        "issuer|owner", "north", input_for(destination, action="create_published")
    )
    with pytest.raises(ConflictException, match="authorized"):
        await unit.commit(NativeKnowledgeOperation(preview, ()), native_workspace_id="owned")
    async with infrastructure_unit(native_lifecycle[1], read_only=True) as session:
        for entity in (
            KnowledgeItemRow,
            KnowledgeVersionRow,
            AuditEventRow,
            CuratedCommitRow,
            CuratedEvidenceRow,
            CuratedHeadRow,
            CuratedVersionChunkRow,
        ):
            assert await session.scalar(select(func.count()).select_from(entity)) == 0
        assert await session.scalar(select(func.count()).select_from(native_lifecycle[3].events)) == 0


async def test_final_outbox_side_effect_cannot_change_authorized_content_before_commit(
    curated, native_lifecycle
):
    from flycanon.models.entities.knowledge_version import KnowledgeVersionRow
    from pyfly.data.transaction import infrastructure_unit
    from pyfly.kernel import ConflictException
    from sqlalchemy import func, select, update

    from koinon.knowledge.curated.domain_entities import CuratedCommitRow
    from koinon.knowledge.curated.ports import NativeKnowledgeOperation

    service, destination, unit = await transaction_fixture(curated, native_lifecycle)
    publisher = unit.publisher

    class RewriteAfterReceiptPublication:
        async def publish(self, **values):
            await publisher.publish(**values)
            if values["event_type"] == "KnowledgeCommitted":
                async with infrastructure_unit(native_lifecycle[1]) as session:
                    await session.execute(
                        update(KnowledgeVersionRow).values(summary="Not reviewed"),
                        execution_options={"synchronize_session": False},
                    )

    unit.publisher = RewriteAfterReceiptPublication()
    preview = await service.preview(
        "issuer|owner", "north", input_for(destination, action="create_published")
    )
    with pytest.raises(ConflictException, match="authorized"):
        await unit.commit(NativeKnowledgeOperation(preview, ()), native_workspace_id="owned")
    async with infrastructure_unit(native_lifecycle[1], read_only=True) as session:
        for table in (KnowledgeVersionRow, CuratedCommitRow):
            assert await session.scalar(select(func.count()).select_from(table)) == 0
        assert await session.scalar(select(func.count()).select_from(native_lifecycle[3].events)) == 0
