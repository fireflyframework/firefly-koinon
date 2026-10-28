# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import FrozenInstanceError
from hashlib import sha256
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic_ai.models.test import TestModel
from pyfly.agentic.config import AgenticConfig
from test_knowledge_connections import configured as configured
from test_knowledge_connections import values
from test_model_bindings import domain as domain
from test_model_bindings import enter_context


async def test_actual_agent_constructor_keeps_frozen_binding_and_applied_inputs(domain):
    package, role, stage, port = domain
    origin = port.ModelBindingProvenance(
        mode="provider",
        assignment_id="assignment",
        assignment_revision=2,
        provider_id="provider",
        provider_revision=3,
        selected_model_id="selected-model",
        model_options_sha256="a" * 64,
    )
    binding = port.ModelBinding(TestModel(), {"max_tokens": 512}, "ollama", "chat", provenance=origin)
    agent = object()
    factory = SimpleNamespace(
        runtime=SimpleNamespace(config=AgenticConfig()), create=MagicMock(return_value=agent)
    )
    settings = SimpleNamespace(_agent_factory=factory, agent_max_output_tokens=1024)
    context = enter_context(package)
    token = port.push_bindings(
        tenant_id="north",
        workspace_id="workspace",
        subject="issuer|north",
        bindings={role: binding, role + ".other": binding},
    )
    try:
        built = import_module(package + ".core.agents.builder").build_agent(
            name=stage,
            model="must-not-infer",
            output_type=str,
            instructions="Exact instructions",
            settings=settings,
        )
        descriptor = port.agent_construction(built)
        assert descriptor.provenance == origin
        assert descriptor.instructions_sha256 == sha256(b"Exact instructions").hexdigest()
        assert descriptor.applied_model_settings_sha256 == port.settings_digest({"max_tokens": 512})
        assert descriptor.model_name == "test" and descriptor.model_class.endswith("TestModel")
        assert descriptor.api == "chat" and descriptor.output_mode == "text"
        if package == "flyquery":
            from flyquery.core.services.ingestion import lineage

            seen = []

            class Sink:
                async def emit(self, event, **values):
                    seen.append(values)

            with lineage.observe(Sink()):
                await lineage.model_input("Private prompt", role=role, implementation="test", agent=built)
            params = seen[0]["parameters"]
            assert params["assignment_id"] == "assignment" and params["provider_revision"] == 3
            assert params["instructions_sha256"] == descriptor.instructions_sha256
            assert params["applied_model_settings_sha256"] == descriptor.applied_model_settings_sha256
            assert params["constructor_identity_complete"] is True
            assert params["transformation_identity_complete"] is False
            assert "Private prompt" not in str(seen) and "Exact instructions" not in str(seen)
            with lineage.observe(Sink()):
                await lineage.model_input("Private prompt", role=role, implementation="test", agent=object())
            assert seen[-1]["parameters"]["constructor_identity_complete"] is False
            assert "assignment_id" not in seen[-1]["parameters"]
            assert seen[-1]["parameters"]["model_reference"] is None
            assert seen[-1]["parameters"]["api"] is None
            with lineage.observe(Sink()), pytest.raises(lineage.LineageError, match="role"):
                await lineage.model_input(
                    "Private prompt", role=role + ".other", implementation="test", agent=built
                )
        with pytest.raises(FrozenInstanceError):
            origin.provider_revision = 99
        assert descriptor.provenance.provider_revision == 3
    finally:
        port.reset_bindings(token)
        context.var.reset(context.token)
    assert port.agent_construction(agent) is None


@pytest.mark.parametrize("mode", ["provider", "current_agent"])
async def test_resolver_captures_selected_ids_and_revisions_without_later_config_lookup(
    configured, domain, monkeypatch, mode
):
    from koinon.assistants.model_bindings import BorrowedModel, bind_model
    from koinon.knowledge.connections.resolver import PersistedKnowledgeConnectionResolver
    from koinon.knowledge.entities import DomainBinding
    from koinon.knowledge.repositories import DomainBindingRepository

    service, _, _, tree, context = configured
    package, role, _, _ = domain
    native_domain = "canon" if package == "flycanon" else "structured"
    public_domain = "documents" if package == "flycanon" else "structured"
    workspace = tree["workspace"].id
    bindings = context.get_bean(DomainBindingRepository)
    await bindings.save(
        DomainBinding(
            id="metadata-workspace",
            tenant_id="north",
            catalog_id=workspace,
            workspace_id=workspace,
            domain=native_domain,
            entity_kind="workspace",
            native_id="native-workspace",
            native_workspace_id="native-workspace",
            created_by="issuer|admin",
        )
    )
    options = dict(domain=public_domain, role=role)
    if mode == "current_agent":
        options.update(mode=mode, provider_id=None, model_id=None, model_options={})
    saved = await service.save("issuer|admin", "north", values(**options))
    monkeypatch.setattr(service.compiler.models, "build_with_secret", MagicMock(return_value=TestModel()))
    resolver = PersistedKnowledgeConnectionResolver(
        service,
        bindings,
        service.providers,
        service.compiler,
        SimpleNamespace(),
        context.container,
        None,
    )
    with bind_model(
        "north",
        "issuer|admin",
        BorrowedModel(
            TestModel(),
            {},
            "ollama",
            "chat",
            agent_id="selected-agent",
            agent_revision=7,
            provider_id="selected-provider",
            provider_revision=4,
            model_id="selected-model",
            options_sha256="b" * 64,
        ),
    ):
        async with resolver.resolve(
            domain=native_domain,
            tenant_id="north",
            workspace_id="native-workspace",
            subject="issuer|admin",
            purpose="search" if native_domain == "canon" else "query",
            roles=(role,),
            catalog_workspace_id=workspace,
        ) as selected:
            observed = selected.models[role].provenance
            assert observed.assignment_id == saved["id"] and observed.assignment_revision == 1
            assert observed.complete and observed.mode == mode
            if mode == "current_agent":
                assert observed.provider_id == "selected-provider" and observed.provider_revision == 4
                assert observed.selected_model_id == "selected-model" and observed.agent_revision == 7
                assert observed.model_options_sha256 == "b" * 64
            else:
                assert observed.provider_id == "north-provider" and observed.provider_revision == 1
                assert observed.selected_model_id == "qwen2.5:3b"
            await service.save(
                "issuer|admin", "north", values(**options, expected_revision=1, enabled=False), saved["id"]
            )
            assert observed.assignment_revision == 1


async def test_valid_native_timeout_settings_remain_usable_and_fingerprinted(domain):
    from httpx import Timeout
    from pyfly.agentic.factory import AgentFactory
    from pyfly.context import ApplicationContext
    from pyfly.core import Config

    package, role, stage, port = domain
    runtime = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "agentic": {
                        "enabled": True,
                        "default-model": "test",
                        "plugin-auto-discover": False,
                    }
                }
            }
        )
    )
    await runtime.start()
    context = enter_context(package)
    token = port.push_bindings(
        tenant_id="north",
        workspace_id="workspace",
        subject="issuer|north",
        bindings={
            role: port.ModelBinding(
                TestModel(custom_output_text="ready"), {"timeout": Timeout(5)}, "ollama", "chat"
            )
        },
    )
    try:
        agent = import_module(package + ".core.agents.builder").build_agent(
            name=stage,
            model="must-not-infer",
            output_type=str,
            instructions="Test",
            settings=SimpleNamespace(
                _agent_factory=runtime.get_bean(AgentFactory), agent_max_output_tokens=256
            ),
        )
        assert len(port.agent_construction(agent).applied_model_settings_sha256) == 64
        assert (await agent.run("Test")).output == "ready"
        assert port.settings_digest({"unknown": object()}) is None
    finally:
        port.reset_bindings(token)
        context.var.reset(context.token)
        await runtime.stop()
