# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Independent native-context regressions for scope, evidence, and worker ownership."""

from contextlib import suppress
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic_ai.models.test import TestModel
from pyfly.kernel import ConflictException
from starlette.requests import Request
from test_service import assistants as assistants
from test_service import configured

from koinon.assistants.audit import AnswerAudits
from koinon.assistants.controllers import AssistantController
from koinon.assistants.execution import AssistantExecutor
from koinon.assistants.lifecycle import timestamp
from koinon.assistants.queue import AssistantQueue
from koinon.assistants.repositories import ChatRunRepository
from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.evidence.dtos import SourceReference
from koinon.knowledge.capture_dtos import CapturedEvidence


async def conversation(service, context, key="review"):
    _, agent = await configured(service)
    thread = await service.create_thread("issuer|viewer", "north", {})
    run = await service.submit(
        "issuer|viewer",
        "north",
        thread["id"],
        {"agent_id": agent["id"], "message": "Review evidence", "client_request_id": key},
    )
    queue = context.get_bean(AssistantQueue)
    await queue.claim("review-worker")
    return agent, thread, run, queue


async def document(context):
    catalog = context.get_bean(CatalogService)
    parent = None
    for kind in ("workspace", "project", "collection", "source", "document"):
        parent = await catalog.create(
            "issuer|admin", "north", kind=kind, name="Review " + kind, parent_id=parent.id if parent else None
        )
    return parent


async def test_history_reauthorizes_prior_evidence_before_model_receives_it(assistants):
    service, context = assistants
    agent, thread, submitted, queue = await conversation(service, context)
    asset = await document(context)
    await queue.evidence(
        submitted["run_id"],
        "review-worker",
        "search",
        {"hits": [{"asset_id": asset.id, "text": "Previously authorized evidence"}]},
        [asset.id],
        capture=CapturedEvidence(
            {"hits": [{"asset_id": asset.id, "text": "Previously authorized evidence"}]},
            (
                SourceReference(
                    id="controlled",
                    asset_id=asset.id,
                    title=asset.name,
                    kind="document",
                    used_revision="controlled-fixture-revision",
                ),
            ),
            True,
        ),
    )
    await queue.append(
        submitted["run_id"], "review-worker", "message_delta", {"text": "Previously authorized evidence"}
    )
    await queue.finish(submitted["run_id"], "review-worker")
    await service.catalog.delete("issuer|admin", "north", asset.id)
    with pytest.raises(AccessDenied):
        await service.messages("issuer|viewer", "north", thread["id"])
    next_run = await service.submit(
        "issuer|viewer",
        "north",
        thread["id"],
        {"agent_id": agent["id"], "message": "Continue", "client_request_id": "review-next"},
    )
    row = await context.get_bean(ChatRunRepository).find_by_id(next_run["run_id"])
    with pytest.raises(AccessDenied):
        await context.get_bean(AssistantExecutor).history(row)


async def test_evidence_response_uses_public_data_shape(assistants, monkeypatch):
    service, context = assistants
    _, _, run, queue = await conversation(service, context)
    result_id = await queue.evidence(
        run["run_id"],
        "review-worker",
        "schema",
        {"tables": []},
        [],
        capture=CapturedEvidence({"tables": []}, (), True),
    )
    monkeypatch.setattr(
        "koinon.assistants.controllers.identity_from_request",
        lambda request: SimpleNamespace(subject="issuer|viewer"),
    )
    from koinon.assistants.history.service import ChatHistoryService

    response = await AssistantController(
        service, context.get_bean(ChatHistoryService), context.get_bean(AnswerAudits)
    ).result(
        "north",
        run["run_id"],
        result_id,
        Request({"type": "http", "method": "GET", "path": "/api/v1/probe", "headers": []}),
    )
    assert response == {"id": result_id, "run_id": run["run_id"], "kind": "schema", "data": {"tables": []}}


async def test_expired_worker_cannot_begin_more_generation_or_tools(assistants):
    service, context = assistants
    _, _, submitted, _ = await conversation(service, context)
    run = await service.runs.find_by_id(submitted["run_id"])
    run.lease_until = timestamp() - timedelta(seconds=1)
    await service.runs.save(run)
    with pytest.raises(ConflictException):
        await context.get_bean(AssistantExecutor).authority(run.id, "review-worker")


async def test_model_client_lifecycle_is_closed_after_generation(assistants, monkeypatch):
    from pyfly.agentic.models import ModelFactory

    from koinon.assistants.probe import ProviderProbe

    service, context = assistants

    class TrackedModel(TestModel):
        exited = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            self.exited = True

    monkeypatch.setattr(
        ProviderProbe,
        "check",
        AsyncMock(
            return_value=[
                {"id": "connection", "status": "passed", "message": "Controlled test model"},
                {"id": "models", "status": "passed", "message": "Controlled discovered model"},
            ]
        ),
    )
    agent, _, submitted, _ = await conversation(service, context)
    await service.validate_provider("issuer|admin", "north", agent["provider_id"])
    model = TrackedModel(call_tools=[], custom_output_args={"outcome": "insufficient_evidence"})
    monkeypatch.setattr(ModelFactory, "build_with_secret", lambda self, spec, secret: model)
    await context.get_bean(AssistantExecutor).execute(submitted["run_id"], "review-worker")
    assert (await service.runs.find_by_id(submitted["run_id"])).status == "completed"
    assert model.exited, "A caller-created provider model needs explicit public lifecycle ownership"


@pytest.mark.integration
@pytest.mark.parametrize("resource_kind", ("provider", "agent"))
async def test_concurrent_provider_edits_get_distinct_revision_fences(monkeypatch, resource_kind):
    import asyncio
    import os
    from uuid import uuid4

    from pyfly.container.scanner import scan_package
    from pyfly.context import ApplicationContext
    from pyfly.core import Config
    from sqlalchemy.engine import make_url

    from koinon.assistants.service import AssistantService
    from koinon.catalog.entities import Membership, Tenant
    from koinon.catalog.repositories import MembershipRepository, TenantRepository

    url = os.environ.get("KOINON_REVIEW_DATABASE_URL")
    if not url:
        pytest.skip("Requires an explicitly configured owned restore database")
    assert make_url(url).database.startswith("koinon_restore_")
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "agentic": {"enabled": True},
                    "eda": {"provider": "memory"},
                    "data": {"relational": {"enabled": True, "ddl-auto": "validate", "url": url}},
                },
                "koinon": {"assistants": {"allowed_provider_hosts": ["127.0.0.1"]}},
            }
        )
    )
    for package in ("koinon.catalog", "koinon.assistants"):
        scan_package(package, context.container)
    await context.start()
    try:
        tenant, subject = "review-" + uuid4().hex[:16], "review|admin"
        await context.get_bean(TenantRepository).save(Tenant(id=tenant, name="Owned revision review"))
        await context.get_bean(MembershipRepository).save(
            Membership(id=str(uuid4()), subject=subject, tenant_id=tenant, role="admin")
        )
        service = context.get_bean(AssistantService)
        provider = await service.save_provider(
            subject,
            tenant,
            {
                "name": "Revision review",
                "kind": "ollama",
                "base_url": "http://127.0.0.1:11434/v1",
                "model_ids": ["fixture"],
            },
        )
        if resource_kind == "agent":
            current = await service.save_agent(
                subject,
                tenant,
                {"name": "Revision review agent", "provider_id": provider["id"], "model_id": "fixture"},
            )
            repository, save = service.agents, service.save_agent
        else:
            current, repository, save = provider, service.providers, service.save_provider
        from koinon.assistants.configuration_service import AssistantConfigurationService

        original = AssistantConfigurationService.scoped
        both_reads, reads = asyncio.Event(), []

        async def synchronize_read(self, repository, tenant_id, resource_id, *args, **kwargs):
            row = await original(self, repository, tenant_id, resource_id, *args, **kwargs)
            if repository is selected_repository and resource_id == current["id"]:
                reads.append(row.revision)
                if len(reads) >= 2:
                    both_reads.set()
                with suppress(TimeoutError):
                    await asyncio.wait_for(both_reads.wait(), 1)
            return row

        selected_repository = repository
        monkeypatch.setattr(AssistantConfigurationService, "scoped", synchronize_read)
        results = await asyncio.gather(
            save(subject, tenant, {"name": "Revision A"}, current["id"]),
            save(subject, tenant, {"name": "Revision B"}, current["id"]),
        )
        assert sorted(row["revision"] for row in results) == [2, 3], (
            "Concurrent edits must never share a validation/worker configuration fence",
            reads,
        )
    finally:
        await context.stop()


async def test_live_run_cancellation_closes_model_and_preserves_cancelled_terminal_state(
    assistants, monkeypatch
):
    import asyncio
    from contextlib import asynccontextmanager

    from pyfly.agentic.models import ModelFactory

    from koinon.assistants.probe import ProviderProbe

    service, context = assistants
    started, stopped = asyncio.Event(), asyncio.Event()

    class WaitingModel(TestModel):
        exited = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            self.exited = True

        @asynccontextmanager
        async def request_stream(self, *args, **kwargs):
            started.set()
            try:
                await asyncio.Event().wait()
                async with super().request_stream(*args, **kwargs) as stream:
                    yield stream
            finally:
                stopped.set()

    monkeypatch.setattr(
        ProviderProbe,
        "check",
        AsyncMock(
            return_value=[
                {"id": "connection", "status": "passed", "message": "Controlled test model"},
                {"id": "models", "status": "passed", "message": "Controlled discovered model"},
            ]
        ),
    )
    agent, thread, submitted, queue = await conversation(service, context)
    await service.validate_provider("issuer|admin", "north", agent["provider_id"])
    model = WaitingModel(call_tools=[], custom_output_text="Must not complete")
    monkeypatch.setattr(ModelFactory, "build_with_secret", lambda self, spec, secret: model)
    service.settings.lease_seconds = 3
    worker = asyncio.create_task(
        context.get_bean(AssistantExecutor).execute(submitted["run_id"], "review-worker")
    )
    await asyncio.wait_for(started.wait(), 2)
    await service.cancel("issuer|viewer", "north", submitted["run_id"])
    await asyncio.wait_for(worker, 3)
    assert stopped.is_set() and model.exited
    run = await service.runs.find_by_id(submitted["run_id"])
    assert run.status == "cancelled" and run.worker_id is None
    assert (await service.messages("issuer|viewer", "north", thread["id"]))[-1]["status"] == "cancelled"
    events = await service.run_events("issuer|viewer", "north", run.id)
    assert events[-1]["type"] == "cancelled"
    assert not any(event["type"] == "completed" for event in events)
    with pytest.raises(ConflictException):
        await queue.append(run.id, "review-worker", "message_delta", {"text": "Late data"})


async def test_provider_probe_cannot_validate_a_changed_configuration(assistants, monkeypatch):
    import asyncio

    from koinon.assistants.probe import ProviderProbe

    service, _ = assistants
    provider, _ = await configured(service)
    started, release = asyncio.Event(), asyncio.Event()

    async def probe(*args, **kwargs):
        started.set()
        await release.wait()
        return [{"id": "connection", "status": "passed", "message": "Controlled stale probe"}]

    monkeypatch.setattr(ProviderProbe, "check", probe)
    validation = asyncio.create_task(service.validate_provider("issuer|admin", "north", provider["id"]))
    await asyncio.wait_for(started.wait(), 2)
    edited = await service.save_provider(
        "issuer|admin", "north", {"name": "Changed while probing"}, provider["id"]
    )
    release.set()
    with pytest.raises(ConflictException):
        await validation
    stored = await service.providers.find_by_id(provider["id"])
    assert stored.revision == edited["revision"] and stored.validated_revision != stored.revision


@pytest.mark.integration
async def test_concurrent_personal_token_creation_respects_owner_limit(monkeypatch):
    import asyncio
    import os
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    from pyfly.container.scanner import scan_package
    from pyfly.context import ApplicationContext
    from pyfly.core import Config
    from sqlalchemy.engine import make_url

    from koinon.catalog.entities import Membership, Tenant
    from koinon.catalog.repositories import MembershipRepository, TenantRepository
    from koinon.tokens.repositories import PersonalTokenRepository
    from koinon.tokens.service import PersonalTokenService
    from koinon.tokens.settings import TokenSettings

    url = os.environ.get("KOINON_REVIEW_DATABASE_URL")
    if not url:
        pytest.skip("Requires an explicitly configured owned restore database")
    assert make_url(url).database.startswith("koinon_restore_")
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "agentic": {"enabled": True},
                    "eda": {"provider": "memory"},
                    "data": {"relational": {"enabled": True, "ddl-auto": "validate", "url": url}},
                }
            }
        )
    )
    for package in ("koinon.catalog", "koinon.tokens", "koinon.profiles"):
        scan_package(package, context.container)
    await context.start()
    try:
        tenant, subject = "review-" + uuid4().hex[:16], "review|" + uuid4().hex
        await context.get_bean(TenantRepository).save(Tenant(id=tenant, name="Owned token limit review"))
        await context.get_bean(MembershipRepository).save(
            Membership(id=str(uuid4()), subject=subject, tenant_id=tenant, role="admin")
        )
        second_tenant = "review-" + uuid4().hex[:16]
        await context.get_bean(TenantRepository).save(
            Tenant(id=second_tenant, name="Other owner organization")
        )
        await context.get_bean(MembershipRepository).save(
            Membership(id=str(uuid4()), subject=subject, tenant_id=second_tenant, role="admin")
        )
        context.get_bean(TokenSettings).max_active_per_user = 1
        service = context.get_bean(PersonalTokenService)
        original = PersonalTokenRepository.find_all
        both_reads, reads = asyncio.Event(), []

        async def synchronized(self, *args, **kwargs):
            rows = await original(self, *args, **kwargs)
            if kwargs.get("subject") == subject:
                reads.append(len(rows))
                if len(reads) >= 2:
                    both_reads.set()
                with suppress(TimeoutError):
                    await asyncio.wait_for(both_reads.wait(), 1)
            return rows

        monkeypatch.setattr(PersonalTokenRepository, "find_all", synchronized)
        values = {
            "name": "Owner limit review",
            "tenant_id": tenant,
            "scopes": ["profile:read"],
            "expires_at": datetime.now(UTC) + timedelta(hours=1),
        }
        results = await asyncio.gather(
            service.create(subject, values),
            service.create(subject, {**values, "tenant_id": second_tenant}),
            return_exceptions=True,
        )
        success_count = sum(isinstance(result, dict) for result in results)
        assert success_count == 1, "Only one token may be created under a one-token policy"
    finally:
        await context.stop()
