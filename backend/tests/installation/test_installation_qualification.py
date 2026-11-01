# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Exercise the native agent and streaming protocol without external provider traffic."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from pydantic import SecretStr
from pydantic_ai.models.test import TestModel
from pyfly.agentic.config import AgenticConfig
from pyfly.agentic.models import ModelFactory
from pyfly.agentic.runtime import AgenticRuntime

from koinon.assistants.connections import ConnectionResolver, ModelParameters
from koinon.assistants.settings import AssistantSettings
from koinon.installation.authority import InstallationError
from koinon.installation.writes import ProviderProbeSnapshot

MARKER = "koinon-installation-ready"


@pytest.fixture
async def native_factory():
    async with AgenticRuntime(AgenticConfig(default_model="test", plugin_auto_discover=False)) as runtime:
        yield runtime.agent_factory


async def fixture_probe(native_factory, monkeypatch, *, output=MARKER, call_tools="all"):
    from koinon.installation.qualification import NativeInstallationQualification

    seen = []
    model = TestModel(call_tools=call_tools, custom_output_text=output)

    @asynccontextmanager
    async def build(_self, spec, secret):
        seen.append((spec, secret))
        yield model

    monkeypatch.setattr(ModelFactory, "build_with_secret", build)
    compiler = ConnectionResolver(
        AssistantSettings(allowed_provider_hosts=["models.example.test"]), ModelFactory()
    )
    qualifier = NativeInstallationQualification(compiler, SimpleNamespace(get=lambda: native_factory))
    snapshot = ProviderProbeSnapshot(
        "provider",
        3,
        "openai",
        "chat",
        "https://models.example.test/v1",
        ["deployed-model"],
        SecretStr("fixture-secret-never-a-prompt"),
    )
    return qualifier, snapshot, seen, model


@pytest.mark.parametrize("require_tools", [False, True])
async def test_native_qualification_observes_real_stream_and_optional_pure_tool(
    native_factory,
    monkeypatch,
    require_tools,
):
    qualifier, snapshot, seen, model = await fixture_probe(native_factory, monkeypatch)
    options = ModelParameters(max_tokens=1024, request_timeout=30)
    await qualifier.qualify(snapshot, "deployed-model", options, require_tools=require_tools)
    assert len(native_factory.runtime.agent_registry) == 0
    assert len(native_factory.runtime.tool_registry) == 0
    assert len(seen) == 1
    assert seen[0][0].model == "deployed-model"
    assert seen[0][0].options.max_tokens == 1024
    assert seen[0][0].options.request_timeout == 30
    assert seen[0][1] == "fixture-secret-never-a-prompt"
    assert [tool.name for tool in model.last_model_request_parameters.function_tools] == (
        ["installation_health"] if require_tools else []
    )


@pytest.mark.parametrize("output,tools", [("Unexpected answer", "all"), (MARKER, [])])
async def test_native_qualification_rejects_missing_tool_or_wrong_final_marker(
    native_factory,
    monkeypatch,
    output,
    tools,
):
    qualifier, snapshot, _, _ = await fixture_probe(
        native_factory, monkeypatch, output=output, call_tools=tools
    )
    with pytest.raises(InstallationError, match="INSTALLATION_MODEL_QUALIFICATION_FAILED"):
        await qualifier.qualify(snapshot, "deployed-model", ModelParameters(), require_tools=True)


async def test_undeclared_model_fails_before_secret_or_transport_use(native_factory, monkeypatch):
    qualifier, snapshot, seen, _ = await fixture_probe(native_factory, monkeypatch)
    with pytest.raises(InstallationError, match="INSTALLATION_MODEL_QUALIFICATION_FAILED"):
        await qualifier.qualify(snapshot, "other-model", ModelParameters(), require_tools=True)
    assert seen == []


@pytest.mark.parametrize("cancel", [False, True])
async def test_timeout_and_cancellation_close_the_model_without_retries(native_factory, monkeypatch, cancel):
    from pydantic_ai.models.function import FunctionModel

    from koinon.installation import qualification

    qualifier, snapshot, _, _ = await fixture_probe(native_factory, monkeypatch)
    started = asyncio.Event()
    closed = []
    requests = []

    async def stalled(messages, info):
        requests.append(info)
        started.set()
        await asyncio.Event().wait()
        yield MARKER

    @asynccontextmanager
    async def build(_self, spec, secret):
        try:
            yield FunctionModel(stream_function=stalled)
        finally:
            closed.append(True)

    monkeypatch.setattr(ModelFactory, "build_with_secret", build)
    monkeypatch.setattr(qualification, "TIMEOUT_SECONDS", 1 if cancel else 0.01)
    task = asyncio.create_task(
        qualifier.qualify(snapshot, "deployed-model", ModelParameters(), require_tools=False)
    )
    if cancel:
        await asyncio.wait_for(started.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        with pytest.raises(InstallationError, match="INSTALLATION_MODEL_QUALIFICATION_FAILED"):
            await task
    assert len(requests) == 1
    assert closed == [True]


async def test_provider_exception_does_not_expose_credentials(native_factory, monkeypatch):
    from pydantic_ai.models.function import FunctionModel

    qualifier, snapshot, _, _ = await fixture_probe(native_factory, monkeypatch)

    async def rejected(messages, info):
        raise ValueError("Provider refused fixture-secret-never-a-prompt")
        yield MARKER

    @asynccontextmanager
    async def build(_self, spec, secret):
        yield FunctionModel(stream_function=rejected)

    monkeypatch.setattr(ModelFactory, "build_with_secret", build)
    with pytest.raises(InstallationError) as failure:
        await qualifier.qualify(snapshot, "deployed-model", ModelParameters(), require_tools=False)
    assert str(failure.value) == "INSTALLATION_MODEL_QUALIFICATION_FAILED"
    assert failure.value.__suppress_context__ is True
