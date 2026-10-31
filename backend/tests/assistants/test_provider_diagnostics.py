# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Provider adapter identity does not establish observed model capabilities."""

from types import SimpleNamespace

import pytest

from koinon.assistants.connections import DEFAULT_URLS, provider_state


def provider(kind, api):
    return SimpleNamespace(
        kind=kind,
        api=api,
        base_url=DEFAULT_URLS[kind],
        enabled=True,
        model_ids=["fixture"],
        secret_ciphertext=None if kind == "ollama" else b"fixture-ciphertext",
        revision=1,
        validated_revision=1,
        checks=[
            {"id": "connection", "status": "passed"},
            {"id": "models", "status": "passed"},
        ],
    )


@pytest.mark.parametrize(
    ("kind", "api", "model_class"),
    [
        ("ollama", "chat", "OpenAIChatModel"),
        ("openai", "chat", "OpenAIChatModel"),
        ("openai", "responses", "OpenAIResponsesModel"),
        ("anthropic", "messages", "AnthropicModel"),
    ],
)
def test_adapter_identity_preserves_provider_and_transport_without_qualifying_generation(
    kind, api, model_class
):
    state = provider_state(provider(kind, api))
    adapter = state["native_adapter"]
    assert adapter["provider_identity"] == kind
    assert adapter["model_class"] == model_class
    assert adapter["profile_status"] == "unverified"
    assert adapter["ownership"] == "deployment" and adapter["read_only"] is True
    assert state["connected"] and state["discovered"] and not state["validated"]
    assert all(
        capability["verified"] is False
        for key, capability in state["model_capabilities"][0].items()
        if key in {"chat", "streaming", "tools", "image_input", "audio_input"}
    )
    if kind == "ollama":
        assert "OpenAI-compatible chat transport" in adapter["reason"]
        assert "provider-specific profile behavior remains unqualified" in adapter["reason"]


def test_ollama_adapter_identity_does_not_refresh_stale_discovery_or_profile_evidence():
    configured = provider("ollama", "chat")
    configured.revision = 2
    state = provider_state(configured)
    assert state["native_adapter"]["provider_identity"] == "ollama"
    assert state["native_adapter"]["profile_status"] == "unverified"
    assert not state["connected"] and not state["discovered"] and not state["validated"]
