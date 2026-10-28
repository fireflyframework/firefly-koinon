# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from test_curated_intents import committed_projection, input_for
from test_curated_intents import curated as curated


async def test_same_owner_can_review_evidence_from_a_read_only_origin_token(curated):
    from koinon.evidence.dtos import ConversationMessage, ConversationSnapshot, SourceReference
    from koinon.tokens.entities import PersonalToken
    from koinon.tokens.repositories import PersonalTokenRepository

    service, catalog, destination, context = curated
    original = await catalog.create(
        "issuer|owner", "north", kind="source", name="Admitted", parent_id=destination.id
    )
    document = await catalog.create(
        "issuer|owner", "north", kind="document", name="Document", parent_id=original.id
    )
    token = PersonalToken(
        id="read-origin",
        subject="issuer|owner",
        tenant_id="north",
        name="Read origin",
        token_hash="b" * 64,
        prefix="read",
        scopes=["catalog:read", "knowledge:search", "chat:use"],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    await context.get_bean(PersonalTokenRepository).save(token)
    reference = SourceReference(
        id="passage",
        asset_id=document.id,
        source_id=original.id,
        kind="document",
        title="Document",
        used_revision="chunk-sha256:" + "a" * 64,
        chunk_id="chunk",
        quote="Threshold47",
    )
    snapshot = ConversationSnapshot(
        thread_id="thread",
        tenant_id="north",
        owner_subject="issuer|owner",
        title="Research",
        revision="b" * 64,
        messages=(
            ConversationMessage(
                id="message", role="assistant", text="Threshold47", status="completed", revision="c" * 64
            ),
        ),
        sources=(reference,),
        source_manifest_complete=True,
        originating_token_ids=(token.id,),
    )

    class Snapshots:
        async def snapshot(self, *args):
            return snapshot

    class Sources:
        async def resolve(self, subject, tenant_id, sources):
            return tuple(
                value.model_copy(
                    update={"availability": "available", "current_revision": value.used_revision}
                )
                for value in sources
            )

    service.authority.snapshots = SimpleNamespace(get=lambda: Snapshots())
    service.authority.sources = SimpleNamespace(get=lambda: Sources())
    preview = await service.preview(
        "issuer|owner",
        "north",
        input_for(
            destination, origin={"kind": "conversation", "thread_id": "thread", "message_ids": ["message"]}
        ),
    )
    assert preview.evidence[0].kind == "document_passage"
    from pyfly.kernel import ServiceUnavailableException

    knowledge = SourceReference(
        id="knowledge",
        asset_id="published",
        title="Published fact",
        kind="knowledge_version",
        knowledge_item_id="published",
        knowledge_version_id="version",
        knowledge_version=1,
        used_revision="knowledge-content-sha256:" + "e" * 64,
        chunk_id="real-version-part",
    )
    snapshot = snapshot.model_copy(update={"sources": (knowledge,), "originating_token_ids": ()})
    with pytest.raises(ServiceUnavailableException) as failure:
        await service.preview(
            "issuer|owner",
            "north",
            input_for(
                destination,
                origin={"kind": "conversation", "thread_id": "thread", "message_ids": ["message"]},
            ),
        )
    assert failure.value.code == "CURATED_DERIVATION_UNQUALIFIED"


@pytest.mark.parametrize("remove_membership", [False, True])
async def test_committed_organizational_receipt_survives_confirmation_token_revocation(
    curated, remove_membership
):
    from pyfly.security.context import SecurityContext
    from pyfly.security.context_holder import SecurityContextHolder

    from koinon.knowledge.curated.authority import digest
    from koinon.knowledge.curated.dtos import KnowledgeCommitReceipt
    from koinon.knowledge.curated.ports import NativeCommitUncertain
    from koinon.tokens.entities import PersonalToken
    from koinon.tokens.repositories import PersonalTokenRepository

    service, _, destination, context = curated
    token = PersonalToken(
        id="writer",
        subject="issuer|owner",
        tenant_id="north",
        name="Writer",
        token_hash="d" * 64,
        prefix="writer",
        scopes=["catalog:read", "catalog:write", "ingest:write"],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    repository = context.get_bean(PersonalTokenRepository)
    await repository.save(token)

    class Port:
        stored = None
        writes = 0

        async def projection(self, subject, tenant_id, receipt):
            return await committed_projection(context, preview, receipt)

        async def receipt(self, *args):
            return self.stored

        async def commit(self, operation):
            self.writes += 1
            preview = operation.preview
            self.stored = KnowledgeCommitReceipt(
                operation_id=preview.id,
                intent_id=preview.id,
                intent_revision=1,
                authorization_digest=preview.authorization_digest,
                item_id=preview.target_item_id,
                native_item_id="native",
                native_version_id="version",
                version=1,
                serving_version=1,
                action=preview.action,
                content_sha256=digest(preview.after.model_dump(mode="json")),
                evidence_sha256=digest([value.model_dump(mode="json") for value in preview.evidence]),
                committed_at=datetime.now(UTC),
                retrieval_state="lexical_ready",
            )
            raise NativeCommitUncertain()

    port = Port()
    service.native = SimpleNamespace(get=lambda: port)
    with SecurityContextHolder.using(
        SecurityContext(
            user_id="owner", attributes={"iss": "issuer", "sub": "owner", "koinon_token_id": token.id}
        )
    ):
        preview = await service.preview(
            "issuer|owner", "north", input_for(destination, action="create_published")
        )
        pending = await service.confirm(
            "issuer|owner",
            "north",
            preview.id,
            {"confirm": True, "expected_revision": 1, "authorization_digest": preview.authorization_digest},
            "explicit-auth",
        )
        assert pending.status == "pending"
    token.revoked_at = datetime.now(UTC)
    await repository.save(token)
    if remove_membership:
        from koinon.catalog.errors import AccessDenied
        from koinon.catalog.repositories import MembershipRepository

        members = context.get_bean(MembershipRepository)
        owner = await members.find_by_id("owner")
        owner.active = False
        await members.save(owner)
        with pytest.raises(AccessDenied):
            await service.get("issuer|owner", "north", preview.id)
        assert await service.reconcile("issuer|owner", "north", preview.id)
        assert not await service.reconcile("issuer|owner", "north", preview.id)
        assert (
            await curated[1].get("issuer|reader", "north", preview.target_item_id)
        ).name == preview.after.title
        assert port.writes == 1
        return
    committed = await service.get("issuer|owner", "north", preview.id)
    assert committed.status == "committed" and committed.receipt == port.stored
    assert port.writes == 1
