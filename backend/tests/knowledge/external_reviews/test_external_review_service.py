# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder


def security(token="origin"):
    return SecurityContextHolder.using(
        SecurityContext(
            user_id="owner", attributes={"iss": "issuer", "sub": "owner", "koinon_token_id": token}
        )
    )


def values(destination):
    return {
        "action": "create_draft",
        "destination_id": destination.id,
        "content": {"title": "External suggestion", "body": "A proposal from another application."},
    }


async def staged(reviewed):
    service, _, destination, _ = reviewed
    with security():
        view = await service.stage("issuer|owner", "north", values(destination), "stage-1")
        challenge = await service.challenge("issuer|owner", "north", view.id)
    return view, challenge


def decision(view, challenge, **changes):
    return {
        "expected_revision": view.review.revision,
        "authorization_digest": view.review.authorization_digest,
        "nonce": challenge.nonce,
        **changes,
    }


async def test_staging_is_private_immutable_unverified_and_credential_derived(reviewed):
    from koinon.knowledge.external_reviews.repositories import ExternalReviewRepository

    service, intents, destination, context = reviewed
    view, challenge = await staged(reviewed)
    assert view.status == "preview" and view.review.receipt is None
    assert "nonce" not in view.model_dump_json()
    evidence = view.review.evidence[0]
    assert evidence.kind == "external_proposal" and evidence.authority == "unverified"
    assert evidence.provider is None and evidence.model is None
    assert evidence.submitted_by == "issuer|owner" and evidence.credential_id == "origin"
    row = await context.get_bean(ExternalReviewRepository).find_by_id(view.id)
    assert challenge.nonce not in str(row.__dict__)
    assert row.nonce_sha256 and row.expires_at <= datetime.now(UTC) + timedelta(minutes=15)
    with security():
        assert await service.stage("issuer|owner", "north", values(destination), "stage-1") == view
    assert await intents.intents.count() == 1


async def test_regular_confirmation_cannot_bypass_external_review(reviewed):
    from koinon.catalog.errors import AccessDenied

    _, intents, _, _ = reviewed
    view, _ = await staged(reviewed)
    with security(), pytest.raises(AccessDenied, match="external"):
        await intents.confirm(
            "issuer|owner",
            "north",
            view.id,
            {
                "confirm": True,
                "expected_revision": 1,
                "authorization_digest": view.review.authorization_digest,
            },
            "bypass",
        )
    with security(), pytest.raises(AccessDenied, match="external"):
        await intents.cancel("issuer|owner", "north", view.id, 1)


@pytest.mark.parametrize(
    "change", [{"nonce": "x" * 43}, {"expected_revision": 2}, {"authorization_digest": "a" * 64}]
)
async def test_exact_nonce_digest_revision_required_before_commit(reviewed, change):
    from pyfly.kernel import ConflictException

    from koinon.catalog.errors import AccessDenied

    service, intents, _, _ = reviewed
    view, challenge = await staged(reviewed)
    with security(), pytest.raises((ConflictException, AccessDenied)):
        await service.approve(
            "issuer|owner", "north", view.id, decision(view, challenge, **change), "approve"
        )
    assert (await intents.intents.find_by_id(view.id)).status == "preview"


@pytest.mark.parametrize("changed", ["source", "origin"])
async def test_server_read_receipts_snapshot_actual_sources_and_recheck_them_before_approval(
    reviewed, changed
):
    from pyfly.kernel import ConflictException

    from koinon.catalog.errors import AccessDenied
    from koinon.evidence.dtos import SourceReference
    from koinon.tokens.repositories import PersonalTokenRepository

    service, intents, destination, context = reviewed
    assert intents.authority.read_receipts is not None
    assert intents.authority.read_receipts.get() is not None
    for identifier in ("origin", "other"):
        token = await context.get_bean(PersonalTokenRepository).find_by_id(identifier)
        token.scopes = [*token.scopes, "knowledge:search"]
        await context.get_bean(PersonalTokenRepository).save(token)
    catalog = intents.authority.catalog
    source = await catalog.create(
        "issuer|owner", "north", kind="source", name="Actual source", parent_id=destination.id
    )
    document = await catalog.create(
        "issuer|owner", "north", kind="document", name="Actual document", parent_id=source.id
    )
    reference = SourceReference(
        id="actual-read",
        asset_id=document.id,
        source_id=source.id,
        kind="document",
        title="Actual document",
        used_revision="chunk-sha256:" + "a" * 64,
        chunk_id="actual-chunk",
        quote="actual observed text",
    )

    class Receipts:
        async def resolve(self, subject, tenant, identifiers):
            assert (subject, tenant, identifiers) == ("issuer|owner", "north", ("read-receipt",))
            return (reference,), ("other",)

    class Sources:
        available = True

        async def resolve(self, subject, tenant, sources):
            return tuple(
                value.model_copy(
                    update={
                        "availability": "available" if self.available else "missing",
                        "current_revision": value.used_revision,
                    }
                )
                for value in sources
            )

    sources = Sources()
    intents.authority.read_receipts = SimpleNamespace(get=lambda: Receipts())
    intents.authority.sources = SimpleNamespace(get=lambda: sources)
    with security():
        view = await service.stage(
            "issuer|owner",
            "north",
            {**values(destination), "source_receipt_ids": ["read-receipt"]},
            "derived",
        )
        challenge = await service.challenge("issuer|owner", "north", view.id)
    assert [item.kind for item in view.review.evidence] == ["external_proposal", "document_passage"]
    assert view.review.evidence[0].source_receipt_ids == ("read-receipt",)
    assert view.review.evidence[1].source == reference
    if changed == "source":
        sources.available = False
    else:
        token = await context.get_bean(PersonalTokenRepository).find_by_id("other")
        token.revoked_at = datetime.now(UTC)
        await context.get_bean(PersonalTokenRepository).save(token)
    with security(), pytest.raises((AccessDenied, ConflictException)):
        await service.approve("issuer|owner", "north", view.id, decision(view, challenge), "approve")
    assert (await intents.intents.find_by_id(view.id)).status == "preview"


async def test_credential_owner_tenant_and_current_authority_cannot_change(reviewed):
    from koinon.catalog.errors import AccessDenied
    from koinon.tokens.repositories import PersonalTokenRepository

    service, _, _, context = reviewed
    view, challenge = await staged(reviewed)
    for token, subject, tenant in (
        ("other", "issuer|owner", "north"),
        ("origin", "issuer|other", "north"),
        ("origin", "issuer|owner", "south"),
    ):
        with security(token), pytest.raises(AccessDenied):
            await service.approve(subject, tenant, view.id, decision(view, challenge), "approve")
    repository = context.get_bean(PersonalTokenRepository)
    token = await repository.find_by_id("origin")
    token.revoked_at = datetime.now(UTC)
    await repository.save(token)
    with security(), pytest.raises(AccessDenied):
        await service.approve("issuer|owner", "north", view.id, decision(view, challenge), "approve")


async def test_expired_challenge_and_cancelled_review_never_admit(reviewed):
    from pyfly.kernel import ConflictException

    from koinon.knowledge.external_reviews.repositories import ExternalReviewRepository

    service, _, _, context = reviewed
    view, challenge = await staged(reviewed)
    repository = context.get_bean(ExternalReviewRepository)
    row = await repository.find_by_id(view.id)
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await repository.save(row)
    with security(), pytest.raises(ConflictException):
        await service.approve("issuer|owner", "north", view.id, decision(view, challenge), "approve")


async def test_rotated_private_challenge_invalidates_previous_nonce_and_cancel_is_terminal(reviewed):
    from pyfly.kernel import ConflictException

    from koinon.catalog.errors import AccessDenied

    service, _, _, _ = reviewed
    view, old = await staged(reviewed)
    with security():
        new = await service.challenge("issuer|owner", "north", view.id)
        assert new.nonce != old.nonce
        with pytest.raises(AccessDenied):
            await service.cancel("issuer|owner", "north", view.id, decision(view, old))
        cancelled = await service.cancel("issuer|owner", "north", view.id, decision(view, new))
        assert cancelled.status == "cancelled"
        assert await service.cancel("issuer|owner", "north", view.id, decision(view, new)) == cancelled
        with pytest.raises(ConflictException):
            await service.approve("issuer|owner", "north", view.id, decision(view, new), "approve")


async def test_no_grant_and_forged_origin_are_rejected(reviewed):
    from pydantic import ValidationError

    from koinon.catalog.errors import AccessDenied

    service, _, destination, _ = reviewed
    with pytest.raises(AccessDenied):
        await service.stage("issuer|owner", "north", values(destination), "no-grant")
    with security(), pytest.raises(ValidationError):
        await service.stage(
            "issuer|owner", "north", {**values(destination), "origin": {"kind": "user_statement"}}, "forged"
        )


@pytest.mark.parametrize("uncertain", [False, True])
async def test_explicit_private_approval_reuses_one_durable_operation_and_receipt(reviewed, uncertain):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import infrastructure_unit
    from pyfly.kernel import ConflictException

    from koinon.knowledge.curated.authority import digest
    from koinon.knowledge.curated.dtos import KnowledgeCommitReceipt
    from koinon.knowledge.curated.ports import NativeCatalogProjection, NativeCommitUncertain
    from koinon.knowledge.entities import DomainBinding

    service, intents, _, context = reviewed
    view, challenge = await staged(reviewed)
    preview = view.review

    class Native:
        writes = 0
        stored = None

        async def receipt(self, *args):
            return self.stored

        async def commit(self, operation):
            self.writes += 1
            assert operation.preview.evidence[0].authority == "unverified"
            self.stored = KnowledgeCommitReceipt(
                operation_id=preview.id,
                intent_id=preview.id,
                intent_revision=preview.revision,
                authorization_digest=preview.authorization_digest,
                item_id=preview.target_item_id,
                native_item_id="native",
                native_version_id="version",
                version=1,
                action=preview.action,
                content_sha256=digest(preview.after.model_dump(mode="json")),
                evidence_sha256=digest([value.model_dump(mode="json") for value in preview.evidence]),
                committed_at=datetime.now(UTC),
                retrieval_state="not_published",
            )
            if uncertain:
                raise NativeCommitUncertain()
            return self.stored

        async def projection(self, *args):
            async with infrastructure_unit(context.get_bean(DataSourceRegistry).get("primary")) as session:
                if await session.get(DomainBinding, "alias") is None:
                    session.add(
                        DomainBinding(
                            id="alias",
                            tenant_id="north",
                            catalog_id=preview.destination.workspace_id,
                            workspace_id=preview.destination.workspace_id,
                            domain="canon",
                            entity_kind="workspace",
                            native_id="native-space",
                            native_workspace_id="native-space",
                            created_by="issuer|owner",
                        )
                    )
            return NativeCatalogProjection(
                native_workspace_id="native-space", title=preview.after.title, summary=preview.after.summary
            )

    native = Native()
    intents.native = SimpleNamespace(get=lambda: native)
    with security():
        outcome = await service.approve(
            "issuer|owner", "north", view.id, decision(view, challenge), "approve"
        )
        assert outcome.status == ("pending" if uncertain else "committed")
        outcome = await service.approve(
            "issuer|owner", "north", view.id, decision(view, challenge), "approve"
        )
        assert outcome.status == "committed" and outcome.receipt == native.stored
        assert (await service.get("issuer|owner", "north", view.id)).status == "committed"
        with pytest.raises(ConflictException):
            await service.approve(
                "issuer|owner", "north", view.id, decision(view, challenge), "different-key"
            )
    assert native.writes == 1


async def test_changed_grant_or_destination_invalidates_exact_review_before_native_commit(reviewed):
    from pyfly.kernel import ConflictException

    from koinon.catalog.errors import AccessDenied
    from koinon.catalog.service import CatalogService
    from koinon.tokens.repositories import PersonalTokenRepository

    service, intents, destination, context = reviewed
    view, challenge = await staged(reviewed)
    await context.get_bean(CatalogService).update("issuer|owner", "north", destination.id, {"name": "Moved"})
    with security(), pytest.raises(ConflictException):
        await service.approve("issuer|owner", "north", view.id, decision(view, challenge), "approve")
    assert (await intents.intents.find_by_id(view.id)).status == "preview"
    token = await context.get_bean(PersonalTokenRepository).find_by_id("origin")
    token.scopes = ["catalog:read"]
    await context.get_bean(PersonalTokenRepository).save(token)
    with security(), pytest.raises(AccessDenied):
        await service.get("issuer|owner", "north", view.id)


async def test_stage_key_cannot_replace_content_or_serialize_a_secret(reviewed):
    from pyfly.kernel import ConflictException

    from koinon.knowledge.external_reviews.dtos import ExternalReviewView

    service, _, destination, _ = reviewed
    view, _ = await staged(reviewed)
    with security(), pytest.raises(ConflictException):
        await service.stage(
            "issuer|owner",
            "north",
            {**values(destination), "content": {"title": "Changed", "body": "Replacement"}},
            "stage-1",
        )
    assert "nonce" not in ExternalReviewView.model_json_schema()["properties"]
    assert view.expires_at == view.review.expires_at


async def test_authorized_application_revocation_denies_its_existing_private_challenge(reviewed):
    from koinon.authorized_applications.entities import AuthorizedApplication
    from koinon.authorized_applications.repositories import AuthorizedApplicationRepository
    from koinon.catalog.errors import AccessDenied
    from koinon.tokens.repositories import PersonalTokenRepository

    service, _, destination, context = reviewed
    tokens = context.get_bean(PersonalTokenRepository)
    token = await tokens.find_by_id("origin")
    token.purpose, token.authorized_application_id = "application", "application"
    token.workspace_ids = [destination.workspace_id]
    applications = context.get_bean(AuthorizedApplicationRepository)
    application = AuthorizedApplication(
        id="application",
        subject="issuer|owner",
        client_id="external-client",
        name="External client",
        resource="https://koinon.example.test/mcp",
        tenant_id="north",
        tenant_name="North",
        workspace_id=destination.workspace_id,
        workspace_name="Workspace",
        scopes=token.scopes,
        connected_at=datetime.now(UTC),
        expires_at=token.expires_at,
    )
    await applications.save(application)
    await tokens.save(token)
    with security():
        view = await service.stage("issuer|owner", "north", values(destination), "application-stage")
        challenge = await service.challenge("issuer|owner", "north", view.id)
    assert view.review.evidence[0].application_id == "application"
    application.revoked_at = datetime.now(UTC)
    await applications.save(application)
    with security(), pytest.raises(AccessDenied):
        await service.approve("issuer|owner", "north", view.id, decision(view, challenge), "approve")


async def test_approval_admission_rolls_back_nonce_when_curated_admission_fails(reviewed):
    from pyfly.kernel import ConflictException

    from koinon.catalog.service import CatalogService
    from koinon.knowledge.external_reviews.repositories import ExternalReviewRepository

    service, intents, destination, context = reviewed
    view, challenge = await staged(reviewed)
    await context.get_bean(CatalogService).update(
        "issuer|owner", "north", destination.id, {"name": "Changed"}
    )
    with security(), pytest.raises(ConflictException):
        await service.approve("issuer|owner", "north", view.id, decision(view, challenge), "approve")
    row = await context.get_bean(ExternalReviewRepository).find_by_id(view.id)
    assert row.status == "preview" and row.confirmation_key is None and row.decided_at is None
    assert (await intents.intents.find_by_id(view.id)).status == "preview"
