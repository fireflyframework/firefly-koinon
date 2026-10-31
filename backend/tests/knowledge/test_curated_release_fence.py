# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""A final set observation rejects changes to earlier selections while later checks await."""

from types import SimpleNamespace

import pytest
from test_curated_intents import curated as curated
from test_curated_intents import input_for
from test_curated_native_commit import transaction_fixture
from test_curated_native_events import native_lifecycle as native_lifecycle


async def _two_workspace_case(curated, native_lifecycle):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import infrastructure_unit
    from sqlalchemy import delete

    from koinon.catalog.entities import Membership
    from koinon.catalog.repositories import MembershipRepository
    from koinon.knowledge.curated.acknowledgement import CatalogAcknowledgement
    from koinon.knowledge.curated.corpus import CuratedBodyCorpus
    from koinon.knowledge.curated.ports import NativeCatalogProjection, NativeKnowledgeOperation
    from koinon.knowledge.curated.reads import CuratedKnowledgeReads
    from koinon.knowledge.entities import DomainBinding

    service, destination, unit = await transaction_fixture(curated, native_lifecycle)
    _, catalog, _, context = curated
    other = None
    for kind in ("workspace", "project", "collection"):
        other = await catalog.create(
            "issuer|owner", "north", kind=kind, name="Other " + kind, parent_id=other.id if other else None
        )
    primary = context.get_bean(DataSourceRegistry).get("primary")
    async with infrastructure_unit(primary) as session:
        for ordinal, target in enumerate((destination, other)):
            session.add(
                DomainBinding(
                    id="workspace-alias-" + str(ordinal),
                    tenant_id="north",
                    catalog_id=target.workspace_id,
                    workspace_id=target.workspace_id,
                    domain="canon",
                    entity_kind="workspace",
                    native_id="owned",
                    native_workspace_id="owned",
                    created_by="issuer|owner",
                )
            )
    published = []
    acknowledgement = context.get_bean(CatalogAcknowledgement)
    for target in (destination, other):
        preview = await service.preview("issuer|owner", "north", input_for(target, action="create_published"))
        receipt = await unit.commit(NativeKnowledgeOperation(preview, ()), native_workspace_id="owned")
        await acknowledgement.apply(
            preview,
            receipt,
            NativeCatalogProjection(
                native_workspace_id="owned",
                title=preview.after.title,
                serving_version_id=receipt.native_version_id,
                serving_operation_id=receipt.operation_id,
            ),
        )
        published.append(receipt)
    async with primary.engine.begin() as connection:
        await connection.execute(delete(Membership).where(Membership.id == "reader"))
    members = context.get_bean(MembershipRepository)
    for ordinal, target in enumerate((destination, other)):
        await members.save(
            Membership(
                id="reader-" + str(ordinal),
                subject="issuer|reader",
                tenant_id="north",
                workspace_id=target.workspace_id,
                role="viewer",
            )
        )
    reads = context.get_bean(CuratedKnowledgeReads)
    reads.native = SimpleNamespace(datasource=lambda: native_lifecycle[1])
    corpus = context.get_bean(CuratedBodyCorpus)
    selected = await corpus.admit("issuer|reader", "north", [row.item_id for row in published])
    return reads, corpus, selected, published, primary


async def test_later_version_check_cannot_release_an_earlier_revoked_workspace(curated, native_lifecycle):
    from sqlalchemy import delete

    from koinon.catalog.entities import Membership
    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.capture_receipt import NativeEvidenceReceipt

    reads, corpus, selected, published, primary = await _two_workspace_case(curated, native_lifecycle)
    original = reads.version
    second_calls = 0

    async def version_then_revoke(subject, tenant, item, version=None):
        nonlocal second_calls
        value = await original(subject, tenant, item, version)
        if item == published[1].item_id:
            second_calls += 1
            if second_calls == 2:
                async with primary.engine.begin() as connection:
                    await connection.execute(delete(Membership).where(Membership.id == "reader-0"))
        return value

    reads.version = version_then_revoke
    capture = NativeEvidenceReceipt("issuer|reader", "north")
    with pytest.raises(AccessDenied) as caught:
        await corpus.search(
            "issuer|reader", "north", "owned", selected, query="threshold", limit=10, _capture=capture
        )
    assert caught.value.code == "KNOWLEDGE_AUTHORITY_CHANGED"
    assert second_calls == 2 and not capture.knowledge_sources and not capture.native_reads


async def test_database_time_expiry_changes_authority_without_mutating_credential_rows(curated):
    import asyncio
    from datetime import UTC, datetime, timedelta

    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import infrastructure_unit
    from pyfly.security.context import SecurityContext
    from pyfly.security.context_holder import SecurityContextHolder
    from sqlalchemy import select

    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.curated.release import CuratedReleaseFence
    from koinon.tokens.entities import PersonalToken

    context = curated[3]
    primary = context.get_bean(DataSourceRegistry).get("primary")
    expires = datetime.now(UTC) + timedelta(seconds=1)
    async with infrastructure_unit(primary) as session:
        session.add(
            PersonalToken(
                id="expiring",
                subject="issuer|reader",
                tenant_id="north",
                name="Owned test",
                token_hash="not-a-secret",
                prefix="fixture",
                scopes=["catalog:read", "knowledge:search"],
                expires_at=expires,
            )
        )
    fence = context.get_bean(CuratedReleaseFence)
    with SecurityContextHolder.using(
        SecurityContext(user_id="reader", attributes={"koinon_token_id": "expiring"})
    ):
        stamp = await fence.observe("issuer|reader", "north", ())
        await asyncio.sleep(1.05)
        with pytest.raises(AccessDenied) as caught:
            await fence.require_unchanged("issuer|reader", "north", (), stamp)
        assert caught.value.code == "KNOWLEDGE_AUTHORITY_CHANGED"
    async with infrastructure_unit(primary, read_only=True) as session:
        token = await session.scalar(select(PersonalToken).where(PersonalToken.id == "expiring"))
        assert token.expires_at == expires and token.revoked_at is None


async def test_primary_fence_uses_requires_new_even_inside_stale_owner_read_unit(curated):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import infrastructure_unit
    from sqlalchemy import delete

    from koinon.catalog.entities import Membership
    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.curated.release import CuratedReleaseFence

    context = curated[3]
    primary = context.get_bean(DataSourceRegistry).get("primary")
    fence = context.get_bean(CuratedReleaseFence)
    async with infrastructure_unit(primary, read_only=True):
        stamp = await fence.observe("issuer|reader", "north", ())
        async with primary.engine.begin() as connection:
            await connection.execute(delete(Membership).where(Membership.id == "reader"))
        with pytest.raises(AccessDenied):
            await fence.require_unchanged("issuer|reader", "north", (), stamp)


@pytest.mark.parametrize(
    "change",
    ["item", "ancestor", "source", "state", "binding", "root", "token", "application", "registration"],
)
async def test_one_primary_observation_covers_every_selected_authority_dependency(curated, change):
    from datetime import UTC, datetime, timedelta

    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import infrastructure_unit
    from pyfly.security.context import SecurityContext
    from pyfly.security.context_holder import SecurityContextHolder
    from sqlalchemy import update

    from koinon.authorized_applications.entities import AuthorizedApplication
    from koinon.catalog.entities import CatalogEntry
    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.curated.entities import CuratedCatalogState, CuratedSourceRoot
    from koinon.knowledge.curated.release import CuratedReleaseFence
    from koinon.knowledge.entities import DomainBinding
    from koinon.mcp_applications.entities import McpOAuthClientRegistration
    from koinon.tokens.entities import PersonalToken

    _, catalog, destination, context = curated
    source_parent = await catalog.create(
        "issuer|owner", "north", kind="source", name="Root source", parent_id=destination.id
    )
    source = await catalog.create(
        "issuer|owner", "north", kind="document", name="Root document", parent_id=source_parent.id
    )
    primary = context.get_bean(DataSourceRegistry).get("primary")
    now = datetime.now(UTC)
    async with infrastructure_unit(primary) as session:
        session.add_all(
            [
                CatalogEntry(
                    id="fixture-item",
                    tenant_id="north",
                    workspace_id=destination.workspace_id,
                    project_id=destination.project_id,
                    parent_id=destination.id,
                    kind="knowledge_item",
                    name="Owned fixture",
                    created_by="issuer|owner",
                ),
                CuratedCatalogState(
                    item_id="fixture-item",
                    tenant_id="north",
                    workspace_id=destination.workspace_id,
                    native_item_id="native-item",
                    native_workspace_id="owned",
                    head_version=1,
                    head_version_id="v1",
                    head_operation_id="op",
                    serving_version=1,
                    serving_version_id="v1",
                    serving_operation_id="op",
                    root_count=1,
                ),
                CuratedSourceRoot(
                    id="fixture-root",
                    tenant_id="north",
                    item_id="fixture-item",
                    native_version_id="v1",
                    source_asset_id=source.id,
                ),
                DomainBinding(
                    id="fixture-binding",
                    tenant_id="north",
                    catalog_id="fixture-item",
                    workspace_id=destination.workspace_id,
                    domain="canon",
                    entity_kind="knowledge_item",
                    native_id="native-item",
                    native_workspace_id="owned",
                    created_by="issuer|owner",
                ),
                McpOAuthClientRegistration(
                    id="fixture-reg",
                    tenant_id="north",
                    client_id="client",
                    name="Owned fixture",
                    client_type="public",
                    redirect_uris=["https://example.invalid/callback"],
                    scopes=["knowledge:search"],
                    enabled=True,
                    revision=1,
                    created_by="issuer|owner",
                    updated_by="issuer|owner",
                    created_at=now,
                    updated_at=now,
                ),
                AuthorizedApplication(
                    id="fixture-app",
                    subject="issuer|reader",
                    client_id="client",
                    name="Owned fixture",
                    resource="https://example.invalid/mcp",
                    tenant_id="north",
                    tenant_name="North",
                    workspace_id=destination.workspace_id,
                    workspace_name="Workspace",
                    scopes=["knowledge:search"],
                    client_registration={"id": "fixture-reg", "revision": 1},
                    connected_at=now,
                    expires_at=now + timedelta(hours=1),
                ),
                PersonalToken(
                    id="fixture-token",
                    subject="issuer|reader",
                    tenant_id="north",
                    name="Owned fixture",
                    token_hash="not-a-secret",
                    prefix="fixture",
                    purpose="application",
                    authorized_application_id="fixture-app",
                    scopes=["knowledge:search"],
                    workspace_ids=[destination.workspace_id],
                    expires_at=now + timedelta(hours=1),
                ),
            ]
        )
    fence = context.get_bean(CuratedReleaseFence)
    with SecurityContextHolder.using(
        SecurityContext(user_id="reader", attributes={"koinon_token_id": "fixture-token"})
    ):
        stamp = await fence.observe("issuer|reader", "north", ("fixture-item",))
        mutations = {
            "item": update(CatalogEntry).where(CatalogEntry.id == "fixture-item").values(status="archived"),
            "ancestor": update(CatalogEntry)
            .where(CatalogEntry.id == destination.id)
            .values(status="archived"),
            "source": update(CatalogEntry).where(CatalogEntry.id == source.id).values(status="archived"),
            "state": update(CuratedCatalogState)
            .where(CuratedCatalogState.item_id == "fixture-item")
            .values(serving_version_id="v2"),
            "binding": update(DomainBinding)
            .where(DomainBinding.id == "fixture-binding")
            .values(native_id="different"),
            "root": update(CuratedSourceRoot)
            .where(CuratedSourceRoot.id == "fixture-root")
            .values(source_asset_id=source_parent.id),
            "token": update(PersonalToken).where(PersonalToken.id == "fixture-token").values(revoked_at=now),
            "application": update(AuthorizedApplication)
            .where(AuthorizedApplication.id == "fixture-app")
            .values(revoked_at=now),
            "registration": update(McpOAuthClientRegistration)
            .where(McpOAuthClientRegistration.id == "fixture-reg")
            .values(enabled=False),
        }
        async with primary.engine.begin() as connection:
            await connection.execute(mutations[change])
        with pytest.raises(AccessDenied) as caught:
            await fence.require_unchanged("issuer|reader", "north", ("fixture-item",), stamp)
        assert caught.value.code == "KNOWLEDGE_AUTHORITY_CHANGED"


async def test_evidence_capture_rechecks_after_all_awaited_source_validation():
    from hashlib import sha256

    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.evidence_capture import NativeEvidenceDenied, NativeKnowledgeEvidence

    events = []

    class Knowledge:
        async def search(self, subject, tenant, **arguments):
            receipt = arguments["_capture"]
            receipt.knowledge_read(
                tenant,
                "native",
                "reader",
                "canonical",
                SimpleNamespace(
                    metadata={
                        "canonical_knowledge_item_id": "item",
                        "knowledge_version_id": "v1",
                        "source_title": "Reviewed",
                    },
                    source_id="native-item",
                    knowledge_version=1,
                    chunk_id="part",
                    content="Private source body",
                ),
                sha256(b"content").hexdigest(),
            )

            async def final_authority():
                events.append("final")
                raise AccessDenied("Revoked before release", code="ACCESS_DENIED")

            receipt.authorize_knowledge = final_authority
            return {
                "hits": [
                    {
                        "id": "part",
                        "asset_id": "item",
                        "source_id": None,
                        "text": "Private source body",
                        "knowledge_version_id": "v1",
                    }
                ]
            }

        async def _chain(self, *args):
            events.append("chain")
            return [SimpleNamespace(id="item", kind="knowledge_item", workspace_id="canonical")]

    with pytest.raises(NativeEvidenceDenied) as caught:
        await NativeKnowledgeEvidence(Knowledge(), None).search("reader", "north", question="Private source")
    assert events == ["chain", "chain", "final"]
    assert caught.value.capture.data == {} and not caught.value.capture.complete


@pytest.mark.parametrize("operation", ["search", "authorize_release"])
async def test_cached_outer_role_cannot_authorize_after_revocation_before_first_stamp(
    curated, native_lifecycle, operation
):
    from pyfly.data.transaction import infrastructure_unit
    from sqlalchemy import update

    from koinon.catalog.entities import Membership
    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.capture_receipt import NativeEvidenceReceipt

    _, corpus, selected, _, primary = await _two_workspace_case(curated, native_lifecycle)
    capture = NativeEvidenceReceipt("issuer|reader", "north")
    async with infrastructure_unit(primary, read_only=True) as session:
        cached = await session.get(Membership, "reader-0")
        assert cached.role == "viewer"
        async with primary.engine.begin() as connection:
            await connection.execute(
                update(Membership).where(Membership.id == "reader-0").values(role="revoked")
            )
        assert cached.role == "viewer"
        with pytest.raises(AccessDenied):
            if operation == "search":
                await corpus.search(
                    "issuer|reader", "north", "owned", selected, query="threshold", limit=10, _capture=capture
                )
            else:
                await corpus.authorize_release("issuer|reader", "north", selected)
    assert not capture.knowledge_sources and not capture.native_reads
