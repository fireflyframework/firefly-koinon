# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Immutable transfer bindings must survive retries without dropping remembered authority."""

import pytest
from sqlalchemy import update
from test_personal_memory import memory_pair, native_tokens, token_row
from test_service import assistants as assistants

from koinon.assistants.lifecycle import timestamp
from koinon.assistants.memory.egress import MemoryEgress
from koinon.catalog.errors import AccessDenied
from koinon.tokens.entities import PersonalToken


@pytest.mark.parametrize("retry", [False, True])
async def test_saved_answer_egress_pins_generation_after_reset_and_origin_revocation(assistants, retry):
    engine = await native_tokens(assistants, [token_row("remembered-origin", ["catalog:read", "chat:use"])])
    service, history, queue, memory, folder, source, old, target, run, generation = await memory_pair(
        assistants, origin_token_id="remembered-origin"
    )
    await queue.finish(run.id, "pair-worker", code="CONTROLLED_FAILURE" if retry else None)
    egress = assistants[1].get_bean(MemoryEgress)
    bindings = await egress.bind("issuer|admin", "north", ((run.id, ()),))
    assert bindings[0].generation_id == generation
    assert await egress.authorize("issuer|admin", "north", bindings)
    if retry:
        await service.retry("issuer|admin", "north", run.id)
        current = await queue.claim("retry-worker")
        await queue.begin_generation(
            current.id, "retry-worker", model_id="empty", model_class="empty", api="chat"
        )
        assert await egress.authorize("issuer|admin", "north", bindings)
    async with engine.begin() as connection:
        await connection.execute(
            update(PersonalToken)
            .where(PersonalToken.id == "remembered-origin")
            .values(revoked_at=timestamp())
        )
    with pytest.raises(AccessDenied):
        await egress.authorize("issuer|admin", "north", bindings)


async def test_stored_query_authorization_uses_generating_memory_context(assistants):
    engine = await native_tokens(assistants, [token_row("remembered-origin", ["catalog:read", "chat:use"])])
    service, history, queue, memory, folder, source, old, target, run, generation = await memory_pair(
        assistants, origin_token_id="remembered-origin"
    )
    from koinon.assistants.entities import ToolResult

    result = ToolResult(
        id="query-artifact",
        run_id=run.id,
        kind="query",
        created_at=timestamp(),
        payload={
            "asset_ids": [],
            "generation_id": generation,
            "origin_token_id": None,
            "data": {"query_id": "stored-query", "preview": [{"private_value": "remembered"}]},
        },
    )
    await service.results.save(result)
    await queue.finish(run.id, "pair-worker")
    egress = assistants[1].get_bean(MemoryEgress)
    await egress.query("issuer|admin", "north", "stored-query")
    with pytest.raises(AccessDenied):
        await egress.query("issuer|other", "north", "stored-query")
    async with engine.begin() as connection:
        await connection.execute(
            update(PersonalToken)
            .where(PersonalToken.id == "remembered-origin")
            .values(revoked_at=timestamp())
        )
    with pytest.raises(AccessDenied):
        await egress.query("issuer|admin", "north", "stored-query")


async def test_saved_export_rechecks_memory_after_creation(assistants):
    from datetime import timedelta
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from koinon.assistants.memory.egress_dtos import MemoryConversationSnapshot
    from koinon.evidence.dtos import ConversationMessage
    from koinon.evidence.entities import EvidenceReview
    from koinon.evidence.reviews import EvidenceReviews
    from koinon.evidence.settings import EvidenceSettings
    from koinon.exports.dtos import ExportCreate
    from koinon.exports.entities import ExportRecord
    from koinon.exports.service import KnowledgeExports

    engine = await native_tokens(
        assistants, [token_row("export-memory-origin", ["catalog:read", "chat:use"])]
    )
    service, history, queue, memory, folder, source, old, target, run, generation = await memory_pair(
        assistants, origin_token_id="export-memory-origin"
    )
    from koinon.answers.dtos import EvidenceAnswerPlan
    from koinon.evidence.ports import ConversationOutputPort

    await queue.release_answer(
        run.id, "pair-worker", EvidenceAnswerPlan(outcome="insufficient_evidence"), "en"
    )
    released_text = (await service.message_repository.find_by_id(run.message_id)).text
    await queue.finish(run.id, "pair-worker")
    egress = assistants[1].get_bean(MemoryEgress)
    bindings = await egress.bind("issuer|admin", "north", ((run.id, ()),))
    snapshot = MemoryConversationSnapshot(
        thread_id=target["id"],
        tenant_id="north",
        owner_subject="issuer|admin",
        title="Retained export",
        revision="a" * 64,
        memory_bindings=bindings,
        messages=(
            ConversationMessage(
                id=run.message_id,
                role="assistant",
                text=released_text,
                status="completed",
                revision="b" * 64,
            ),
        ),
    )
    review = EvidenceReview(
        id="review",
        tenant_id="north",
        owner_subject="issuer|admin",
        title=snapshot.title,
        revision="c" * 64,
        request_json={"kind": "conversation", "format": "json", "include_evidence": True},
        snapshot_json=snapshot.model_dump(mode="json"),
        manifest_json=[],
        creator_token_id=None,
        kind="export",
        created_at=timestamp(),
        expires_at=timestamp() + timedelta(hours=1),
        consumed_at=None,
    )
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync: EvidenceReview.__table__.create(sync, checkfirst=True))
        await connection.run_sync(lambda sync: ExportRecord.__table__.create(sync, checkfirst=True))
        await connection.execute(
            EvidenceReview.__table__.insert().values(
                **{column.name: getattr(review, column.name) for column in EvidenceReview.__table__.columns}
            )
        )
    reviews = object.__new__(EvidenceReviews)
    reviews.settings = EvidenceSettings()
    reviews.catalog = SimpleNamespace(_lock_tenant=AsyncMock(), _audit=AsyncMock())
    reviews.claim = AsyncMock(return_value=review)
    reviews.reviews = SimpleNamespace(find_by_id=AsyncMock(return_value=review))
    reviews.access = SimpleNamespace(check=AsyncMock())
    reviews.memory = SimpleNamespace(get=lambda: egress)
    reviews.outputs = SimpleNamespace(get=lambda: assistants[1].get_bean(ConversationOutputPort))
    saved = []

    async def save(row):
        from pyfly.data.transaction import current_unit_of_work

        saved.append(row)
        unit = current_unit_of_work("primary")
        assert unit is not None
        unit.resource.add(row)
        await unit.resource.flush()

    exports = KnowledgeExports(
        SimpleNamespace(
            active_count=AsyncMock(return_value=0),
            save=save,
            find_all=AsyncMock(side_effect=lambda **kwargs: saved),
        ),
        reviews,
    )
    created = await exports.create(
        "issuer|admin", "north", ExportCreate(review_id=review.id, expected_revision=review.revision)
    )
    assert released_text.encode() in (await exports.download("issuer|admin", "north", created.id)).content
    async with engine.begin() as connection:
        await connection.execute(
            update(ExportRecord).where(ExportRecord.id == created.id).values(cancelled_at=timestamp())
        )
    with pytest.raises(AccessDenied):
        await exports.download("issuer|admin", "north", created.id)
    async with engine.begin() as connection:
        await connection.execute(
            update(ExportRecord).where(ExportRecord.id == created.id).values(cancelled_at=None)
        )
    async with engine.begin() as connection:
        await connection.execute(
            update(PersonalToken)
            .where(PersonalToken.id == "export-memory-origin")
            .values(revoked_at=timestamp())
        )
    with pytest.raises(AccessDenied):
        await exports.download("issuer|admin", "north", created.id)


async def test_recipient_transfer_requires_explicit_consent_and_preserves_private_chat_bounds(assistants):
    from types import SimpleNamespace

    from pyfly.kernel import ConflictException

    from koinon.evidence.access import EvidenceAccess

    engine = await native_tokens(assistants, [token_row("share-memory-origin", ["catalog:read", "chat:use"])])
    service, history, queue, memory, folder, source, old, target, run, generation = await memory_pair(
        assistants, origin_token_id="share-memory-origin"
    )
    await queue.finish(run.id, "pair-worker")
    egress = assistants[1].get_bean(MemoryEgress)
    egress.access = SimpleNamespace(
        get=lambda: EvidenceAccess(service.catalog, service.catalog.restriction.tokens)
    )
    bindings = await egress.bind("issuer|admin", "north", ((run.id, ()),))
    with pytest.raises(ConflictException, match="remembered context"):
        await egress.authorize(
            "issuer|admin", "north", bindings, transfer=True, reader_subject="issuer|other"
        )
    assert await egress.authorize(
        "issuer|admin", "north", bindings, transfer=True, consent=True, reader_subject="issuer|other"
    )
    with pytest.raises(AccessDenied):
        await service.thread("issuer|other", "north", source["id"])
    with pytest.raises(AccessDenied):
        await egress.authorize(
            "issuer|admin", "north", bindings, transfer=True, consent=True, reader_subject="issuer|outsider"
        )
    async with engine.begin() as connection:
        await connection.execute(
            update(PersonalToken)
            .where(PersonalToken.id == "share-memory-origin")
            .values(revoked_at=timestamp())
        )
    with pytest.raises(AccessDenied):
        await egress.authorize(
            "issuer|admin", "north", bindings, transfer=True, consent=True, reader_subject="issuer|other"
        )


async def test_native_query_context_authorizes_before_any_chat_tool_result_exists(assistants):
    from koinon.assistants.memory.query_access import MemoryQueryAccess
    from koinon.knowledge.adapters import native_scope

    engine = await native_tokens(assistants, [token_row("query-memory-origin", ["catalog:read", "chat:use"])])
    service, history, queue, memory, folder, source, old, target, run, generation = await memory_pair(
        assistants, origin_token_id="query-memory-origin"
    )
    value = await memory.query_context("issuer|admin", "north", run.id)
    access = assistants[1].get_bean(MemoryQueryAccess)
    workspace = "00000000-0000-0000-0000-000000000001"
    with native_scope("structured", "north", workspace, "issuer|admin"):
        await access.authorize((value,), "north", workspace)
    with native_scope("structured", "north", workspace, "issuer|other"), pytest.raises(AccessDenied):
        await access.authorize((value,), "north", workspace)
    async with engine.begin() as connection:
        await connection.execute(
            update(PersonalToken)
            .where(PersonalToken.id == "query-memory-origin")
            .values(revoked_at=timestamp())
        )
    with native_scope("structured", "north", workspace, "issuer|admin"), pytest.raises(AccessDenied):
        await access.authorize((value,), "north", workspace)


async def test_egress_suppresses_large_results_and_manifests_in_sql_before_transfer(assistants, monkeypatch):
    from koinon.assistants.entities import ToolResult
    from koinon.assistants.memory import egress_repository

    service, history, queue, memory, folder, source, old, target, run, generation = await memory_pair(
        assistants
    )
    await service.results.save(
        ToolResult(
            id="large-egress",
            run_id=run.id,
            kind="query",
            created_at=timestamp(),
            payload={"generation_id": generation, "asset_ids": [], "data": {"text": "x" * 4096}},
        )
    )
    egress = assistants[1].get_bean(MemoryEgress)
    monkeypatch.setattr(egress_repository, "MAX_EGRESS_BYTES", 128)
    headers, results = await egress.repository.fixed("issuer|admin", "north", (run.id,), ("large-egress",))
    assert headers and results == ()
    with pytest.raises(AccessDenied):
        await egress.repository.manifests((generation,))


async def test_native_curated_admission_rechecks_confirmed_memory_immediately_before_commit(assistants):
    from datetime import timedelta
    from hashlib import sha256
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from koinon.knowledge.curated.authority import CuratedAuthority, digest
    from koinon.knowledge.curated.entities import KnowledgeIntentRow
    from koinon.knowledge.curated.intents import view
    from koinon.knowledge.curated.native import NativeCuratedKnowledge
    from koinon.knowledge.curated.ports import NativeKnowledgeOperation

    engine = await native_tokens(
        assistants, [token_row("curated-memory-origin", ["catalog:read", "chat:use"])]
    )
    service, history, queue, memory, folder, source, old, target, run, generation = await memory_pair(
        assistants, origin_token_id="curated-memory-origin"
    )
    await queue.finish(run.id, "pair-worker")
    destination = None
    for kind in ("workspace", "project", "collection"):
        destination = await service.catalog.create(
            "issuer|admin", "north", kind=kind, name=kind, parent_id=destination.id if destination else None
        )
    egress = assistants[1].get_bean(MemoryEgress)
    bindings = await egress.bind("issuer|admin", "north", ((run.id, ()),))
    authority = CuratedAuthority(service.catalog, None, None, memory=SimpleNamespace(get=lambda: egress))
    location = await authority.destination("issuer|admin", "north", destination.id)
    request = {
        "action": "create_published",
        "destination_id": destination.id,
        "content": {"title": "Reviewed remembered rule", "body": "Explicitly reviewed answer"},
        "origin": {"kind": "user_statement"},
        "_memory_context": {
            "present": True,
            "consented": True,
            "bindings": [binding.model_dump(mode="json") for binding in bindings],
        },
    }
    row = KnowledgeIntentRow(
        id="confirmed-memory-intent",
        tenant_id="north",
        subject="issuer|admin",
        revision=1,
        status="committing",
        request_json=request,
        destination_json=location.model_dump(mode="json"),
        evidence_json=[
            {
                "kind": "user_statement",
                "text": request["content"]["body"],
                "sha256": sha256(request["content"]["body"].encode()).hexdigest(),
                "author_subject": "issuer|admin",
                "recorded_at": timestamp().isoformat(),
            }
        ],
        before_json=None,
        target_item_id="new-knowledge",
        authorization_digest=digest(request),
        originating_token_ids=[],
        preview_token_id=None,
        confirming_token_id=None,
        confirmation_key="explicit-confirmation",
        receipt_json=None,
        created_at=timestamp(),
        expires_at=timestamp() + timedelta(hours=1),
    )
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync: KnowledgeIntentRow.__table__.create(sync, checkfirst=True))
        await connection.execute(
            KnowledgeIntentRow.__table__.insert().values(
                **{column.name: getattr(row, column.name) for column in KnowledgeIntentRow.__table__.columns}
            )
        )
    native = object.__new__(NativeCuratedKnowledge)
    native.intents, native.authority = SimpleNamespace(find_by_id=AsyncMock(return_value=row)), authority
    operation = NativeKnowledgeOperation(view(row), ())
    assert await native.admitted(operation) is row
    async with engine.begin() as connection:
        await connection.execute(
            update(PersonalToken)
            .where(PersonalToken.id == "curated-memory-origin")
            .values(revoked_at=timestamp())
        )
    with pytest.raises(AccessDenied):
        await native.admitted(operation)


async def test_native_query_context_preserves_active_consent_checks_and_owned_historical_replay(assistants):
    from koinon.assistants.memory.query_access import MemoryQueryAccess
    from koinon.knowledge.adapters import native_scope

    service, history, queue, memory, folder, source, old, target, run, generation = await memory_pair(
        assistants
    )
    value = await memory.query_context("issuer|admin", "north", run.id)
    access = assistants[1].get_bean(MemoryQueryAccess)
    workspace = "00000000-0000-0000-0000-000000000001"
    with native_scope("structured", "north", workspace, "issuer|admin"):
        await access.authorize((value,), "north", workspace)
    await history.patch_folder(
        "issuer|admin", "north", folder["id"], {"expected_revision": 1, "memory_enabled": False}
    )
    with native_scope("structured", "north", workspace, "issuer|admin"), pytest.raises(AccessDenied):
        await access.authorize((value,), "north", workspace)
    await queue.finish(run.id, "pair-worker")
    with native_scope("structured", "north", workspace, "issuer|admin"):
        await access.authorize((value,), "north", workspace)
