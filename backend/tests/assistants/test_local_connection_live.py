# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import os

import pytest
from test_service import assistants as assistants

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("KOINON_LOCAL_MODEL_TEST") != "1",
        reason="Explicit owned local Ollama qualification only",
    ),
]


async def test_installed_local_model_stream_qualifies_only_observed_capabilities_and_closes_client(
    assistants, monkeypatch
):
    from pyfly.agentic.models import ModelFactory

    from koinon.assistants.execution import AssistantExecutor
    from koinon.assistants.model_bindings import current_model_binding
    from koinon.assistants.queue import AssistantQueue

    service, context = assistants
    provider = await service.save_provider(
        "issuer|admin",
        "north",
        {
            "name": "Owned native local qualification",
            "kind": "ollama",
            "base_url": "http://127.0.0.1:11434",
            "model_ids": ["qwen2.5:3b"],
        },
    )
    assert provider["base_url"].endswith("/v1")
    discovery = await service.validate_provider("issuer|admin", "north", provider["id"])
    assert discovery["connected"] and discovery["discovered"] and discovery["status"] == "unverified"
    agent = await service.save_agent(
        "issuer|admin",
        "north",
        {
            "name": "Local stream proof",
            "provider_id": provider["id"],
            "model_id": "qwen2.5:3b",
            "tools": [],
            "model_options": {"max_tokens": 64, "request_timeout": 20},
        },
    )
    assert agent["status"] == "unverified" and agent["can_run"]
    thread = await service.create_thread("issuer|viewer", "north", {})
    submitted = await service.submit(
        "issuer|viewer",
        "north",
        thread["id"],
        {
            "agent_id": agent["id"],
            "message": "Reply exactly READY.",
            "client_request_id": "local-native-connection",
        },
    )
    claimed = await context.get_bean(AssistantQueue).claim("local-proof-worker")
    assert claimed.id == submitted["run_id"]
    original = ModelFactory.build_with_secret
    clients = []

    def capture(self, spec, secret):
        model = original(self, spec, secret)
        assert model.base_url.rstrip("/") == "http://127.0.0.1:11434/v1"
        clients.append(model.client)
        return model

    monkeypatch.setattr(ModelFactory, "build_with_secret", capture)
    await context.get_bean(AssistantExecutor).execute(submitted["run_id"], "local-proof-worker")
    run = await service.runs.find_by_id(submitted["run_id"])
    assert run.status == "completed", run.error_code
    assert all(client.is_closed() for client in clients)
    assert current_model_binding("north", "issuer|viewer") is None
    saved = await service.agent_dto(await service.agents.find_by_id(agent["id"]))
    assert saved["status"] == "ready"
    capability = (await service.configuration("issuer|admin", "north"))["providers"][0]["model_capabilities"][
        0
    ]
    assert capability["chat"]["verified"] and capability["streaming"]["verified"]
    assert not capability["tools"]["verified"]
