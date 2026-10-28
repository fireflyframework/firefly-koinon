# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pyfly.kernel import ConflictException, InvalidRequestException

from koinon.assistants.connections import ConnectionResolver
from koinon.assistants.entities import Provider
from koinon.assistants.repositories import ProviderRepository
from koinon.assistants.settings import AssistantSettings
from koinon.catalog.errors import AccessDenied
from koinon.knowledge.connections.repositories import KnowledgeConnectionRepository
from koinon.knowledge.connections.service import KnowledgeConnectionService
from koinon.knowledge.repositories import DomainBindingRepository


@pytest.fixture
async def configured(tmp_path):
    from uuid import uuid4

    from pyfly.core import PyFlyApplication

    from koinon.app import KoinonApplication
    from koinon.assistants.configuration import AssistantConfiguration
    from koinon.catalog.entities import Membership, Tenant
    from koinon.catalog.repositories import MembershipRepository, TenantRepository
    from koinon.catalog.service import CatalogService

    config = tmp_path / "pyfly.yaml"
    config.write_text(
        "pyfly:\n  banner:\n    mode: off\n  agentic:\n    enabled: true\n"
        "    default-model: test\n    plugin-auto-discover: false\n  data:\n"
        "    relational:\n      enabled: true\n      ddl-auto: create\n"
        + f"      url: sqlite+aiosqlite:///{tmp_path / 'connections.db'}\n"
        + "koinon:\n  assistants:\n    allowed-provider-hosts: [127.0.0.1]\n"
    )
    app = PyFlyApplication(KoinonApplication, config_path=str(config))
    for cls in (
        AssistantConfiguration,
        ConnectionResolver,
        AssistantSettings,
        ProviderRepository,
        KnowledgeConnectionRepository,
        DomainBindingRepository,
        KnowledgeConnectionService,
    ):
        app.context.register_bean(cls)
    await app.startup()
    try:
        context = app.context
        catalog = context.get_bean(CatalogService)
        for tenant in ("north", "south"):
            await context.get_bean(TenantRepository).save(Tenant(id=tenant, name=tenant))
        for subject, tenant, role in (
            ("admin", "north", "admin"),
            ("reader", "north", "viewer"),
            ("outsider", "south", "admin"),
        ):
            await context.get_bean(MembershipRepository).save(
                Membership(id=str(uuid4()), subject="issuer|" + subject, tenant_id=tenant, role=role)
            )
        workspace = await catalog.create("issuer|admin", "north", kind="workspace", name="Owned workspace")
        providers = context.get_bean(ProviderRepository)
        await providers.save(
            Provider(
                id="north-provider",
                tenant_id="north",
                name="Owned local",
                kind="ollama",
                api="chat",
                base_url="http://127.0.0.1:11434/v1",
                model_ids=["qwen2.5:3b", "nomic-embed-text"],
            )
        )
        await providers.save(
            Provider(
                id="south-provider",
                tenant_id="south",
                name="Other organization",
                kind="ollama",
                api="chat",
                base_url="http://127.0.0.1:11434/v1",
                model_ids=["qwen2.5:3b"],
            )
        )
        yield (
            context.get_bean(KnowledgeConnectionService),
            catalog,
            context.get_bean(KnowledgeConnectionRepository),
            {"workspace": workspace},
            context,
        )
    finally:
        await app.shutdown()


def values(**changes):
    return {
        "domain": "documents",
        "role": "documents.answer",
        "mode": "provider",
        "provider_id": "north-provider",
        "model_id": "qwen2.5:3b",
        "model_options": {"max_tokens": 512},
        **changes,
    }


async def test_connection_configuration_requires_current_scoped_authority_and_rejects_foreign_provider(
    configured,
):
    service, _, rows, _, _ = configured
    for subject in ("issuer|reader", "issuer|outsider"):
        with pytest.raises(AccessDenied):
            await service.save(subject, "north", values())
    with pytest.raises(AccessDenied):
        await service.save("issuer|admin", "north", values(provider_id="south-provider"))
    assert await rows.find_all() == []


async def test_connection_defaults_and_workspace_overrides_have_revision_and_trusted_actor(configured):
    service, _, _, tree, _ = configured
    default = await service.save("issuer|admin", "north", values())
    override = await service.save("issuer|admin", "north", values(workspace_id=tree["workspace"].id))
    assert default["id"] != override["id"]
    assert default["workspace_id"] is None and override["revision"] == 1
    assert override["created_by"] == "issuer|admin"
    updated = await service.save(
        "issuer|admin",
        "north",
        values(workspace_id=tree["workspace"].id, expected_revision=1, model_options={"max_tokens": 256}),
        override["id"],
    )
    assert updated["revision"] == 2 and updated["model_options"]["max_tokens"] == 256
    with pytest.raises(ConflictException):
        await service.save(
            "issuer|admin",
            "north",
            values(workspace_id=tree["workspace"].id, expected_revision=1),
            override["id"],
        )
    with pytest.raises(ConflictException):
        await service.save("issuer|admin", "north", values())
    selected = await service.selected("north", tree["workspace"].id, "documents", "documents.answer")
    assert selected.id == override["id"]
    await service.delete("issuer|admin", "north", override["id"], expected_revision=2)
    assert (
        await service.selected("north", tree["workspace"].id, "documents", "documents.answer")
    ).id == default["id"]


async def test_embeddings_never_inherit_chat_model_or_current_agent_and_require_explicit_space(configured):
    service, _, _, _, _ = configured
    for changes in (
        {"mode": "current_agent", "provider_id": None, "model_id": None},
        {"dimensions": 768, "storage_dimensions": 768},
        {
            "dimensions": 768,
            "storage_dimensions": 768,
            "space_id": "known",
            "model_options": {"max_tokens": 512},
        },
    ):
        with pytest.raises(InvalidRequestException):
            await service.save(
                "issuer|admin",
                "north",
                values(**{"role": "documents.embedding", "model_id": "nomic-embed-text", **changes}),
            )
    saved = await service.save(
        "issuer|admin",
        "north",
        values(
            role="documents.embedding",
            model_id="nomic-embed-text",
            model_options={},
            dimensions=768,
            storage_dimensions=768,
            space_id="profile:qualified-space",
        ),
    )
    assert saved["space_id"] == "profile:qualified-space"


async def test_viewer_role_descriptors_do_not_disclose_admin_configuration(configured):
    service, _, _, tree, _ = configured
    await service.save("issuer|admin", "north", values())
    result = await service.descriptors("issuer|reader", "north", tree["workspace"].id)
    assert (
        next(role for role in result["roles"] if role["id"] == "documents.answer")["assignment"] == "tenant"
    )
    assert "north-provider" not in str(result) and "qwen2.5" not in str(result)
    with pytest.raises(AccessDenied):
        await service.list("issuer|reader", "north")


def test_additive_migration_enforces_null_workspace_uniqueness_and_matches_entity_columns():
    import importlib.util
    from datetime import UTC, datetime
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import Column, MetaData, String, Table, create_engine, inspect
    from sqlalchemy.exc import IntegrityError

    from koinon.knowledge.connections.entities import KnowledgeConnection

    location = (
        Path(__file__).resolve().parents[3]
        / "deploy/migrations/native_versions/0007_knowledge_connections.py"
    )
    spec = importlib.util.spec_from_file_location("knowledge_connections_migration", location)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert len(migration.revision) <= 32
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    for name in ("lattice_tenants", "lattice_catalog", "koinon_providers"):
        Table(name, metadata, Column("id", String(64), primary_key=True))
    metadata.create_all(engine)
    try:
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            assert set(KnowledgeConnection.__table__.columns.keys()) == {
                column["name"] for column in inspect(connection).get_columns("koinon_knowledge_connections")
            }
            table = Table("koinon_knowledge_connections", MetaData(), autoload_with=connection)
            row = {
                "tenant_id": "north",
                "domain": "documents",
                "role": "documents.answer",
                "mode": "current_agent",
                "created_by": "issuer|admin",
                "updated_by": "issuer|admin",
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            }
            connection.execute(table.insert().values(id="one", **row))
            with pytest.raises(IntegrityError):
                connection.execute(table.insert().values(id="two", **row))
            with pytest.raises(IntegrityError):
                connection.execute(
                    table.insert().values(
                        id="three", workspace_id="workspace", scope_key="wrong-workspace", **row
                    )
                )
    finally:
        engine.dispose()


async def test_workspace_operator_cannot_change_tenant_defaults_or_read_other_scope_configuration(configured):
    from uuid import uuid4

    from koinon.catalog.entities import Membership

    service, catalog, _, tree, _ = configured
    workspace = tree["workspace"].id
    await catalog.membership_repository.save(
        Membership(
            id=str(uuid4()),
            subject="issuer|operator",
            tenant_id="north",
            workspace_id=workspace,
            role="operator",
        )
    )
    with pytest.raises(AccessDenied):
        await service.save("issuer|operator", "north", values())
    saved = await service.save("issuer|operator", "north", values(workspace_id=workspace))
    assert saved["updated_by"] == "issuer|operator"
    with pytest.raises(AccessDenied):
        await service.get("issuer|reader", "north", saved["id"])
    assert "providers" not in await service.descriptors("issuer|reader", "north", workspace)


async def test_role_write_and_audit_failure_roll_back_together(configured, monkeypatch):
    from unittest.mock import AsyncMock

    service, catalog, rows, _, _ = configured
    monkeypatch.setattr(catalog, "_audit", AsyncMock(side_effect=RuntimeError("Audit write unavailable")))
    with pytest.raises(RuntimeError, match="Audit write"):
        await service.save("issuer|admin", "north", values())
    assert await rows.find_all(tenant_id="north") == []


async def test_resolver_uses_exact_purpose_and_current_authority_before_any_secret(configured, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from pydantic_ai.models.test import TestModel

    from koinon.knowledge.connections.resolver import PersistedKnowledgeConnectionResolver
    from koinon.knowledge.entities import DomainBinding

    service, catalog, _, tree, context = configured
    bindings = context.get_bean(DomainBindingRepository)
    workspace = tree["workspace"].id
    await bindings.save(
        DomainBinding(
            id="document-workspace",
            tenant_id="north",
            catalog_id=workspace,
            workspace_id=workspace,
            domain="canon",
            entity_kind="workspace",
            native_id="native-workspace",
            native_workspace_id="native-workspace",
            created_by="issuer|admin",
        )
    )
    await service.save("issuer|admin", "north", values())
    model = TestModel(custom_output_text="authorized native model")
    build = MagicMock(return_value=model)
    monkeypatch.setattr(service.compiler.models, "build_with_secret", build)
    secrets = SimpleNamespace(
        decrypt=MagicMock(side_effect=AssertionError("No ambient or foreign credential access"))
    )
    resolver = PersistedKnowledgeConnectionResolver(
        service, bindings, service.providers, service.compiler, secrets, context.container, None
    )
    arguments = {
        "domain": "canon",
        "tenant_id": "north",
        "workspace_id": "native-workspace",
        "catalog_workspace_id": workspace,
        "subject": "issuer|reader",
        "purpose": "search",
        "roles": ("documents.answer",),
    }
    async with resolver.resolve(**arguments) as selected:
        assert selected.models["documents.answer"].model is model
    assert build.call_args.args[1] == "unused"
    assert build.call_args.args[0].model == "qwen2.5:3b"
    for changed in (
        {"purpose": "ingest", "roles": ("documents.consolidation",)},
        {"subject": "issuer|outsider"},
    ):
        with pytest.raises(AccessDenied):
            async with resolver.resolve(**{**arguments, **changed}):
                raise AssertionError("Denied purpose must not yield clients")
    assert build.call_count == 1
    member = (await catalog.membership_repository.find_all(subject="issuer|reader"))[0]
    member.active = False
    await catalog.membership_repository.save(member)
    with pytest.raises(AccessDenied):
        async with resolver.resolve(**arguments):
            raise AssertionError("Revoked authority must not yield clients")
    assert build.call_count == 1
    secrets.decrypt.assert_not_called()


async def test_embedding_history_prevents_delete_recreate_reindex_bypass(configured):
    service, _, _, _, _ = configured
    initial = values(
        role="documents.embedding",
        model_id="nomic-embed-text",
        model_options={},
        dimensions=768,
        storage_dimensions=768,
        space_id="qualified-index",
    )
    saved = await service.save("issuer|admin", "north", initial)
    await service.delete("issuer|admin", "north", saved["id"], expected_revision=1)
    with pytest.raises(ConflictException) as error:
        await service.save("issuer|admin", "north", {**initial, "model_id": "qwen2.5:3b"})
    assert error.value.code == "KNOWLEDGE_EMBEDDING_REINDEX_REQUIRED"
    restored = await service.save("issuer|admin", "north", initial)
    assert restored["embedding_fingerprint"] == saved["embedding_fingerprint"]


async def test_explicit_current_agent_role_borrows_actor_bound_model_without_building_another_client(
    configured, monkeypatch
):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from pydantic_ai.models.test import TestModel
    from pyfly.kernel import ServiceUnavailableException

    from koinon.assistants.model_bindings import BorrowedModel, bind_model
    from koinon.knowledge.connections.resolver import PersistedKnowledgeConnectionResolver
    from koinon.knowledge.entities import DomainBinding

    service, _, _, tree, context = configured
    workspace = tree["workspace"].id
    bindings = context.get_bean(DomainBindingRepository)
    await bindings.save(
        DomainBinding(
            id="borrowed-workspace",
            tenant_id="north",
            catalog_id=workspace,
            workspace_id=workspace,
            domain="canon",
            entity_kind="workspace",
            native_id="native-workspace",
            native_workspace_id="native-workspace",
            created_by="issuer|admin",
        )
    )
    await service.save(
        "issuer|admin",
        "north",
        values(mode="current_agent", provider_id=None, model_id=None, model_options={}),
    )
    build = MagicMock(side_effect=AssertionError("Borrowing must not create another native client"))
    monkeypatch.setattr(service.compiler.models, "build_with_secret", build)
    resolver = PersistedKnowledgeConnectionResolver(
        service, bindings, service.providers, service.compiler, SimpleNamespace(), context.container, None
    )
    arguments = dict(
        domain="canon",
        tenant_id="north",
        workspace_id="native-workspace",
        catalog_workspace_id=workspace,
        subject="issuer|reader",
        purpose="search",
        roles=("documents.answer",),
    )
    with pytest.raises(ServiceUnavailableException) as missing:
        async with resolver.resolve(**arguments):
            raise AssertionError("No agent is selected")
    assert missing.value.code == "KNOWLEDGE_CURRENT_AGENT_REQUIRED"
    model = TestModel()
    with bind_model(
        "north", "issuer|reader", BorrowedModel(model, {"max_tokens": 512}, "openai", "responses")
    ):
        async with resolver.resolve(**arguments) as selected:
            binding = selected.models["documents.answer"]
            assert binding.model is model and binding.api == "responses"
            assert dict(binding.model_settings) == {"max_tokens": 512}
    with (
        bind_model("south", "issuer|reader", BorrowedModel(model, {}, "openai", "chat")),
        pytest.raises(ServiceUnavailableException),
    ):
        async with resolver.resolve(**arguments):
            raise AssertionError("A foreign agent scope must not be borrowed")
    build.assert_not_called()
