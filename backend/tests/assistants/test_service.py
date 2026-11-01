# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import base64
from pathlib import Path

import pytest


@pytest.fixture
async def assistants(tmp_path: Path):
    from flycanon.config import CanonSettings
    from flyquery.config import FlyquerySettings
    from pyfly.container.scanner import scan_package
    from pyfly.context import ApplicationContext
    from pyfly.core import Config

    # Optional bulk models can load during collection; register their native job foreign key.
    import koinon.jobs.entities  # noqa: F401
    from koinon.assistants.service import AssistantService
    from koinon.catalog.entities import Membership, Tenant
    from koinon.catalog.repositories import MembershipRepository, TenantRepository

    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "agentic": {"enabled": True},
                    "eda": {"provider": "memory"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "create",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'assistant.db'}",
                        }
                    },
                },
                "koinon": {
                    "assistants": {
                        "master_key": base64.urlsafe_b64encode(b"k" * 32).decode(),
                        "allowed_provider_hosts": ["127.0.0.1", "models.example.test"],
                    }
                },
            }
        )
    )
    context.container.register_instance(CanonSettings, CanonSettings(answer_mode="rag"))
    context.container.register_instance(FlyquerySettings, FlyquerySettings())
    for package in (
        "koinon.catalog",
        "koinon.organization_knowledge",
        "koinon.organization_branding",
        "koinon.assistants",
    ):
        scan_package(package, context.container)
    await context.start()
    for tenant in ("north", "south"):
        await context.get_bean(TenantRepository).save(Tenant(id=tenant, name=tenant.title()))
    for name, tenant, role in (
        ("admin", "north", "admin"),
        ("viewer", "north", "viewer"),
        ("other", "north", "viewer"),
        ("outsider", "south", "admin"),
    ):
        await context.get_bean(MembershipRepository).save(
            Membership(
                id=name,
                subject=f"issuer|{name}",
                tenant_id=tenant,
                role=role,
            )
        )
    yield context.get_bean(AssistantService), context
    await context.stop()


async def configured(service):
    provider = await service.save_provider(
        "issuer|admin",
        "north",
        {
            "name": "Local models",
            "kind": "ollama",
            "base_url": "http://127.0.0.1:11434/v1",
            "model_ids": ["qwen2.5:1.5b"],
            "secret": "private-provider-key",
        },
    )
    agent = await service.save_agent(
        "issuer|admin",
        "north",
        {
            "name": "Knowledge guide",
            "provider_id": provider["id"],
            "model_id": "qwen2.5:1.5b",
            "tools": ["search_knowledge"],
            "scope": {},
        },
    )
    return provider, agent


async def test_provider_secrets_are_write_only_and_ciphertext_is_tenant_bound(assistants):
    from koinon.assistants.repositories import ProviderRepository

    service, context = assistants
    provider, _ = await configured(service)
    assert provider["secret_configured"] is True
    assert "private-provider-key" not in str(provider)
    stored = (await context.get_bean(ProviderRepository).find_all(id=provider["id"]))[0]
    assert b"private-provider-key" not in stored.secret_ciphertext
    assert service.secrets.decrypt("north", stored.id, stored.secret_ciphertext) == "private-provider-key"
    with pytest.raises(ValueError):
        service.secrets.decrypt("south", stored.id, stored.secret_ciphertext)


async def test_readers_cannot_change_configuration_or_read_foreign_threads(assistants):
    from koinon.catalog.errors import AccessDenied

    service, _ = assistants
    with pytest.raises(AccessDenied):
        await service.save_provider("issuer|viewer", "north", {"name": "Forbidden", "kind": "ollama"})
    thread = await service.create_thread("issuer|viewer", "north", {"title": "Research"})
    for subject, tenant in (("issuer|other", "north"), ("issuer|outsider", "south")):
        with pytest.raises(AccessDenied):
            await service.messages(subject, tenant, thread["id"])
    assert await service.messages("issuer|viewer", "north", thread["id"]) == []


async def test_run_submission_is_durable_idempotent_and_conflict_checked(assistants):
    from pyfly.kernel import ConflictException

    from koinon.assistants.repositories import ChatMessageRepository, ChatRunRepository

    service, context = assistants
    _, agent = await configured(service)
    thread = await service.create_thread("issuer|viewer", "north", {"title": "Research"})
    request = {
        "agent_id": agent["id"],
        "message": "What do we know?",
        "scope": {},
        "client_request_id": "request-1",
    }
    first = await service.submit("issuer|viewer", "north", thread["id"], request)
    assert first == await service.submit("issuer|viewer", "north", thread["id"], request)
    with pytest.raises(ConflictException):
        await service.submit("issuer|viewer", "north", thread["id"], {**request, "message": "Different"})
    runs = await context.get_bean(ChatRunRepository).find_all(thread_id=thread["id"])
    messages = await context.get_bean(ChatMessageRepository).find_all(thread_id=thread["id"])
    assert len(runs) == 1 and runs[0].status == "queued"
    assert [m.role for m in sorted(messages, key=lambda m: m.created_at)] == ["user", "assistant"]


async def test_run_scope_cannot_exceed_agent_or_current_membership(assistants):
    from koinon.catalog.errors import AccessDenied
    from koinon.catalog.service import CatalogService

    service, context = assistants
    provider, agent = await configured(service)
    catalog = context.get_bean(CatalogService)
    workspace = await catalog.create("issuer|admin", "north", kind="workspace", name="Research")
    other = await catalog.create("issuer|admin", "north", kind="workspace", name="Restricted")
    agent = await service.save_agent(
        "issuer|admin",
        "north",
        {
            "name": "Scoped guide",
            "provider_id": provider["id"],
            "model_id": "qwen2.5:1.5b",
            "tools": ["search_knowledge"],
            "scope": {"workspace_id": workspace.id},
        },
        agent["id"],
    )
    thread = await service.create_thread("issuer|viewer", "north", {})
    with pytest.raises(AccessDenied):
        await service.submit(
            "issuer|viewer",
            "north",
            thread["id"],
            {
                "agent_id": agent["id"],
                "message": "Question",
                "scope": {"workspace_id": other.id},
                "client_request_id": "bad-scope",
            },
        )


async def test_provider_addresses_require_explicit_deployment_allowlist(assistants):
    from pyfly.kernel import InvalidRequestException

    service, _ = assistants
    for address in (
        "http://models.example.test/v1",
        "https://unapproved.example.test/v1",
        "https://user:pass@models.example.test/v1",
    ):
        with pytest.raises(InvalidRequestException):
            await service.save_provider(
                "issuer|admin",
                "north",
                {
                    "name": "Rejected",
                    "kind": "openai",
                    "base_url": address,
                    "model_ids": ["test-model"],
                },
            )


async def test_leased_run_events_replay_and_cancellation_reject_stale_worker(assistants):
    from pyfly.kernel import ConflictException

    from koinon.assistants.queue import AssistantQueue

    service, context = assistants
    _, agent = await configured(service)
    thread = await service.create_thread("issuer|viewer", "north", {})
    submitted = await service.submit(
        "issuer|viewer",
        "north",
        thread["id"],
        {
            "agent_id": agent["id"],
            "message": "Question",
            "scope": {},
            "client_request_id": "lease-1",
        },
    )
    queue = context.get_bean(AssistantQueue)
    claimed = await queue.claim("worker-a")
    assert claimed.id == submitted["run_id"]
    assert await queue.claim("worker-b") is None
    await queue.append(claimed.id, "worker-a", "message_delta", {"text": "Observed answer"})
    assert (await service.messages("issuer|viewer", "north", thread["id"]))[-1]["text"] != "Observed answer"
    events = await service.run_events("issuer|viewer", "north", claimed.id, after=0)
    assert "Observed answer" not in str(events)
    assert (await service.message_repository.find_by_id(claimed.message_id)).text == "Observed answer"
    assert await service.run_events("issuer|viewer", "north", claimed.id, after=events[-1]["id"]) == []
    await service.cancel("issuer|viewer", "north", claimed.id)
    with pytest.raises(ConflictException):
        await queue.append(claimed.id, "worker-a", "message_delta", {"text": "Must not appear"})
    assert (await service.messages("issuer|viewer", "north", thread["id"]))[-1]["status"] == "cancelled"


async def test_revocation_is_rechecked_for_run_event_access(assistants):
    from koinon.catalog.errors import AccessDenied
    from koinon.catalog.repositories import MembershipRepository

    service, context = assistants
    _, agent = await configured(service)
    thread = await service.create_thread("issuer|viewer", "north", {})
    submitted = await service.submit(
        "issuer|viewer",
        "north",
        thread["id"],
        {
            "agent_id": agent["id"],
            "message": "Question",
            "client_request_id": "revoke-1",
        },
    )
    await context.get_bean(MembershipRepository).delete_by_id("viewer")
    with pytest.raises(AccessDenied):
        await service.run_events("issuer|viewer", "north", submitted["run_id"])


async def test_native_agent_worker_uses_scoped_tools_and_persists_replayable_evidence(
    assistants, monkeypatch
):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from pydantic_ai.models.test import TestModel
    from pyfly.agentic.models import ModelFactory

    from koinon.assistants.execution import AssistantExecutor
    from koinon.assistants.probe import ProviderProbe
    from koinon.assistants.queue import AssistantQueue
    from koinon.knowledge.evidence_capture import CapturedEvidence, NativeKnowledgeEvidence

    service, context = assistants
    monkeypatch.setattr(
        ProviderProbe,
        "check",
        AsyncMock(
            return_value=[
                {"id": "connection", "status": "passed", "message": "Controlled provider"},
                {"id": "models", "status": "passed", "message": "Controlled discovered model"},
            ]
        ),
    )
    _, agent = await configured(service)
    await service.validate_provider("issuer|admin", "north", agent["provider_id"])
    model = TestModel(
        call_tools=["search_knowledge"], custom_output_args={"outcome": "insufficient_evidence"}
    )
    monkeypatch.setattr(ModelFactory, "build_with_secret", lambda self, spec, secret: model)
    from koinon.catalog.service import CatalogService

    parent = None
    source = None
    for kind in ("workspace", "project", "collection", "source", "document"):
        parent = await context.get_bean(CatalogService).create(
            "issuer|admin",
            "north",
            kind=kind,
            name="Worker evidence " + kind,
            parent_id=parent.id if parent else None,
        )
        if kind == "source":
            source = parent
    document = parent
    knowledge = SimpleNamespace(
        search=AsyncMock(
            return_value={
                "hits": [
                    {
                        "asset_id": document.id,
                        "source_id": source.id,
                        "title": "Worker evidence",
                        "text": "Verified scoped evidence.",
                    }
                ]
            }
        )
    )
    from koinon.evidence.dtos import SourceReference

    knowledge.search.return_value = CapturedEvidence(
        knowledge.search.return_value,
        (
            SourceReference(
                id="verified-chunk",
                asset_id=document.id,
                source_id=source.id,
                title="Worker evidence",
                kind="document",
                used_revision="chunk-sha256:" + "a" * 64,
            ),
        ),
        True,
    )
    context.container.register_instance(NativeKnowledgeEvidence, knowledge)
    thread = await service.create_thread("issuer|viewer", "north", {})
    submitted = await service.submit(
        "issuer|viewer",
        "north",
        thread["id"],
        {
            "agent_id": agent["id"],
            "message": "What is documented?",
            "scope": {"asset_ids": [document.id]},
            "client_request_id": "native-1",
        },
    )
    queue = context.get_bean(AssistantQueue)
    run = await queue.claim("worker-test")
    await context.get_bean(AssistantExecutor).execute(run.id, "worker-test")
    message = (await service.messages("issuer|viewer", "north", thread["id"]))[-1]
    assert message["status"] == "completed"
    assert "verifiable evidence" in message["text"]
    assert message["artifacts"] == []
    assert knowledge.search.await_args.kwargs["asset_ids"] == [document.id]
    assert message["answer_policy"]["outcome"] == "refused"
    assert any(row.kind == "search" for row in await service.results.find_all(run_id=run.id))
    events = await service.run_events("issuer|viewer", "north", submitted["run_id"])
    assert events[-1]["type"] == "completed"
    assert not any(event["type"] == "openui_delta" for event in events)


async def test_message_cursor_pages_do_not_duplicate_and_snapshot_carries_event_boundary(assistants):
    from koinon.assistants.queue import AssistantQueue

    service, context = assistants
    _, agent = await configured(service)
    thread = await service.create_thread("issuer|viewer", "north", {})
    queue = context.get_bean(AssistantQueue)
    for index in range(3):
        submitted = await service.submit(
            "issuer|viewer",
            "north",
            thread["id"],
            {
                "agent_id": agent["id"],
                "message": f"Question {index}",
                "client_request_id": f"page-{index}",
            },
        )
        run = await queue.claim("cursor-worker")
        assert run.id == submitted["run_id"]
        await queue.append(run.id, "cursor-worker", "message_delta", {"text": f"Answer {index}"})
        await queue.finish(run.id, "cursor-worker")
    cursor, seen = None, []
    for index in (2, 1, 0):
        page = await service.message_page("issuer|viewer", "north", thread["id"], before=cursor, limit=2)
        from koinon.answers.receipts import legacy_notice

        assert [item["text"] for item in page["items"]] == [f"Question {index}", legacy_notice("en")]
        assert page["items"][-1]["event_cursor"] == "3"
        seen.extend(item["id"] for item in page["items"])
        cursor = page["next_cursor"]
    assert cursor is None and len(set(seen)) == 6


async def test_agent_pages_filter_before_count_and_threads_remain_owner_scoped(assistants):
    service, _ = assistants
    provider, first = await configured(service)
    await service.save_agent(
        "issuer|admin",
        "north",
        {
            "name": "Disabled guide",
            "provider_id": provider["id"],
            "model_id": first["model_id"],
            "enabled": False,
        },
    )
    page = await service.agent_page("issuer|viewer", "north", status="disabled", q="guide", page_size=1)
    assert page["total"] == 1 and page["items"][0]["name"] == "Disabled guide"
    for title in ("Research A", "Research B", "Different"):
        await service.create_thread("issuer|viewer", "north", {"title": title})
    await service.create_thread("issuer|other", "north", {"title": "Research private"})
    page = await service.thread_page(
        "issuer|viewer", "north", q="Research", page=2, page_size=1, sort="title", order="asc"
    )
    assert page["total"] == 2 and [row["title"] for row in page["items"]] == ["Research B"]


@pytest.mark.parametrize("recovery", ["retry", "lease"])
async def test_restarted_generation_does_not_reuse_the_previous_attempts_grounding_policy(
    assistants, recovery
):
    from datetime import timedelta

    from koinon.assistants.lifecycle import timestamp
    from koinon.assistants.queue import AssistantQueue

    service, context = assistants
    _, agent = await configured(service)
    thread = await service.create_thread("issuer|viewer", "north", {})
    run = await service.submit(
        "issuer|viewer",
        "north",
        thread["id"],
        {"agent_id": agent["id"], "message": "Question", "client_request_id": "policy-reset"},
    )
    queue = context.get_bean(AssistantQueue)
    claimed = await queue.claim("policy-worker")
    await queue.policy(run["run_id"], "policy-worker", {"outcome": "grounded"})
    assert (await service.messages("issuer|viewer", "north", thread["id"]))[-1]["answer_policy"] == {
        "outcome": "refused",
        "code": "EVIDENCE_RELEASE_REQUIRED",
    }
    if recovery == "retry":
        await queue.finish(run["run_id"], "policy-worker", code="CONTROLLED_FAILURE")
        await service.retry("issuer|viewer", "north", run["run_id"])
    else:
        claimed.lease_until = timestamp() - timedelta(seconds=1)
        await service.runs.save(claimed)
        await queue.claim("replacement-worker")
    assert "answer_policy" not in (await service.messages("issuer|viewer", "north", thread["id"]))[-1]


async def test_workspace_chat_directory_includes_compatible_organization_agents_only(assistants):
    from koinon.catalog.repositories import MembershipRepository
    from koinon.catalog.service import CatalogService

    service, context = assistants
    _, agent = await configured(service)
    catalog = context.get_bean(CatalogService)
    workspace = await catalog.create("issuer|admin", "north", kind="workspace", name="Selected space")
    other = await catalog.create("issuer|admin", "north", kind="workspace", name="Other space")
    membership = await context.get_bean(MembershipRepository).find_by_id("viewer")
    membership.workspace_id = workspace.id
    await context.get_bean(MembershipRepository).save(membership)
    await service.save_agent(
        "issuer|admin",
        "north",
        {
            "name": "Other space guide",
            "provider_id": agent["provider_id"],
            "model_id": agent["model_id"],
            "scope": {"workspace_id": other.id},
        },
    )
    page = await service.configuration_service.agent_page("issuer|viewer", "north", workspace_id=workspace.id)
    assert [row["id"] for row in page["items"]] == [agent["id"]]


async def test_document_corpus_chat_scope_accepts_its_assets_and_rejects_sibling_assets(assistants):
    from koinon.catalog.errors import AccessDenied
    from koinon.catalog.service import CatalogService

    service, context = assistants
    catalog = context.get_bean(CatalogService)
    workspace = await catalog.create("issuer|admin", "north", kind="workspace", name="Research")
    project = await catalog.create(
        "issuer|admin", "north", kind="project", name="Evidence", parent_id=workspace.id
    )
    corpora, documents = [], []
    for name in ("Selected", "Sibling"):
        corpus = await catalog.create("issuer|admin", "north", kind="corpus", name=name, parent_id=project.id)
        source = await catalog.create("issuer|admin", "north", kind="source", name=name, parent_id=corpus.id)
        document = await catalog.create(
            "issuer|admin", "north", kind="document", name=name, parent_id=source.id
        )
        corpora.append(corpus)
        documents.append(document)
    scope = {
        "workspace_id": workspace.id,
        "project_id": project.id,
        "collection_id": corpora[0].id,
        "asset_ids": [documents[0].id],
    }
    assert await service.validate_scope("issuer|viewer", "north", scope) == scope
    with pytest.raises(AccessDenied, match="another folder"):
        await service.validate_scope("issuer|viewer", "north", {**scope, "asset_ids": [documents[1].id]})
