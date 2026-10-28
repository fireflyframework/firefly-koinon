# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_service import assistants as assistants


def test_native_connection_api_is_explicit_and_options_are_bounded():
    from pyfly.agentic.models import ModelFactory

    from koinon.assistants.connections import ConnectionResolver, ModelParameters
    from koinon.assistants.settings import AssistantSettings

    resolver = ConnectionResolver(
        AssistantSettings(allowed_provider_hosts=["api.openai.com"]), ModelFactory()
    )
    provider = SimpleNamespace(kind="openai", api="responses", base_url="https://api.openai.com/v1")
    spec = resolver.spec(provider, "gpt-4o", {"max_tokens": 512, "store_responses": False})
    assert spec.model_class == "OpenAIResponsesModel"
    assert resolver.settings_for(spec)["openai_store"] is False
    provider.api = "chat"
    assert resolver.spec(provider, "gpt-4o", {}).model_class == "OpenAIChatModel"
    provider.api = "messages"
    with pytest.raises(ValueError):
        resolver.spec(provider, "gpt-4o", {})
    for invalid in (
        {"max_tokens": 16385},
        {"request_timeout": 121},
        {"max_tokens": True},
        {"extra_body": {}},
        {"temperature": float("nan")},
        {"model_class": "some.arbitrary.Class"},
    ):
        with pytest.raises(ValueError):
            ModelParameters.model_validate(invalid)


async def test_discovery_does_not_qualify_chat_and_embedding_only_is_rejected(assistants, monkeypatch):
    from koinon.assistants import probe
    from koinon.assistants.probe import ProviderProbe

    service, context = assistants
    seen = []

    class Client:
        def __init__(self, **kwargs):
            pass

        async def request_bounded(self, method, url, **kwargs):
            seen.append((method, url, kwargs))
            data = {"data": [{"id": "chat:latest"}, {"id": "embed:latest"}]}
            if method == "POST":
                data = {
                    "capabilities": ["completion", "tools", "vision"]
                    if kwargs["json"]["model"] == "chat:latest"
                    else ["embedding"]
                }
            return SimpleNamespace(status_code=200, json=lambda: data)

        async def stop(self):
            pass

    monkeypatch.setattr(probe, "HttpxClientAdapter", Client)
    checks = await context.get_bean(ProviderProbe).check(
        "ollama", "http://127.0.0.1:11434/v1", ["chat:latest", "embed:latest"], None, api="chat"
    )
    assert any(
        c.get("model_id") == "embed:latest" and c.get("capability") == "chat" and c["status"] == "failed"
        for c in checks
    )
    from koinon.assistants.connections import capability_state, input_modalities

    discovered = SimpleNamespace(
        checks=checks,
        validated_revision=1,
        revision=1,
        model_ids=["chat:latest"],
        kind="ollama",
        api="chat",
        base_url="http://127.0.0.1:11434/v1",
    )
    state = capability_state(discovered)[0]
    assert input_modalities(state) == ["text", "image"]
    assert not state["image_input"]["verified"] and state["audio_input"]["supported"] is False
    assert input_modalities(None) == ["text"]
    discovered.revision = 2
    assert input_modalities(capability_state(discovered)[0]) == ["text"]
    assert not any(c.get("verified") for c in checks)
    assert {row[0] for row in seen} == {"GET", "POST"}
    assert all("/models" in url or "/api/show" in url for _, url, _ in seen)
    probe_service = context.get_bean(ProviderProbe)
    await probe_service.check("ollama", "http://127.0.0.1:11434", ["chat:latest"], None, api="chat")
    assert [url for _, url, _ in seen[-2:]] == [
        "http://127.0.0.1:11434/v1/models",
        "http://127.0.0.1:11434/api/show",
    ]
    await probe_service.check(
        "ollama", "http://127.0.0.1:11434/gateway/v1", ["chat:latest"], None, api="chat"
    )
    assert [url for _, url, _ in seen[-2:]] == [
        "http://127.0.0.1:11434/gateway/v1/models",
        "http://127.0.0.1:11434/gateway/api/show",
    ]

    provider = await service.save_provider(
        "issuer|admin",
        "north",
        {
            "name": "Discovery only",
            "kind": "ollama",
            "base_url": "http://127.0.0.1:11434/v1",
            "model_ids": ["chat:latest"],
        },
    )
    result = await service.validate_provider("issuer|admin", "north", provider["id"])
    assert result["connected"] and result["discovered"] and result["status"] == "unverified"
    agent = await service.save_agent(
        "issuer|admin",
        "north",
        {
            "name": "Untested",
            "provider_id": provider["id"],
            "model_id": "chat:latest",
            "tools": [],
            "model_options": {"max_tokens": 256},
        },
    )
    assert agent["configured"] and agent["status"] == "unverified" and agent["can_run"]
    assert agent["model_class"] == "OpenAIChatModel" and agent["model_options"]["max_tokens"] == 256
    configuration = await service.configuration("issuer|admin", "north")
    assert any(
        p["id"] == "azure" and p["native_supported"] and not p["exposed"]
        for p in configuration["framework_providers"]
    )
    assert any(c["ownership"] == "deployment" for c in configuration["connections"])


spec = importlib.util.spec_from_file_location(
    "connections_native_web_fixture", Path(__file__).resolve().parents[1] / "web/conftest.py"
)
assert spec and spec.loader
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
client = native.client


def test_http_null_removes_credential_and_omission_preserves_it(client):
    import base64
    import secrets

    from koinon.assistants.settings import AssistantSettings

    settings = client.native_app.state.context.get_bean(AssistantSettings)
    settings.allowed_provider_hosts = ["api.openai.com"]
    settings.master_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    endpoint = "/api/v1/tenants/north/providers"
    created = client.post(
        endpoint,
        headers=native.bearer(),
        json={
            "name": "Explicit native API",
            "kind": "openai",
            "api": "responses",
            "base_url": "https://api.openai.com/v1",
            "model_ids": ["gpt-4o"],
            "secret": "fictional-key",
        },
    )
    assert created.status_code == 201, created.text
    row = created.json()
    assert (
        row["api"] == "responses"
        and row["model_class"] == "OpenAIResponsesModel"
        and row["secret_configured"]
    )
    retained = client.put(endpoint + "/" + row["id"], headers=native.bearer(), json={"name": "Keep key"})
    assert retained.status_code == 200 and retained.json()["secret_configured"]
    removed = client.put(endpoint + "/" + row["id"], headers=native.bearer(), json={"secret": None})
    assert removed.status_code == 200 and removed.json()["secret_configured"] is False
    assert "fictional-key" not in removed.text
    assert (
        client.put(endpoint + "/" + row["id"], headers=native.bearer(), json={"api": "messages"}).status_code
        == 400
    )
    assert client.put(
        endpoint + "/" + row["id"], headers=native.bearer(), json={"model_class": "anything.Class"}
    ).status_code in (400, 422)


async def test_runtime_qualification_is_specific_to_effective_options_and_revision(assistants, monkeypatch):
    from unittest.mock import AsyncMock

    from koinon.assistants.probe import ProviderProbe

    service, _ = assistants
    monkeypatch.setattr(
        ProviderProbe,
        "check",
        AsyncMock(
            return_value=[
                {"id": "connection", "status": "passed", "message": "Controlled connection"},
                {"id": "models", "status": "passed", "message": "Controlled discovery"},
            ]
        ),
    )
    provider = await service.save_provider(
        "issuer|admin",
        "north",
        {
            "name": "Options proof",
            "kind": "ollama",
            "base_url": "http://127.0.0.1:11434/v1",
            "model_ids": ["fixture"],
        },
    )
    await service.validate_provider("issuer|admin", "north", provider["id"])
    agents = [
        await service.save_agent(
            "issuer|admin",
            "north",
            {
                "name": str(budget),
                "provider_id": provider["id"],
                "model_id": "fixture",
                "tools": [],
                "model_options": {"max_tokens": budget},
            },
        )
        for budget in (128, 256)
    ]
    await service.configuration_service.record_runtime_qualification(
        "north", provider["id"], 1, "fixture", [], {"max_tokens": 128}
    )
    rows = [await service.scoped(service.agents, "north", row["id"]) for row in agents]
    assert (await service.agent_dto(rows[0]))["status"] == "ready"
    assert (await service.agent_dto(rows[1]))["status"] == "unverified"
    await service.save_provider("issuer|admin", "north", {"name": "New revision"}, provider["id"])
    await service.configuration_service.record_runtime_qualification(
        "north", provider["id"], 1, "fixture", [], {"max_tokens": 256}
    )
    assert (await service.agent_dto(rows[0]))["status"] != "ready"


async def test_known_embedding_only_model_cannot_be_saved_as_a_conversational_agent(assistants, monkeypatch):
    from unittest.mock import AsyncMock

    from pyfly.kernel import InvalidRequestException

    from koinon.assistants.probe import ProviderProbe

    service, _ = assistants
    monkeypatch.setattr(
        ProviderProbe,
        "check",
        AsyncMock(
            return_value=[
                {"id": "connection", "status": "passed", "message": "Connected"},
                {"id": "models", "status": "passed", "message": "Discovered"},
                {
                    "id": "model:embed:chat",
                    "model_id": "embed",
                    "capability": "chat",
                    "supported": False,
                    "verified": False,
                    "status": "failed",
                    "message": "Embedding only",
                },
            ]
        ),
    )
    provider = await service.save_provider(
        "issuer|admin",
        "north",
        {
            "name": "Embeddings only",
            "kind": "ollama",
            "base_url": "http://127.0.0.1:11434/v1",
            "model_ids": ["embed"],
        },
    )
    await service.validate_provider("issuer|admin", "north", provider["id"])
    with pytest.raises(InvalidRequestException, match="conversational"):
        await service.save_agent(
            "issuer|admin",
            "north",
            {"name": "Must reject", "provider_id": provider["id"], "model_id": "embed", "tools": []},
        )


def test_ollama_api_base_normalization_and_custom_prefix_are_explicit():
    from pyfly.agentic.models import ModelFactory

    from koinon.assistants.connections import ConnectionResolver
    from koinon.assistants.settings import AssistantSettings

    resolver = ConnectionResolver(AssistantSettings(allowed_provider_hosts=["127.0.0.1"]), ModelFactory())
    origin = "http://127.0.0.1:11434"
    assert resolver.address("ollama", origin) == origin + "/v1"
    assert resolver.address("ollama", origin + "/v1/") == origin + "/v1"
    assert resolver.address("ollama", origin + "/gateway/v1") == origin + "/gateway/v1"
    for ambiguous in ("/gateway", "/api", "/v1/models"):
        with pytest.raises(ValueError, match="/v1"):
            resolver.address("ollama", origin + ambiguous)
    provider = SimpleNamespace(kind="ollama", api="chat", base_url=origin)
    assert resolver.spec(provider, "fixture", {}).base_url == origin + "/v1"


def test_native_anthropic_transport_cannot_follow_an_ambient_endpoint_override(monkeypatch):
    from pyfly.agentic.models import ModelFactory

    from koinon.assistants.connections import ConnectionResolver
    from koinon.assistants.settings import AssistantSettings

    resolver = ConnectionResolver(
        AssistantSettings(allowed_provider_hosts=["api.anthropic.com"]), ModelFactory()
    )
    provider = SimpleNamespace(kind="anthropic", api="messages", base_url="https://api.anthropic.com/v1")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://unapproved.example")
    with pytest.raises(ValueError, match="endpoint override"):
        resolver.spec(provider, "claude-sonnet-4-6", {})


@pytest.mark.parametrize("variable", ["OPENAI_ORG_ID", "OPENAI_PROJECT_ID"])
def test_tenant_openai_connection_rejects_ambient_billing_selectors(monkeypatch, variable):
    from pyfly.agentic.models import ModelFactory

    from koinon.assistants.connections import ConnectionResolver
    from koinon.assistants.settings import AssistantSettings

    resolver = ConnectionResolver(
        AssistantSettings(allowed_provider_hosts=["api.openai.com"]), ModelFactory()
    )
    provider = SimpleNamespace(kind="openai", api="chat", base_url="https://api.openai.com/v1")
    monkeypatch.setenv(variable, "ambient-deployment-selector")
    with pytest.raises(ValueError, match="Ambient OpenAI"):
        resolver.spec(provider, "gpt-4o", {})


def test_agent_and_thread_filters_reach_native_pagination_services(client):
    from koinon.assistants.settings import AssistantSettings

    client.native_app.state.context.get_bean(AssistantSettings).allowed_provider_hosts = ["127.0.0.1"]
    tenant = "/api/v1/tenants/north"
    provider = client.post(
        tenant + "/providers",
        headers=native.bearer(),
        json={
            "name": "No network fixture",
            "kind": "ollama",
            "base_url": "http://127.0.0.1:11434",
            "model_ids": ["fixture"],
        },
    ).json()
    for name in ("Alpha", "Beta"):
        response = client.post(
            tenant + "/agents",
            headers=native.bearer(),
            json={"name": name, "provider_id": provider["id"], "model_id": "fixture", "tools": []},
        )
        assert response.status_code == 201, response.text
        assert (
            client.post(tenant + "/chat/threads", headers=native.bearer(), json={"title": name}).status_code
            == 201
        )
    agents = client.get(
        tenant + "/agents",
        headers=native.bearer(),
        params={"q": "Alpha", "page_size": 1, "status": "unverified"},
    )
    assert agents.status_code == 200, agents.text
    assert [row["name"] for row in agents.json()["items"]] == ["Alpha"]
    assert agents.json()["total"] == 1
    threads = client.get(
        tenant + "/chat/threads", headers=native.bearer(), params={"q": "Beta", "page_size": 1}
    )
    assert threads.status_code == 200, threads.text
    assert [row["title"] for row in threads.json()["items"]] == ["Beta"] and threads.json()["total"] == 1
