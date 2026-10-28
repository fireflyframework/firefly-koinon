# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
from contextlib import suppress
from datetime import timedelta
from types import SimpleNamespace

from pyfly.client import HttpxClientAdapter
from pyfly.container import component

from koinon.assistants.connections import ConnectionResolver, api_for


@component(name="assistants.provider_probe")
class ProviderProbe:
    def __init__(self, connections: ConnectionResolver):
        self.connections = connections

    async def check(
        self, kind: str, address: str, models: list[str], secret: str | None, *, api: str | None = None
    ) -> list[dict]:
        selected = api_for(kind, api)
        address = self.connections.address(kind, address)
        if kind != "ollama" and not secret:
            return [{"id": "credential", "status": "needs_setup", "message": "Enter the provider API key."}]
        for model in models:
            self.connections.spec(SimpleNamespace(kind=kind, api=selected, base_url=address), model, {})
        client = HttpxClientAdapter(timeout=timedelta(seconds=8), trust_env=False)
        headers = {"Accept": "application/json"}
        if kind == "anthropic":
            headers.update({"x-api-key": secret or "", "anthropic-version": "2023-06-01"})
        else:
            headers["Authorization"] = "Bearer " + (secret or "unused")
        checks: list[dict] = []
        try:
            async with asyncio.timeout(8):
                response = await client.request_bounded(
                    "GET",
                    address + "/models",
                    max_response_bytes=524288,
                    headers=headers,
                    follow_redirects=False,
                )
                if response.status_code != 200:
                    return [
                        {
                            "id": "connection",
                            "status": "failed",
                            "message": "The provider did not accept the connection. "
                            "Check its address and credential.",
                        }
                    ]
                data = response.json()
                available = {
                    r["id"]
                    for r in data.get("data", [])
                    if isinstance(r, dict) and isinstance(r.get("id"), str)
                }
                missing = set(models) - available
                checks = [
                    {"id": "connection", "status": "passed", "message": "Connected to the provider."},
                    {
                        "id": "models",
                        "status": "failed" if missing or not models else "passed",
                        "message": "Choose models available from this provider."
                        if missing or not models
                        else "Selected model identifiers were discovered; generation is not verified.",
                    },
                ]
                for model in models:
                    capabilities = None
                    if kind == "ollama" and address.endswith("/v1") and model in available:
                        metadata = await client.request_bounded(
                            "POST",
                            address[:-3] + "/api/show",
                            max_response_bytes=524288,
                            headers=headers,
                            json={"model": model},
                            follow_redirects=False,
                        )
                        if metadata.status_code == 200:
                            value = metadata.json().get("capabilities")
                            if isinstance(value, list) and all(isinstance(c, str) for c in value):
                                capabilities = value
                    for capability in ("chat", "streaming", "tools", "image_input", "audio_input"):
                        supported = (
                            {
                                "chat": "completion",
                                "tools": "tools",
                                "image_input": "vision",
                                "audio_input": "audio",
                            }[capability]
                            in capabilities
                            if capabilities is not None and capability != "streaming"
                            else None
                        )
                        checks.append(
                            {
                                "id": f"model:{model}:{capability}",
                                "model_id": model,
                                "capability": capability,
                                "supported": supported,
                                "verified": False,
                                "status": "failed" if supported is False else "unverified",
                                "message": f"The model does not advertise {capability} support."
                                if supported is False
                                else f"{capability.capitalize()} remains unverified through the native API.",
                            }
                        )
        except Exception:
            checks.append(
                {
                    "id": "discovery",
                    "status": "unverified",
                    "message": "Capability discovery was incomplete; generation remains unverified.",
                }
            )
        finally:
            with suppress(Exception):
                await client.stop()
        return checks
