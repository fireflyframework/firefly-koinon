# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Queued execution uses actual catalog, credential, binding and model records."""

import runpy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder

from koinon.assistants.entities import Provider
from koinon.assistants.repositories import ProviderRepository
from koinon.catalog.repositories import MembershipRepository
from koinon.catalog.service import CatalogService
from koinon.knowledge.connections.entities import KnowledgeConnection
from koinon.knowledge.connections.repositories import KnowledgeConnectionRepository
from koinon.knowledge.entities import DomainBinding
from koinon.knowledge.repositories import DomainBindingRepository
from koinon.tokens.entities import PersonalToken
from koinon.tokens.repositories import PersonalTokenRepository
from koinon.workers.execution import IngestionExecutionAuthority

_fixtures = runpy.run_path(str(Path(__file__).parents[1] / "web" / "conftest.py"))
client = _fixtures["client"]


@pytest.fixture(autouse=True)
def knowledge_core(monkeypatch):
    import koinon.app

    original = koinon.app.create_application

    def enabled(config):
        config["koinon"]["knowledge"]["enabled"] = True
        return original(config)

    monkeypatch.setattr(koinon.app, "create_application", enabled)


@pytest.fixture
def captured(client):
    async def setup():
        context = client.native_app.state.context
        subject = _fixtures["ISSUER"] + "|admin"
        catalog = context.get_bean(CatalogService)
        project = await catalog.create(
            subject, "north", kind="project", name="Project", parent_id=client.workspace_id
        )
        collection = await catalog.create(
            subject, "north", kind="collection", name="Collection", parent_id=project.id
        )
        source = await catalog.create(
            subject, "north", kind="source", name="Queued source", parent_id=collection.id
        )
        native_workspace = str(uuid4())
        await context.get_bean(DomainBindingRepository).save(
            DomainBinding(
                id="workspace-binding",
                tenant_id="north",
                catalog_id=client.workspace_id,
                workspace_id=client.workspace_id,
                domain="structured",
                entity_kind="workspace",
                native_id=native_workspace,
                native_workspace_id=native_workspace,
                created_by=subject,
            )
        )
        await context.get_bean(ProviderRepository).save(
            Provider(
                id="provider",
                tenant_id="north",
                name="Inert provider",
                kind="openai",
                api="chat",
                base_url="https://provider.invalid/v1",
                model_ids=["declared-model"],
            )
        )
        await context.get_bean(KnowledgeConnectionRepository).save(
            KnowledgeConnection(
                id="assignment",
                tenant_id="north",
                workspace_id=client.workspace_id,
                scope_key=client.workspace_id,
                domain="structured",
                role="structured.describe",
                mode="provider",
                provider_id="provider",
                model_id="declared-model",
                created_by=subject,
                updated_by=subject,
            )
        )
        await context.get_bean(PersonalTokenRepository).save(
            PersonalToken(
                id="credential",
                subject=subject,
                tenant_id="north",
                name="Origin",
                prefix="inert",
                token_hash="0" * 64,
                scopes=["catalog:read", "ingest:write"],
                workspace_ids=[client.workspace_id],
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        security = SecurityContext(
            user_id="admin",
            attributes={"iss": _fixtures["ISSUER"], "sub": "admin", "koinon_token_id": "credential"},
        )
        authority = context.get_bean(IngestionExecutionAuthority)
        with SecurityContextHolder.using(security):
            value = await authority.capture(
                "structured",
                {
                    "actor": subject,
                    "tenant_id": "north",
                    "workspace_id": native_workspace,
                    "catalog_workspace_id": client.workspace_id,
                    "source_catalog_id": source.id,
                },
                ("structured.describe",),
            )
        return authority, value, security

    return client.portal.call(setup)


@pytest.mark.parametrize("change", ["membership", "credential", "provider", "assignment"])
def test_queued_execution_rechecks_current_primary_authority_before_opening_models(client, captured, change):
    authority, value, security = captured

    async def check():
        context = client.native_app.state.context
        with SecurityContextHolder.using(security):
            await authority.validate(value)
        if change == "membership":
            await context.get_bean(MembershipRepository).delete_by_id("admin")
        else:
            kind, identifier, field, replacement = {
                "credential": (PersonalTokenRepository, "credential", "revoked_at", datetime.now(UTC)),
                "provider": (ProviderRepository, "provider", "revision", 2),
                "assignment": (KnowledgeConnectionRepository, "assignment", "revision", 2),
            }[change]
            repository = context.get_bean(kind)
            row = await repository.find_by_id(identifier)
            setattr(row, field, replacement)
            await repository.save(row)
        with SecurityContextHolder.using(security), pytest.raises(Exception) as denied:
            await authority.validate(value)
        assert getattr(denied.value, "code", None) in {
            "ACCESS_DENIED",
            "TOKEN_UNAVAILABLE",
            "INGEST_EXECUTION_CONTEXT_REQUIRED",
        }

    client.portal.call(check)


def test_unprovable_old_pending_job_never_opens_a_model(client, captured, monkeypatch):
    from unittest.mock import Mock

    authority, value, security = captured
    open_models = Mock(side_effect=AssertionError("Unprovable job opened a model"))
    monkeypatch.setattr(authority.resolver, "resolve", open_models)

    async def check():
        with pytest.raises(Exception) as denied:
            async with authority.admit("structured", {"request_json": {}}, None):
                pytest.fail("Unprovable job was admitted")
        assert getattr(denied.value, "code", None) == "INGEST_EXECUTION_CONTEXT_REQUIRED"
        open_models.assert_not_called()
        assert SecurityContextHolder.get_context() is None

    client.portal.call(check)


@pytest.mark.parametrize("change", ["job", "workspace", "tenant", "status", "attempt", "credential"])
def test_callback_requires_exact_origin_job_and_current_credential(client, captured, change):
    import sqlalchemy as sa
    from pyfly.context.consumer_context import PRIVATE_CONSUMER_CONTEXT
    from pyfly.data.relational.datasource_registry import DataSourceRegistry

    from koinon.workers.callbacks import ManagedCallbackAccess

    authority, value, security = captured

    async def check():
        context = client.native_app.state.context
        registry = context.get_bean(DataSourceRegistry)
        metadata = sa.MetaData()
        jobs = sa.Table(
            "flyquery_ingest_jobs",
            metadata,
            sa.Column("id", sa.Uuid),
            sa.Column("tenant_id", sa.String),
            sa.Column("workspace_id", sa.Uuid),
            sa.Column("request_json", sa.JSON),
            sa.Column("status", sa.String),
            sa.Column("attempts", sa.Integer),
        )
        identifier = uuid4()
        from uuid import UUID

        workspace = UUID(value.native_workspace_id)
        async with registry.get("structured").engine.begin() as connection:
            await connection.run_sync(metadata.create_all)
            await connection.execute(
                jobs.insert().values(
                    id=identifier,
                    tenant_id="north",
                    workspace_id=workspace,
                    request_json={PRIVATE_CONSUMER_CONTEXT: value.model_dump(mode="json")},
                    status="SUCCEEDED",
                    attempts=1,
                )
            )
        access = ManagedCallbackAccess(registry, authority)
        claim = {
            "ingest_job_id": identifier,
            "tenant_id": "north",
            "workspace_id": workspace,
            "payload_json": {"status": "SUCCEEDED", "attempts": 1},
        }
        await access.authorize(claim)
        if change == "credential":
            repository = context.get_bean(PersonalTokenRepository)
            row = await repository.find_by_id("credential")
            row.revoked_at = datetime.now(UTC)
            await repository.save(row)
        elif change in {"status", "attempt"}:
            claim["payload_json"]["status" if change == "status" else "attempts"] = (
                "FAILED" if change == "status" else 2
            )
        else:
            claim[{"job": "ingest_job_id", "workspace": "workspace_id", "tenant": "tenant_id"}[change]] = (
                "south" if change == "tenant" else uuid4()
            )
        with pytest.raises(Exception) as denied:
            await access.authorize(claim)
        assert getattr(denied.value, "code", None) in {
            "TOKEN_UNAVAILABLE",
            "INGEST_EXECUTION_CONTEXT_REQUIRED",
        }
        assert SecurityContextHolder.get_context() is None

    client.portal.call(check)


def test_complete_backlog_observation_executes_every_queue_on_its_named_datasource(client):
    import sqlalchemy as sa
    from pyfly.data.relational.datasource_registry import DataSourceRegistry

    from koinon.workers.observations import WorkerBacklog

    async def observe():
        context = client.native_app.state.context
        registry = context.get_bean(DataSourceRegistry)
        for name, tables in {
            "canon_admin": ["canon_ingest_jobs"],
            "structured_admin": ["flyquery_ingest_jobs", "flyquery_callback_outbox"],
        }.items():
            metadata = sa.MetaData()
            for name_ in tables:
                sa.Table(
                    name_,
                    metadata,
                    sa.Column("id", sa.String),
                    sa.Column("kind", sa.String),
                    sa.Column("status", sa.String),
                    sa.Column("attempts", sa.Integer),
                    sa.Column("started_at", sa.DateTime(timezone=True)),
                    sa.Column("created_at", sa.DateTime(timezone=True)),
                    sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
                    sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
                    sa.Column("last_status_code", sa.Integer),
                    sa.Column("last_error", sa.String),
                )
            async with registry.get(name).engine.begin() as connection:
                await connection.run_sync(metadata.create_all)
        result = await context.get_bean(WorkerBacklog).snapshot()
        assert {row.queue for row in result.queues} == {
            "conversation",
            "index",
            "attachment",
            "profile",
            "document_ingest",
            "structured_ingest",
            "callback",
            "communications",
            "bulk_intake",
            "bulk_query",
        }
        assert all(row.available and row.ready == row.active == row.demand == 0 for row in result.queues)
        assert all(1 <= row.capacity <= 100 for row in result.queues)
        return result

    client.portal.call(observe)
