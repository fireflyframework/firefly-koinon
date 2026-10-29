# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Owned PostgreSQL service composition; no HTTP or model-provider acceptance claim."""

import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from test_curated_source_scope_postgres import pg_scope as pg_scope

pytestmark = pytest.mark.skipif(not os.getenv("KOINON_CURATED_SCOPE_PRIMARY_URL"), reason="owned PostgreSQL")


@pytest.fixture
async def pg_curated(pg_scope, monkeypatch):
    from flycanon.config import CanonSettings
    from flycanon.core.services.audit import AuditService
    from flycanon.core.services.knowledge import KnowledgeService
    from flycanon.data import TenantGucCustomizer
    from flycanon.models.repositories.audit_repository import AuditRepository
    from flycanon.models.repositories.knowledge_repository import KnowledgeRepository
    from pyfly.agentic.models import ModelFactory
    from pyfly.container.scanner import scan_package
    from pyfly.context import ApplicationContext
    from pyfly.core import Config
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from sqlalchemy.engine import make_url
    from test_policy_runtime_scope import snapshot as knowledge_snapshot

    from koinon.catalog.entities import Membership, Tenant
    from koinon.catalog.repositories import MembershipRepository, TenantRepository
    from koinon.catalog.service import CatalogService
    from koinon.evidence.dtos import ConversationMessage, ConversationSnapshot
    from koinon.knowledge.curated.authority import CuratedAuthority
    from koinon.knowledge.curated.intents import KnowledgeIntents
    from koinon.knowledge.curated.native import NativeCuratedKnowledge
    from koinon.knowledge.evidence_sources import NativeSourceResolver
    from koinon.knowledge.repositories import DomainBindingRepository
    from koinon.knowledge.service import KnowledgeFacade, KnowledgeSettings
    from koinon.tokens.authorization import TokenRestriction
    from koinon.tokens.repositories import PersonalTokenRepository

    primary_target = make_url(os.environ["KOINON_CURATED_SCOPE_PRIMARY_URL"])
    native_target = make_url(os.environ["KOINON_CURATED_SCOPE_POSTGRES_URL"])
    if not (
        primary_target.host == native_target.host == "127.0.0.1"
        and primary_target.port == native_target.port == 18783
        and primary_target.database == native_target.database
        and (primary_target.database or "").startswith("koinon_index_qualification_curated_")
    ):
        pytest.fail("Primary consent fixtures require the same dedicated owned PostgreSQL database")

    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "none",
                            "url": os.environ["KOINON_CURATED_SCOPE_PRIMARY_URL"],
                            "datasources": {
                                "canon": {"url": os.environ["KOINON_CURATED_SCOPE_POSTGRES_URL"]}
                            },
                        }
                    },
                }
            }
        )
    )
    for package in ("koinon.catalog", "koinon.knowledge.curated"):
        scan_package(package, context.container)
    for bean in (PersonalTokenRepository, TokenRestriction, DomainBindingRepository):
        context.register_bean(bean)
    await context.start()
    registry = context.get_bean(DataSourceRegistry)
    registry.add_customizer(TenantGucCustomizer("canon"), datasource="canon")
    source = registry.get("canon")
    from pyfly.data.transaction import infrastructure_unit
    from sqlalchemy import text

    async with infrastructure_unit(registry.get("primary"), read_only=True) as session:
        assert (
            await session.execute(
                text("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")
            )
        ).one() == (False, False)

    def no_models(*args, **kwargs):
        raise AssertionError("Model calls are forbidden in curated PostgreSQL qualification")

    monkeypatch.setattr(ModelFactory, "build_with_secret", no_models)
    settings = CanonSettings()

    class NoAmbient:
        async def publish(self, *args, **kwargs):
            raise AssertionError("Only the transactional publisher may run")

    lifecycle = KnowledgeService(
        KnowledgeRepository(source.sessionmaker),
        AuditService(AuditRepository(source.sessionmaker), NoAmbient(), settings),
        NoAmbient(),
        settings,
    )
    domains = pg_scope.domains
    resolve = domains._resolve
    domains._resolve = lambda kind: lifecycle if kind is KnowledgeService else resolve(kind)
    catalog = context.get_bean(CatalogService)
    bindings = context.get_bean(DomainBindingRepository)
    facade = KnowledgeFacade(
        catalog,
        bindings,
        domains,
        KnowledgeSettings(),
        knowledge_settings=SimpleNamespace(
            snapshot=AsyncMock(side_effect=lambda subject, tenant: knowledge_snapshot(tenant))
        ),
    )
    authority = context.get_bean(CuratedAuthority)
    authority.sources = SimpleNamespace(get=lambda: NativeSourceResolver(facade, domains, registry))
    native = context.get_bean(NativeCuratedKnowledge)
    native.knowledge = SimpleNamespace(get=lambda: facade)
    subject = "qualification|owner"
    tenant = pg_scope.tenant
    await context.get_bean(TenantRepository).save(Tenant(id=tenant, name="Owned qualification"))
    await context.get_bean(MembershipRepository).save(
        Membership(id=str(uuid4()), subject=subject, tenant_id=tenant, role="editor")
    )
    destinations = []
    workspaces = []
    for label, native_workspace in (
        ("Source", pg_scope.binding.native_workspace_id),
        ("Destination", pg_scope.workspace),
    ):
        parent = None
        for kind in ("workspace", "project", "collection"):
            parent = await catalog.create(
                subject, tenant, kind=kind, name=label + " " + kind, parent_id=parent.id if parent else None
            )
            if kind == "workspace":
                workspaces.append(parent)
                await facade._bind(subject, tenant, parent, "canon", native_workspace, native_workspace)
        destinations.append(parent)
    parent = destinations[0]
    for kind in ("source", "document"):
        parent = await catalog.create(
            subject, tenant, kind=kind, name="Controlled " + kind, parent_id=parent.id
        )
    await facade._bind(
        subject, tenant, parent, "canon", pg_scope.binding.native_id, pg_scope.binding.native_workspace_id
    )
    reference = pg_scope.reference.model_copy(update={"asset_id": parent.id, "source_id": parent.parent_id})
    snapshot = ConversationSnapshot(
        thread_id=str(uuid4()),
        tenant_id=tenant,
        owner_subject=subject,
        title="Controlled conversation evidence",
        revision="a" * 64,
        source_manifest_complete=True,
        sources=(reference,),
        messages=(
            ConversationMessage(
                id="answer",
                role="assistant",
                text=reference.quote,
                status="completed",
                revision="a" * 64,
                source_ids=(reference.id,),
            ),
        ),
    )

    class Snapshots:
        async def snapshot(self, *args):
            return snapshot

    authority.snapshots = SimpleNamespace(get=lambda: Snapshots())
    try:
        yield SimpleNamespace(
            context=context,
            registry=registry,
            service=context.get_bean(KnowledgeIntents),
            native=native,
            facade=facade,
            authority=authority,
            tenant=tenant,
            subject=subject,
            source_destination=destinations[0],
            destination=destinations[1],
            source_asset=parent,
            workspaces=workspaces,
            snapshot=snapshot,
            reference=reference,
        )
    finally:
        await context.stop()


async def test_postgres_exact_consent_native_commit_ack_reconciliation_and_published_body(pg_curated):
    from pyfly.data.transaction import infrastructure_unit
    from sqlalchemy import func, select

    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.adapters import native_scope
    from koinon.knowledge.curated.corpus import CuratedBodyCorpus
    from koinon.knowledge.curated.domain_entities import CuratedCommitRow, CuratedVersionChunkRow
    from koinon.knowledge.curated.dtos import PendingKnowledgeCommit
    from koinon.knowledge.curated.ports import NativeCommitUncertain
    from koinon.knowledge.curated.reads import CuratedKnowledgeReads

    fixture = pg_curated
    service = fixture.service
    request = {
        "action": "create_published",
        "destination_id": fixture.destination.id,
        "content": {"title": "Reviewed rule", "body": fixture.reference.quote},
        "origin": {
            "kind": "conversation",
            "thread_id": fixture.snapshot.thread_id,
            "message_ids": ["answer"],
        },
    }
    preview = await service.preview(fixture.subject, fixture.tenant, request)
    confirmation = {
        "confirm": True,
        "expected_revision": preview.revision,
        "authorization_digest": preview.authorization_digest,
    }
    # Simulate a lost acknowledgement only after the real native COMMIT returns.
    actual_commit = fixture.native.commit
    calls = []

    async def lost_ack(operation):
        receipt = await actual_commit(operation)
        calls.append(receipt)
        raise NativeCommitUncertain()

    fixture.native.commit = lost_ack
    pending = await service.confirm(fixture.subject, fixture.tenant, preview.id, confirmation, "exact-review")
    assert isinstance(pending, PendingKnowledgeCommit) and len(calls) == 1
    receipt = calls[0]
    assert (
        await fixture.native.receipt(
            fixture.subject, fixture.tenant, preview.id, preview.authorization_digest
        )
        == receipt
    )
    assert await service.reconcile(fixture.subject, fixture.tenant, preview.id)
    result = await service.confirm(fixture.subject, fixture.tenant, preview.id, confirmation, "exact-review")
    assert result.receipt == receipt and len(calls) == 1
    reads = fixture.context.get_bean(CuratedKnowledgeReads)
    body = await reads.version(fixture.subject, fixture.tenant, receipt.item_id)
    assert body.selected_version.content == preview.after
    corpus = fixture.context.get_bean(CuratedBodyCorpus)
    admitted = await corpus.admit(fixture.subject, fixture.tenant, [receipt.item_id])
    binding = await fixture.facade.binding(fixture.tenant, fixture.destination.workspace_id, "canon")
    hits = await corpus.search(
        fixture.subject, fixture.tenant, binding.native_id, admitted, query="threshold", limit=10
    )
    assert len(hits) == 1 and hits[0].content == preview.after.body
    with native_scope("canon", fixture.tenant, binding.native_id, fixture.subject):
        async with infrastructure_unit(fixture.registry.get("canon"), read_only=True) as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(CuratedCommitRow)
                    .where(CuratedCommitRow.operation_id == preview.id)
                )
                == 1
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(CuratedVersionChunkRow)
                    .where(CuratedVersionChunkRow.native_version_id == receipt.native_version_id)
                )
                == 1
            )
    with pytest.raises(AccessDenied):
        await reads.version("qualification|foreign", fixture.tenant, receipt.item_id)


async def test_postgres_real_workspace_read_and_write_denials(pg_curated):
    from koinon.catalog.entities import Membership
    from koinon.catalog.errors import AccessDenied
    from koinon.catalog.repositories import MembershipRepository
    from koinon.knowledge.curated.dtos import DocumentEvidence

    fixture = pg_curated
    memberships = fixture.context.get_bean(MembershipRepository)
    restricted = "qualification|destination-only"
    await memberships.save(
        Membership(
            id=str(uuid4()),
            subject=restricted,
            tenant_id=fixture.tenant,
            role="editor",
            workspace_id=fixture.destination.workspace_id,
        )
    )
    await fixture.authority.destination(restricted, fixture.tenant, fixture.destination.id)
    with pytest.raises(AccessDenied):
        await fixture.authority.evidence(
            restricted,
            fixture.tenant,
            (DocumentEvidence(source=fixture.reference),),
        )
    viewer = "qualification|viewer"
    await memberships.save(
        Membership(
            id=str(uuid4()),
            subject=viewer,
            tenant_id=fixture.tenant,
            role="viewer",
            workspace_id=fixture.destination.workspace_id,
        )
    )
    await fixture.authority.destination(viewer, fixture.tenant, fixture.destination.id, write=False)
    with pytest.raises(AccessDenied):
        await fixture.service.preview(
            viewer,
            fixture.tenant,
            {
                "action": "create_published",
                "destination_id": fixture.destination.id,
                "content": {"title": "Denied", "body": "Denied"},
                "origin": {"kind": "user_statement"},
            },
        )


async def test_postgres_revoked_origin_pat_denies_confirmation_and_leaves_no_native_claim(pg_curated):
    from pyfly.data.transaction import infrastructure_unit
    from pyfly.security.context import SecurityContext
    from pyfly.security.context_holder import SecurityContextHolder
    from sqlalchemy import func, select

    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.adapters import native_scope
    from koinon.knowledge.curated.domain_entities import CuratedCommitRow
    from koinon.tokens.entities import PersonalToken
    from koinon.tokens.repositories import PersonalTokenRepository

    fixture = pg_curated
    repository = fixture.context.get_bean(PersonalTokenRepository)
    token = PersonalToken(
        id=str(uuid4()),
        subject=fixture.subject,
        tenant_id=fixture.tenant,
        name="Controlled origin",
        token_hash="a" * 64,
        prefix="qualification",
        scopes=["catalog:read", "catalog:write", "ingest:write", "knowledge:search"],
        workspace_ids=[workspace.id for workspace in fixture.workspaces],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    await repository.save(token)
    request = {
        "action": "create_published",
        "destination_id": fixture.destination.id,
        "content": {"title": "Reviewed", "body": fixture.reference.quote},
        "origin": {
            "kind": "conversation",
            "thread_id": fixture.snapshot.thread_id,
            "message_ids": ["answer"],
        },
    }
    with SecurityContextHolder.using(
        SecurityContext(
            user_id="owner", attributes={"iss": "qualification", "sub": "owner", "koinon_token_id": token.id}
        )
    ):
        preview = await fixture.service.preview(fixture.subject, fixture.tenant, request)
    token.revoked_at = datetime.now(UTC)
    await repository.save(token)
    with pytest.raises(AccessDenied):
        await fixture.service.confirm(
            fixture.subject,
            fixture.tenant,
            preview.id,
            {
                "confirm": True,
                "expected_revision": preview.revision,
                "authorization_digest": preview.authorization_digest,
            },
            "revoked-origin",
        )
    binding = await fixture.facade.binding(fixture.tenant, fixture.destination.workspace_id, "canon")
    with native_scope("canon", fixture.tenant, binding.native_id, fixture.subject):
        async with infrastructure_unit(fixture.registry.get("canon"), read_only=True) as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(CuratedCommitRow)
                    .where(CuratedCommitRow.operation_id == preview.id)
                )
                == 0
            )


async def test_postgres_final_source_change_rolls_back_claim_and_content(pg_curated):
    from flycanon.models.entities.knowledge_item import KnowledgeItemRow
    from flycanon.models.entities.source_lineage import source_extractions, source_heads, source_versions
    from pyfly.data.transaction import infrastructure_unit, outside_transaction
    from pyfly.kernel import ConflictException
    from sqlalchemy import func, insert, select, update

    from koinon.knowledge.adapters import native_scope
    from koinon.knowledge.curated.domain_entities import CuratedCommitRow

    fixture = pg_curated
    preview = await fixture.service.preview(
        fixture.subject,
        fixture.tenant,
        {
            "action": "create_published",
            "destination_id": fixture.destination.id,
            "content": {"title": "Reviewed", "body": fixture.reference.quote},
            "origin": {
                "kind": "conversation",
                "thread_id": fixture.snapshot.thread_id,
                "message_ids": ["answer"],
            },
        },
    )
    admitted = fixture.native.admitted
    source_binding = await fixture.facade.binding(fixture.tenant, fixture.source_asset.id, "canon")
    calls = 0

    async def changed_source(operation):
        nonlocal calls
        calls += 1
        if calls == 3:
            with (
                outside_transaction(),
                native_scope(
                    "canon",
                    fixture.tenant,
                    source_binding.native_workspace_id,
                    fixture.subject,
                ),
            ):
                async with infrastructure_unit(fixture.registry.get("canon")) as session:
                    prior = (
                        (
                            await session.execute(
                                select(source_versions).where(
                                    source_versions.c.id == fixture.reference.source_version_id
                                )
                            )
                        )
                        .mappings()
                        .one()
                    )
                    ingestion = (
                        (
                            await session.execute(
                                select(source_extractions).where(
                                    source_extractions.c.version_id == prior["id"],
                                    source_extractions.c.purpose == "ingestion",
                                )
                            )
                        )
                        .mappings()
                        .one()
                    )
                    version, extraction = str(uuid4()), str(uuid4())
                    await session.execute(
                        insert(source_versions).values(
                            **{
                                **dict(prior),
                                "id": version,
                                "operation_id": str(uuid4()),
                                "predecessor_id": prior["id"],
                            }
                        )
                    )
                    await session.execute(
                        insert(source_extractions).values(
                            **{
                                **dict(ingestion),
                                "id": extraction,
                                "version_id": version,
                                "predecessor_id": ingestion["id"],
                            }
                        )
                    )
                    await session.execute(
                        update(source_heads)
                        .where(source_heads.c.source_id == prior["source_id"])
                        .values(version_id=version, extraction_id=extraction)
                    )
        return await admitted(operation)

    fixture.native.admitted = changed_source
    with pytest.raises(ConflictException) as failure:
        await fixture.service.confirm(
            fixture.subject,
            fixture.tenant,
            preview.id,
            {
                "confirm": True,
                "expected_revision": preview.revision,
                "authorization_digest": preview.authorization_digest,
            },
            "source-changed",
        )
    assert failure.value.code == "KNOWLEDGE_SOURCE_CHANGED" and calls == 3
    binding = await fixture.facade.binding(fixture.tenant, fixture.destination.workspace_id, "canon")
    with native_scope("canon", fixture.tenant, binding.native_id, fixture.subject):
        async with infrastructure_unit(fixture.registry.get("canon"), read_only=True) as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(CuratedCommitRow)
                    .where(CuratedCommitRow.operation_id == preview.id)
                )
                == 0
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(KnowledgeItemRow)
                    .where(KnowledgeItemRow.title == "Reviewed")
                )
                == 0
            )


async def test_postgres_authorized_null_summary_draft_preserves_published_body(pg_curated):
    from koinon.knowledge.curated.reads import CuratedKnowledgeReads

    fixture = pg_curated

    async def confirmed(request, key):
        preview = await fixture.service.preview(fixture.subject, fixture.tenant, request)
        result = await fixture.service.confirm(
            fixture.subject,
            fixture.tenant,
            preview.id,
            {
                "confirm": True,
                "expected_revision": preview.revision,
                "authorization_digest": preview.authorization_digest,
            },
            key,
        )
        return preview, result.receipt

    published, first = await confirmed(
        {
            "action": "create_published",
            "destination_id": fixture.destination.id,
            "content": {
                "title": "Reviewed summary",
                "body": "Published threshold 47",
                "summary": "Old summary",
            },
            "origin": {"kind": "user_statement"},
        },
        "publish-summary",
    )
    draft, second = await confirmed(
        {
            "action": "update_draft",
            "destination_id": fixture.destination.id,
            "target_item_id": first.item_id,
            "expected_version": 1,
            "content": {"title": "Reviewed summary", "body": "Draft threshold 48", "summary": None},
            "origin": {"kind": "user_statement"},
        },
        "clear-draft-summary",
    )
    assert second.version == 2 and second.serving_version == 1
    reads = fixture.context.get_bean(CuratedKnowledgeReads)
    current = await reads.version(fixture.subject, fixture.tenant, first.item_id)
    saved_draft = await reads.version(fixture.subject, fixture.tenant, first.item_id, 2)
    assert current.selected_version.content == published.after
    assert saved_draft.selected_version.content == draft.after
    assert saved_draft.selected_version.content.summary is None
