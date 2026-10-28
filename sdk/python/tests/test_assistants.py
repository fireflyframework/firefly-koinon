# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json

import httpx
import pytest

from koinon_sdk import ApiError, KoinonClient, ProviderInput, RunInput


@pytest.mark.parametrize(
    "method,operation,args,body,suffix,response",
    [
        (
            "GET",
            "configuration",
            ("north",),
            None,
            "/configuration",
            {"providers": [], "provider_types": [], "connections": [], "checks": []},
        ),
        (
            "POST",
            "create_provider",
            (
                "north",
                ProviderInput(
                    name="Owned model",
                    kind="ollama",
                    base_url="http://localhost:11434",
                    model_ids=["fixture"],
                ),
            ),
            {
                "name": "Owned model",
                "kind": "ollama",
                "base_url": "http://localhost:11434",
                "model_ids": ["fixture"],
            },
            "/providers",
            {
                "id": "p1",
                "name": "Owned model",
                "kind": "ollama",
                "base_url": "http://localhost:11434",
                "model_ids": ["fixture"],
                "enabled": True,
                "revision": 1,
                "secret_configured": False,
                "validated": False,
                "checks": [],
            },
        ),
        (
            "PUT",
            "update_provider",
            ("north", "p1", ProviderInput(enabled=False)),
            {"enabled": False},
            "/providers/p1",
            {
                "id": "p1",
                "name": "Owned model",
                "kind": "ollama",
                "base_url": "http://localhost:11434",
                "model_ids": ["fixture"],
                "enabled": False,
                "revision": 2,
                "secret_configured": False,
                "validated": False,
                "checks": [],
            },
        ),
        (
            "POST",
            "validate_provider",
            ("north", "p1"),
            None,
            "/providers/p1/validate",
            {"provider_id": "p1", "revision": 2, "status": "needs_setup", "checks": []},
        ),
        ("GET", "agents", ("north",), None, "/agents", {"items": []}),
        ("GET", "threads", ("north",), None, "/chat/threads", {"items": []}),
        ("GET", "messages", ("north", "t1"), None, "/chat/threads/t1/messages", {"items": []}),
        (
            "POST",
            "submit_run",
            ("north", "t1", RunInput(agent_id="a1", message="Question", client_request_id="once")),
            {"agent_id": "a1", "message": "Question", "client_request_id": "once"},
            "/chat/threads/t1/runs",
            {"run_id": "r1", "message_id": "m1"},
        ),
        (
            "POST",
            "cancel_run",
            ("north", "r1"),
            None,
            "/chat/runs/r1/cancel",
            {"run_id": "r1", "message_id": "m1", "status": "cancelled"},
        ),
        (
            "POST",
            "retry_run",
            ("north", "r1"),
            None,
            "/chat/runs/r1/retry",
            {"run_id": "r1", "message_id": "m1", "status": "queued"},
        ),
        (
            "GET",
            "result",
            ("north", "r1", "e1"),
            None,
            "/chat/runs/r1/results/e1",
            {"id": "e1", "run_id": "r1", "kind": "schema", "data": {"tables": []}},
        ),
    ],
)
async def test_assistant_operation_contract(method, operation, args, body, suffix, response):
    calls = []

    def handle(request):
        calls.append(request)
        assert request.method == method
        assert request.url.path.endswith(suffix)
        assert request.headers["Authorization"] == "Bearer fresh"
        if body is not None:
            assert json.loads(request.content) == body
        return httpx.Response(200, json=response)

    async with KoinonClient(
        "https://api.test/api/v1", token_provider=lambda: "fresh", transport=httpx.MockTransport(handle)
    ) as client:
        await getattr(client, operation)(*args)
    assert len(calls) == 1


async def test_secret_input_is_write_only_in_repr_but_sent_once():
    secret = "local-only-fixture-credential"
    value = ProviderInput(secret=secret)
    assert secret not in repr(value)
    calls = []

    def handle(request):
        calls.append(request)
        assert json.loads(request.content)["secret"] == secret
        return httpx.Response(503, json={"code": "NOT_READY"})

    async with KoinonClient(
        "https://api.test/api/v1", token_provider=lambda: "fresh", transport=httpx.MockTransport(handle)
    ) as client:
        with pytest.raises(ApiError):
            await client.update_provider("north", "p1", value)
    assert len(calls) == 1


async def test_agent_and_thread_mutations_keep_typed_scope():
    from koinon_sdk import AgentInput, KnowledgeScope

    seen = []
    agent = {
        "id": "agent-id",
        "name": "Reader",
        "description": "",
        "provider_id": "provider-id",
        "model_id": "fixture",
        "tools": ["search_knowledge"],
        "scope": {"workspace_id": "workspace-id"},
        "instructions": "Use evidence",
        "enabled": True,
        "revision": 1,
        "status": "needs_setup",
        "checks": [],
    }

    def handle(request):
        seen.append(
            (request.method, request.url.path, json.loads(request.content) if request.content else None)
        )
        if request.url.path.endswith("/chat/threads"):
            return httpx.Response(
                201,
                json={
                    "id": "thread-id",
                    "revision": 1,
                    "title_source": "manual",
                    "folder_id": None,
                    "archived_at": None,
                    "title": "Question",
                    "scope": {"workspace_id": "workspace-id"},
                    "created_at": "2026-10-26T00:00:00Z",
                    "updated_at": "2026-10-26T00:00:00Z",
                },
            )
        return httpx.Response(200, json=agent)

    async with KoinonClient(
        "https://api.test/api/v1", token_provider=lambda: "fresh", transport=httpx.MockTransport(handle)
    ) as client:
        scope = KnowledgeScope(workspace_id="workspace-id")
        created = await client.create_agent("north", AgentInput(name="Reader", scope=scope))
        assert created.scope.workspace_id == "workspace-id"
        await client.update_agent("north", "agent/id", AgentInput(instructions="Use evidence"))
        await client.validate_agent("north", "agent/id")
        thread = await client.create_thread("north", title="Question", scope=scope)
        assert thread.scope.workspace_id == "workspace-id"
    assert [request[0] for request in seen] == ["POST", "PATCH", "POST", "POST"]
    assert seen[0][2] == {"name": "Reader", "scope": {"workspace_id": "workspace-id"}}
