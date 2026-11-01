# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Real native repository/ledger roundtrips; external provider/native-domain ports remain inert."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.data.relational.sqlalchemy import Base
from pyfly.data.transaction import TransactionTemplate
from sqlalchemy import create_engine
from test_installation_manifest import example

from koinon.assistants.entities import Provider
from koinon.assistants.repositories import ProviderRepository
from koinon.catalog.entities import AuditEvent, CatalogEntry, Tenant
from koinon.catalog.repositories import (
    AuditRepository,
    CatalogRepository,
    MembershipRepository,
    TenantRepository,
)
from koinon.catalog.service import CatalogService
from koinon.communications.entities import InstallationRecord
from koinon.installation.authority import InstallationAdmissions
from koinon.installation.dtos import InstallationPlan
from koinon.installation.entities import InstallationRun
from koinon.installation.indexes import NativeInstallationIndexes
from koinon.installation.repositories import InstallationRepository
from koinon.installation.writes import NativeInstallationWrites, resource_id
from koinon.knowledge.entities import DomainBinding
from koinon.knowledge.indexes.entities import KnowledgeIndex
from koinon.knowledge.indexes.planner import IndexPlanner
from koinon.knowledge.indexes.repositories import KnowledgeIndexRepository
from koinon.knowledge.repositories import DomainBindingRepository


@pytest.fixture
async def persisted_indexes(tmp_path, monkeypatch):
    path = tmp_path / "intent.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(
        engine,
        tables=[
            Tenant.__table__,
            InstallationRecord.__table__,
            InstallationRun.__table__,
            CatalogEntry.__table__,
            AuditEvent.__table__,
            Provider.__table__,
            KnowledgeIndex.__table__,
            DomainBinding.__table__,
        ],
    )
    engine.dispose()
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "none",
                            "url": f"sqlite+aiosqlite:///{path}",
                        }
                    },
                }
            }
        )
    )
    for bean in (
        TenantRepository,
        MembershipRepository,
        CatalogRepository,
        AuditRepository,
        ProviderRepository,
        KnowledgeIndexRepository,
        DomainBindingRepository,
        InstallationRepository,
        InstallationAdmissions,
    ):
        context.register_bean(bean)
    await context.start()
    try:
        get = context.get_bean
        admissions = get(InstallationAdmissions)
        # Only this SQLite fixture supplies the PostgreSQL operator capability.
        monkeypatch.setattr(admissions.runs, "operator_capable", AsyncMock(return_value=True))
        await get(TenantRepository).save(Tenant(id="example", name="Example"))
        plan = InstallationPlan.model_validate(example())
        permit = await admissions.admit(plan, resume=False)
        async with TransactionTemplate("primary").transaction():
            for value in plan.providers:
                row = await get(ProviderRepository).save(
                    Provider(
                        id=resource_id(permit, "provider:" + value.key),
                        tenant_id="example",
                        name=value.name,
                        kind=value.kind,
                        api=value.api,
                        base_url=value.base_url,
                        model_ids=value.model_ids,
                    )
                )
                await admissions.checkpoint(
                    permit,
                    "provider:" + value.key,
                    {"status": "done", "resource_id": row.id, "revision": row.revision},
                )
        catalog = CatalogService(
            get(TenantRepository), get(MembershipRepository), get(CatalogRepository), get(AuditRepository)
        )
        writes = NativeInstallationWrites(
            admissions, Mock(), SimpleNamespace(get=lambda: catalog), Mock(), Mock()
        )
        for key in plan.catalog_order():
            await writes.catalog_node(permit, next(value for value in plan.catalog if value.key == key))
        planner = IndexPlanner(get(ProviderRepository), Mock(), Mock())

        async def prepare(tenant, value):
            return await planner.provider(tenant, value.provider_id, value.model_id), {
                "dimensions": 1536,
                "storage_dimensions": 1536,
            }

        monkeypatch.setattr(planner, "prepare", prepare)
        adapter = AsyncMock()
        adapter.workspace_exists.return_value = False
        adapter.overview.return_value = {"active_native_id": None, "chunk_count": 0}
        adapter.discover.return_value = {"items": [], "total": 0}
        reader = SimpleNamespace(
            records=get(KnowledgeIndexRepository),
            planner=planner,
            adapter=adapter,
            facade=SimpleNamespace(catalog=catalog, bindings=get(DomainBindingRepository)),
            connections=SimpleNamespace(selected=AsyncMock(return_value=None)),
        )
        writer = NativeInstallationIndexes(admissions, SimpleNamespace(get=lambda: reader))
        yield SimpleNamespace(
            context=context,
            admissions=admissions,
            plan=plan,
            permit=permit,
            value=plan.indexes[0],
            writer=writer,
            reader=reader,
            catalog=catalog,
        )
    finally:
        await context.stop()


async def test_new_intent_checkpoints_managed_revision_from_actual_repository(persisted_indexes):
    state = persisted_indexes
    identifier = await state.writer.intent(state.permit, state.value)
    row = await state.reader.records.find_by_id(identifier)
    receipt = await state.admissions.receipt(state.permit)
    assert row.revision == 1
    assert receipt["checkpoints"]["index-intent:" + state.value.key]["revision"] == 1
    async with TransactionTemplate("primary").transaction():
        assert (await state.writer.owned(state.permit, state.value))[2].id == identifier


async def legacy_intent(state, *, original_changes=None):
    from hashlib import sha256
    from json import dumps

    from koinon.installation.authority import ACTOR
    from koinon.knowledge.connections.service import embedding_fingerprint
    from koinon.knowledge.indexes.adapters import index_id

    workspace = resource_id(state.permit, "catalog:" + state.value.workspace_key)
    native = "es-" + resource_id(state.permit, "index:" + state.value.key).replace("-", "")
    identifier = index_id("example", workspace, "documents", native)
    async with TransactionTemplate("primary").transaction():
        provider = await state.reader.planner.provider(
            "example", resource_id(state.permit, "provider:" + state.value.provider_key), state.value.model_id
        )
        transient = KnowledgeIndex(
            id=identifier,
            tenant_id="example",
            workspace_id=workspace,
            native_workspace_id=workspace,
            domain="documents",
            native_id=native,
            provider_id=provider.id,
            provider_kind=provider.kind,
            provider_revision=provider.revision,
            model_id=state.value.model_id,
            dimensions=1536,
            storage_dimensions=1536,
            embedding_fingerprint=embedding_fingerprint(provider, state.value.model_id, 1536, 1536),
            build_slot=sha256(dumps(["example", "documents", workspace]).encode()).hexdigest(),
            status="queued",
            cursor={},
            transition={},
            created_by=ACTOR,
            updated_by=ACTOR,
        )
        managed = await state.reader.records.save(transient)
        assert managed is not transient
        assert managed.revision == 1 and transient.revision is None
        await state.admissions.checkpoint(
            state.permit,
            "index-intent:" + state.value.key,
            {
                "status": "done",
                "resource_id": identifier,
                "dimensions": 1536,
                "revision": transient.revision,
                "row_status": "queued",
                **(original_changes or {}),
            },
        )
    return identifier


async def resumed(state):
    await state.admissions.fail(state.permit)
    return await state.admissions.admit(state.plan, resume=True)


async def test_explicit_resume_appends_reconciliation_preserving_original_null(persisted_indexes):
    from koinon.catalog.repositories import AuditRepository

    state = persisted_indexes
    identifier = await legacy_intent(state)
    permit = await resumed(state)
    assert await state.writer.intent(permit, state.value) == identifier
    receipt = await state.admissions.receipt(permit)
    original = receipt["checkpoints"]["index-intent:" + state.value.key]
    repaired = receipt["checkpoints"]["index-intent-reconciled:" + state.value.key]
    assert original == {
        "status": "done",
        "resource_id": identifier,
        "dimensions": 1536,
        "revision": None,
        "row_status": "queued",
    }
    assert repaired["revision"] == 1 and repaired["generation"] == 2
    events = await state.context.get_bean(AuditRepository).find_all(
        tenant_id="example", action="installation.index.intent_reconciled"
    )
    assert len(events) == 1 and events[0].resource_id == identifier
    assert await state.writer.intent(permit, state.value) == identifier
    assert (
        len(
            await state.context.get_bean(AuditRepository).find_all(
                tenant_id="example", action="installation.index.intent_reconciled"
            )
        )
        == 1
    )


async def test_legacy_intent_never_reconciles_without_explicit_resume(persisted_indexes):
    from koinon.installation.authority import InstallationError

    state = persisted_indexes
    await legacy_intent(state)
    with pytest.raises(InstallationError):
        await state.writer.intent(state.permit, state.value)
    assert (
        "index-intent-reconciled:" + state.value.key
        not in (await state.admissions.receipt(state.permit))["checkpoints"]
    )


@pytest.mark.parametrize(
    "change",
    [
        "revision",
        "cancelled",
        "provider",
        "fingerprint",
        "native_id",
        "build_slot",
        "cursor",
        "job_id",
        "actor",
        "storage_dimensions",
        "active_slot",
        "workspace",
        "native_target",
        "chunks",
        "native_workspace",
        "binding",
        "catalog_effect",
        "selected_connection",
        "native_read_error",
    ],
)
async def test_legacy_resume_rejects_changed_or_effectful_state(persisted_indexes, change):
    from koinon.installation.authority import InstallationError

    state = persisted_indexes
    identifier = await legacy_intent(state)
    async with TransactionTemplate("primary").transaction():
        row = await state.reader.records.find_by_id(identifier)
        if change == "revision":
            row.revision = 2
        elif change == "cancelled":
            row.status = "cancelled"
        elif change == "provider":
            provider = await state.context.get_bean(ProviderRepository).find_by_id(row.provider_id)
            provider.revision += 1
            await state.context.get_bean(ProviderRepository).save(provider)
        elif change == "fingerprint":
            row.embedding_fingerprint = "f" * 64
        elif change == "native_id":
            row.native_id = "manual"
        elif change == "build_slot":
            row.build_slot = "manual"
        elif change == "cursor":
            row.cursor = {"native_config_fingerprint": "already-created"}
        elif change == "job_id":
            row.job_id = "manual-job"
        elif change == "actor":
            row.updated_by = "issuer|manual"
        elif change == "storage_dimensions":
            row.storage_dimensions = 768
        elif change == "active_slot":
            row.active_slot = row.build_slot
        elif change == "workspace":
            row.native_workspace_id = "manual-workspace"
        elif change == "binding":
            await state.reader.facade.bindings.save(
                DomainBinding(
                    id="manual-binding",
                    tenant_id="example",
                    catalog_id=row.workspace_id,
                    workspace_id=row.workspace_id,
                    domain="canon",
                    entity_kind="workspace",
                    native_id=row.workspace_id,
                    native_workspace_id=row.workspace_id,
                    created_by="issuer|manual",
                )
            )
        elif change == "catalog_effect":
            await state.context.get_bean(CatalogRepository).save(
                CatalogEntry(
                    id="manual-folder",
                    tenant_id="example",
                    workspace_id=row.workspace_id,
                    kind="project",
                    project_id="manual-folder",
                    parent_id=row.workspace_id,
                    name="Manual",
                    created_by="issuer|manual",
                )
            )
        await state.reader.records.save(row)
    if change == "native_target":
        state.reader.adapter.discover.return_value = {"total": 1, "items": [{"native_id": "manual"}]}
    elif change == "chunks":
        state.reader.adapter.overview.return_value = {"active_native_id": None, "chunk_count": 1}
    elif change == "native_workspace":
        state.reader.adapter.workspace_exists.return_value = True
    elif change == "selected_connection":
        state.reader.connections.selected.return_value = SimpleNamespace(id="manual")
    elif change == "native_read_error":
        state.reader.adapter.workspace_exists.side_effect = PermissionError("denied")
    permit = await resumed(state)
    with pytest.raises((InstallationError, PermissionError)):
        await state.writer.intent(permit, state.value)
    receipt = await state.admissions.receipt(permit)
    assert receipt["checkpoints"]["index-intent:" + state.value.key]["revision"] is None
    assert "index-intent-reconciled:" + state.value.key not in receipt["checkpoints"]


@pytest.mark.parametrize(
    "changes",
    [
        {"resource_id": "forged"},
        {"dimensions": 768},
        {"row_status": "ready"},
        {"status": "pending"},
        {"revision": 0},
        {"extra": "forged"},
    ],
)
async def test_legacy_resume_rejects_malformed_original_checkpoint(persisted_indexes, changes):
    from koinon.installation.authority import InstallationError

    state = persisted_indexes
    await legacy_intent(state, original_changes=changes)
    permit = await resumed(state)
    with pytest.raises(InstallationError):
        await state.writer.intent(permit, state.value)
    assert (
        "index-intent-reconciled:" + state.value.key
        not in (await state.admissions.receipt(permit))["checkpoints"]
    )


@pytest.mark.parametrize(
    "change", ["generation", "revision", "source_hash", "descriptor_hash", "resource_id", "extra"]
)
async def test_legacy_resume_rejects_forged_reconciliation(persisted_indexes, change):
    from koinon.installation.authority import InstallationError
    from koinon.installation.intent_recovery import legacy_intent as describe_legacy
    from koinon.installation.intent_recovery import pristine_descriptor
    from koinon.installation.writes import fingerprint

    state = persisted_indexes
    identifier = await legacy_intent(state)
    permit = await resumed(state)
    async with TransactionTemplate("primary").transaction():
        run = await state.admissions.require(permit)
        workspace, provider_id, native, _, original = describe_legacy(permit, state.value, run)
        row = await state.reader.records.find_by_id(identifier)
        provider = await state.reader.planner.provider("example", provider_id, state.value.model_id)
        certificate = {
            "status": "done",
            "resource_id": identifier,
            "dimensions": 1536,
            "revision": 1,
            "row_status": "queued",
            "generation": 2,
            "source_checkpoint_sha256": fingerprint(original),
            "descriptor_sha256": pristine_descriptor(
                permit, state.value, run, row, provider, workspace, native, identifier
            ),
            "reason": "repository_defaults_26_11_1",
        }
        if change == "generation":
            certificate["generation"] = True
        elif change == "revision":
            certificate["revision"] = True
        elif change == "source_hash":
            certificate["source_checkpoint_sha256"] = "f" * 64
        elif change == "descriptor_hash":
            certificate["descriptor_sha256"] = "f" * 64
        elif change == "resource_id":
            certificate["resource_id"] = "forged"
        elif change == "extra":
            certificate["extra"] = "forged"
        await state.admissions.checkpoint(permit, "index-intent-reconciled:" + state.value.key, certificate)
    with pytest.raises(InstallationError):
        await state.writer.intent(permit, state.value)


async def test_reconciled_intent_retains_normal_revision_fence(persisted_indexes):
    from koinon.installation.authority import InstallationError

    state = persisted_indexes
    identifier = await legacy_intent(state)
    permit = await resumed(state)
    await state.writer.intent(permit, state.value)
    async with TransactionTemplate("primary").transaction():
        row = await state.reader.records.find_by_id(identifier)
        row.revision += 1
        await state.reader.records.save(row)
    with pytest.raises(InstallationError):
        await state.writer.intent(permit, state.value)
