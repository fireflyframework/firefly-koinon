# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import httpx
import pytest

from koinon_sdk import AgentInput, KoinonClient, ProviderInput


async def test_provider_null_is_distinct_from_omission_and_native_api_is_transmitted():
    calls = []

    def handle(request):
        import json

        calls.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "p",
                "name": "Provider",
                "kind": "openai",
                "api": "responses",
                "model_class": "OpenAIResponsesModel",
                "base_url": "https://api.openai.com/v1",
                "model_ids": ["fixture"],
                "enabled": True,
                "revision": 1,
                "secret_configured": False,
                "validated": False,
                "checks": [],
                "connected": True,
                "discovered": True,
            },
        )

    async with KoinonClient(
        "https://api.test/api/v1", token_provider=lambda: "caller", transport=httpx.MockTransport(handle)
    ) as client:
        result = await client.update_provider("north", "p", ProviderInput(api="responses", secret=None))
        await client.update_provider("north", "p", ProviderInput(name="Keep key"))
    assert calls == [{"api": "responses", "secret": None}, {"name": "Keep key"}]
    assert result.api == "responses" and result.model_class == "OpenAIResponsesModel" and not result.validated


def test_headless_model_options_reject_unbounded_or_arbitrary_native_overrides():
    from koinon_sdk import ModelParameters

    value = AgentInput(model_options=ModelParameters(max_tokens=512, store_responses=False))
    assert value.model_options.max_tokens == 512
    for options in (
        {"max_tokens": None},
        {"max_tokens": True},
        {"max_tokens": 16385},
        {"request_timeout": 121},
        {"temperature": float("inf")},
        {"extra_body": {}},
        {"model_class": "arbitrary.Class"},
    ):
        with pytest.raises(ValueError):
            ModelParameters.model_validate(options)


@pytest.mark.parametrize("mode", ["default", "native", None])
def test_output_mode_is_typed_and_preserves_explicit_null_separately_from_omission(mode):
    from koinon_sdk import ModelParameters

    value = AgentInput(model_options=ModelParameters(output_mode=mode))
    assert value.model_dump(exclude_unset=True)["model_options"] == {"output_mode": mode}
    assert "output_mode" not in ModelParameters().model_dump(exclude_unset=True)
    for invalid in ("auto", "tool", True):
        with pytest.raises(ValueError):
            ModelParameters.model_validate({"output_mode": invalid})
