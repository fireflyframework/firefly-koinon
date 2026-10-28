# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""A structured agent must use the application-owned factory and usage ledger."""

import pytest
from pydantic_ai.models.test import TestModel
from pyfly.agentic.factory import AgentFactory
from pyfly.agentic.runtime import AgenticRuntime
from pyfly.context import ApplicationContext
from pyfly.core import Config

from flyquery.config import FlyquerySettings
from flyquery.core.agents.builder import build_agent


async def test_structured_agent_uses_the_context_runtime_and_closes_with_it():
    context = ApplicationContext(
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
    await context.start()
    runtime = context.get_bean(AgenticRuntime)
    try:
        factory = context.get_bean(AgentFactory)
        settings = FlyquerySettings()
        settings.bind_agent_factory(factory)
        agent = build_agent(
            name="structured-native-fixture",
            model=TestModel(custom_output_text="native response"),
            output_type=str,
            instructions="Synthetic instructions",
            settings=settings,
        )
        assert agent._runtime is runtime
        assert agent.usage_tracker is runtime.usage_tracker
        assert (await agent.run("Synthetic tenant input")).output == "native response"
    finally:
        await context.stop()
    assert runtime._closed


def test_unbound_agent_factory_is_actionable_and_does_not_create_a_runtime():
    with pytest.raises(RuntimeError, match="ApplicationContext"):
        build_agent(
            name="unbound",
            model=TestModel(),
            output_type=str,
            instructions="Synthetic instructions",
            settings=FlyquerySettings(),
        )
