# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Qualify one exact model/options snapshot with a bounded, data-free native stream."""

import asyncio

from pydantic_ai.usage import UsageLimits
from pyfly.agentic.factory import AgentFactory
from pyfly.agentic.tools import agent_tool
from pyfly.container import Provider, service

from koinon.assistants.connections import ConnectionResolver, ModelParameters
from koinon.installation.authority import InstallationError
from koinon.installation.writes import ProviderProbeSnapshot

MARKER = "koinon-installation-ready"
TIMEOUT_SECONDS = 90


@service(name="installation.model_qualification")
class NativeInstallationQualification:
    def __init__(self, compiler: ConnectionResolver, factory: Provider[AgentFactory]):
        self.compiler, self.factory = compiler, factory

    async def qualify(
        self,
        snapshot: ProviderProbeSnapshot,
        model_id: str,
        model_options: ModelParameters,
        *,
        require_tools: bool,
    ) -> None:
        try:
            await self._qualify(snapshot, model_id, model_options, require_tools=require_tools)
        except Exception:
            raise InstallationError("INSTALLATION_MODEL_QUALIFICATION_FAILED") from None

    async def _qualify(
        self,
        snapshot: ProviderProbeSnapshot,
        model_id: str,
        model_options: ModelParameters,
        *,
        require_tools: bool,
    ) -> None:
        if model_id not in snapshot.model_ids or (snapshot.kind != "ollama" and not snapshot.secret):
            raise ValueError("The snapshot has no admitted model credential")
        spec = self.compiler.spec(
            snapshot, model_id, model_options.model_dump(mode="json", exclude_none=True)
        )
        calls = 0

        @agent_tool(
            "installation_health",
            description="Return a fixed installation health marker.",
            auto_register=False,
        )
        async def installation_health() -> str:
            nonlocal calls
            calls += 1
            if calls != 1:
                raise ValueError("Installation health must be requested once")
            return MARKER

        instructions = (
            "This is an installation connection check with no organizational data. "
            + (
                "Call installation_health exactly once. After it returns, "
                if require_tools
                else "Do not call tools. "
            )
            + f"Reply with exactly {MARKER} and no other text."
        )
        secret = snapshot.secret.get_secret_value() if snapshot.secret else "unused"
        async with (
            asyncio.timeout(TIMEOUT_SECONDS),
            self.compiler.models.build_with_secret(spec, secret) as model,
        ):
            factory = self.factory.get()
            agent = factory.create(
                name="koinon-installation-qualification",
                model=model,
                instructions=instructions,
                output_type=str,
                tools=[installation_health] if require_tools else [],
                auto_register=False,
                memory=None,
                retries=0,
                model_settings=self.compiler.settings_for(spec),
                model_options=spec.options,
                config=factory.runtime.config.model_copy(update={"default_temperature": None}),
            )
            text = ""
            async with await agent.run_stream(
                "Check the connection.",
                usage_limits=UsageLimits(
                    request_limit=3,
                    tool_calls_limit=1 if require_tools else 0,
                    input_tokens_limit=4096,
                    output_tokens_limit=512,
                ),
            ) as stream:
                async for delta in stream.stream_text(delta=True, debounce_by=None):
                    text += delta
                    if len(text) > 4096:
                        raise ValueError("Installation response exceeds its bound")
        if text.strip() != MARKER or calls != (1 if require_tools else 0):
            raise ValueError("Installation did not observe the requested capabilities")
