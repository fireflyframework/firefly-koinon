# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

import pytest
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.data.transaction import TransactionTemplate

from koinon.activity.dtos import ActivityWindow
from koinon.activity.knowledge_repository import KnowledgeActivityRepository
from koinon.catalog.entities import AuditEvent, CatalogEntry, Tenant
from koinon.catalog.repositories import AuditRepository, CatalogRepository, TenantRepository
from koinon.knowledge.external_reviews.read_receipt_entities import ExternalReadReceiptRow


@pytest.fixture
async def history(tmp_path):
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "create",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'activity.db'}",
                        }
                    },
                }
            }
        )
    )
    for cls in (KnowledgeActivityRepository, TenantRepository, CatalogRepository, AuditRepository):
        context.register_bean(cls)
    await context.start()
    try:
        yield context
    finally:
        await context.stop()


async def test_committed_semantic_events_are_owner_and_tenant_scoped_without_counting_chunks(history):
    clock = datetime(2026, 10, 31, tzinfo=UTC)
    window = ActivityWindow(start_at=clock, end_at=clock + timedelta(days=1), time_zone="UTC")
    async with TransactionTemplate("primary").transaction():
        tenants = history.get_bean(TenantRepository)
        entries = history.get_bean(CatalogRepository)
        audit = history.get_bean(AuditRepository)
        for tenant in ("north", "south"):
            await tenants.save(Tenant(id=tenant, name=tenant))
        for key, kind, tenant in (
            ("doc", "document", "north"),
            ("chunk", "chunk", "north"),
            ("other", "dataset", "south"),
        ):
            await entries.save(
                CatalogEntry(id=key, tenant_id=tenant, kind=kind, name=key, created_by="issuer|owner")
            )
        for key, asset, subject, tenant in (
            ("a", "doc", "issuer|owner", "north"),
            ("b", "chunk", "issuer|owner", "north"),
            ("c", "doc", "issuer|other", "north"),
            ("d", "other", "issuer|owner", "south"),
        ):
            await audit.save(
                AuditEvent(
                    id=key,
                    resource_id=asset,
                    subject=subject,
                    tenant_id=tenant,
                    action="catalog.created",
                    created_at=clock,
                )
            )
    async with TransactionTemplate("primary", read_only=True).transaction():
        values, partial = await history.get_bean(KnowledgeActivityRepository).observations(
            "north", "issuer|owner", window
        )
        assert [(value.asset_id, value.action) for value in values] == [("doc", "created")]
        assert partial is False
        organization, _ = await history.get_bean(KnowledgeActivityRepository).observations(
            "north", None, window
        )
        assert len(organization) == 2


async def test_expired_evidence_is_retained_activity_without_loading_queries_or_private_bodies(history):
    clock = datetime(2026, 10, 31, tzinfo=UTC)
    window = ActivityWindow(start_at=clock, end_at=clock + timedelta(days=1), time_zone="UTC")
    async with TransactionTemplate("primary").transaction():
        await history.get_bean(TenantRepository).save(Tenant(id="north", name="North"))
        session = history.get_bean(KnowledgeActivityRepository)._require_session()
        for key, owner in (("receipt", "issuer|owner"), ("other", "issuer|other")):
            session.add(
                ExternalReadReceiptRow(
                    id=key,
                    tenant_id="north",
                    subject=owner,
                    credential_id="retired-credential",
                    credential_sha256="a" * 64,
                    operation="query",
                    request_sha256="b" * 64,
                    result_sha256="c" * 64,
                    sources_json=[
                        {"asset_id": "dataset", "private_extra": "must-not-be-projected"},
                        {"asset_id": "dataset"},
                    ],
                    provenance_json={"sql": "private SQL must not be projected"},
                    receipt_sha256="d" * 64,
                    created_at=clock,
                    expires_at=clock + timedelta(minutes=10),
                )
            )
    async with TransactionTemplate("primary", read_only=True).transaction():
        values, _ = await history.get_bean(KnowledgeActivityRepository).observations(
            "north", "issuer|owner", window
        )
        assert len(values) == 2
        assert all(value.asset_id == "dataset" and value.action == "consulted" for value in values)
        assert all(not hasattr(value, "provenance") for value in values)


async def test_large_history_is_bounded_and_marked_partial(history, monkeypatch):
    import koinon.activity.knowledge_repository as module

    monkeypatch.setattr(module, "HISTORY_LIMIT", 2)
    clock = datetime(2026, 10, 31, tzinfo=UTC)
    window = ActivityWindow(start_at=clock, end_at=clock + timedelta(days=1), time_zone="UTC")
    async with TransactionTemplate("primary").transaction():
        await history.get_bean(TenantRepository).save(Tenant(id="north", name="North"))
        session = history.get_bean(KnowledgeActivityRepository)._require_session()
        for index in range(3):
            session.add(
                CatalogEntry(
                    id=str(index), tenant_id="north", kind="document", name="Piece", created_by="issuer|owner"
                )
            )
            session.add(
                AuditEvent(
                    id=str(index),
                    resource_id=str(index),
                    subject="issuer|owner",
                    tenant_id="north",
                    action="catalog.created",
                    created_at=clock,
                )
            )
    async with TransactionTemplate("primary", read_only=True).transaction():
        values, partial = await history.get_bean(KnowledgeActivityRepository).observations(
            "north", "issuer|owner", window
        )
        assert partial is True and len(values) == 2


async def test_pending_and_failed_status_transitions_are_not_knowledge_updates(history):
    clock = datetime(2026, 10, 31, tzinfo=UTC)
    window = ActivityWindow(start_at=clock, end_at=clock + timedelta(days=1), time_zone="UTC")
    async with TransactionTemplate("primary").transaction():
        await history.get_bean(TenantRepository).save(Tenant(id="north", name="North"))
        await history.get_bean(CatalogRepository).save(
            CatalogEntry(
                id="dataset", tenant_id="north", kind="dataset", name="Dataset", created_by="issuer|owner"
            )
        )
        audit = history.get_bean(AuditRepository)
        for identifier in ("pending", "failed"):
            await audit.save(
                AuditEvent(
                    id=identifier,
                    tenant_id="north",
                    subject="issuer|owner",
                    resource_id="dataset",
                    action="catalog.updated",
                    details={"fields": ["status"]},
                    created_at=clock,
                )
            )
    async with TransactionTemplate("primary", read_only=True).transaction():
        values, partial = await history.get_bean(KnowledgeActivityRepository).observations(
            "north", "issuer|owner", window
        )
        assert values == [] and not partial
    async with TransactionTemplate("primary").transaction():
        await audit.save(
            AuditEvent(
                id="completed",
                tenant_id="north",
                subject="issuer|owner",
                resource_id="dataset",
                action="knowledge.content_updated",
                details={"file_version_id": "committed-version"},
                created_at=clock,
            )
        )
    async with TransactionTemplate("primary", read_only=True).transaction():
        values, _ = await history.get_bean(KnowledgeActivityRepository).observations(
            "north", "issuer|owner", window
        )
        assert [(value.asset_id, value.action) for value in values] == [("dataset", "updated")]
