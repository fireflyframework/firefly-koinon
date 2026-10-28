# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Explicit transaction publishers must not leak precommit ambient events."""

import pytest


@pytest.fixture
async def native_lifecycle(tmp_path):
    from flycanon.config import CanonSettings
    from flycanon.core.services.audit import AuditService
    from flycanon.core.services.knowledge import KnowledgeService
    from flycanon.models.entities.audit_event import AuditEventRow
    from flycanon.models.entities.citation import CitationRow
    from flycanon.models.entities.knowledge_item import KnowledgeItemRow
    from flycanon.models.entities.knowledge_version import KnowledgeVersionRow
    from flycanon.models.repositories.audit_repository import AuditRepository
    from flycanon.models.repositories.knowledge_repository import KnowledgeRepository
    from pyfly.core import Config
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.eda.adapters.database import DatabaseEventBus
    from pyfly.eda.outbox import OutboxTables

    relational = {
        "url": f"sqlite+aiosqlite:///{tmp_path / 'primary.db'}",
        "datasources": {"canon": {"url": f"sqlite+aiosqlite:///{tmp_path / 'canon.db'}"}},
    }
    registry = DataSourceRegistry.for_config(Config({"pyfly": {"data": {"relational": relational}}}))
    source = registry.get("canon")
    outbox = OutboxTables.named("canon_knowledge_outbox")
    async with source.engine.begin() as connection:
        for table in (
            KnowledgeItemRow.__table__,
            KnowledgeVersionRow.__table__,
            CitationRow.__table__,
            AuditEventRow.__table__,
            *outbox.all(),
        ):
            await connection.run_sync(table.create)

    class Ambient:
        async def publish(self, *args, **kwargs):
            pytest.fail("Canon must not publish through the ambient bus")

    settings = CanonSettings()
    audit = AuditService(AuditRepository(source.sessionmaker), Ambient(), settings)
    service = KnowledgeService(KnowledgeRepository(source.sessionmaker), audit, Ambient(), settings)
    publisher = DatabaseEventBus(
        source, tables=outbox, create_tables=False, notify=False, group="curated-test"
    )
    try:
        yield service, source, publisher, outbox
    finally:
        await registry.close()


async def test_native_lifecycle_same_unit_outbox_rolls_back_on_failure(native_lifecycle):
    from flycanon.interfaces.dtos.knowledge import CreateKnowledgeRequest
    from flycanon.interfaces.enums import Domain
    from flycanon.models.entities.knowledge_version import KnowledgeVersionRow
    from pyfly.data.transaction import infrastructure_unit
    from sqlalchemy import func, select

    service, source, publisher, outbox = native_lifecycle
    request = CreateKnowledgeRequest(
        title="Reviewed", body="Threshold47", domain=Domain.other, publish=True, actor="issuer|owner"
    )
    with pytest.raises(RuntimeError, match="after-native-write"):
        async with infrastructure_unit(source):
            await service.create(request, tenant_id="north", workspace_id="owned", event_publisher=publisher)
            raise RuntimeError("after-native-write")
    async with infrastructure_unit(source, read_only=True) as session:
        assert await session.scalar(select(func.count()).select_from(KnowledgeVersionRow)) == 0
        assert await session.scalar(select(func.count()).select_from(outbox.events)) == 0
    async with infrastructure_unit(source):
        await service.create(request, tenant_id="north", workspace_id="owned", event_publisher=publisher)
    async with infrastructure_unit(source, read_only=True) as session:
        assert await session.scalar(select(func.count()).select_from(KnowledgeVersionRow)) == 1
        assert await session.scalar(select(func.count()).select_from(outbox.events)) == 2


async def test_native_subject_512_is_preserved_in_version_audit_and_event(native_lifecycle):
    import json

    from flycanon.interfaces.dtos.knowledge import CreateKnowledgeRequest
    from flycanon.interfaces.enums import Domain
    from flycanon.models.entities.audit_event import AuditEventRow
    from flycanon.models.entities.knowledge_version import KnowledgeVersionRow
    from pydantic import ValidationError
    from pyfly.data.transaction import infrastructure_unit
    from sqlalchemy import select

    subject = "issuer|" + "s" * 505
    request = CreateKnowledgeRequest(title="Verified fact", body="47", domain=Domain.other, actor=subject)
    with pytest.raises(ValidationError):
        CreateKnowledgeRequest(title="Invalid", body="47", domain=Domain.other, actor=subject + "s")
    lifecycle, source, publisher, outbox = native_lifecycle
    async with infrastructure_unit(source):
        await lifecycle.create(request, tenant_id="north", workspace_id="owned", event_publisher=publisher)
    async with infrastructure_unit(source, read_only=True) as session:
        assert (await session.scalar(select(KnowledgeVersionRow))).created_by == subject
        assert (await session.scalar(select(AuditEventRow))).actor == subject
        payloads = list(await session.scalars(select(outbox.events.c.payload)))
        assert any(json.loads(payload).get("actor") == subject for payload in payloads)
    assert KnowledgeVersionRow.__table__.c.created_by.type.length == 512
    assert AuditEventRow.__table__.c.actor.type.length == 512
