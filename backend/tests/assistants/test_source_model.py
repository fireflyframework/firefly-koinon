# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Every model boundary checks current authority, including retries and token counting."""

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.usage import RequestUsage

from koinon.assistants.source_model import SourceAuthorizedModel
from koinon.integrations.content_sources.errors import SourceError


@pytest.mark.parametrize("boundary", ["request", "count_tokens", "stream"])
@pytest.mark.parametrize("denied_before", [True, False])
async def test_model_boundary_denies_before_input_and_rechecks_before_return(boundary, denied_before):
    calls = []
    allowed = not denied_before

    async def check():
        if not allowed:
            raise SourceError("access_denied")

    def consume(messages):
        nonlocal allowed
        calls.append(messages)
        allowed = False

    def respond(messages, info):
        consume(messages)
        return ModelResponse(parts=[TextPart("Protected model output")])

    async def stream(messages, info):
        consume(messages)
        yield "Protected model output"

    class ControlledModel(FunctionModel):
        async def count_tokens(self, messages, settings, parameters):
            consume(messages)
            return RequestUsage(input_tokens=3)

    model = SourceAuthorizedModel(ControlledModel(function=respond, stream_function=stream), check)
    messages = [ModelRequest(parts=[UserPromptPart("Protected source content")])]
    released = []
    with pytest.raises(SourceError):
        if boundary == "stream":
            async with model.request_stream(messages, None, ModelRequestParameters()) as response:
                async for _ in response:
                    pass
            released.append("stream")
        else:
            released.append(await getattr(model, boundary)(messages, None, ModelRequestParameters()))
    assert calls == ([] if denied_before else [messages])
    assert released == []


async def test_stream_revocation_stops_events_before_the_consumer_receives_them():
    allowed = True

    async def check():
        if not allowed:
            raise SourceError("access_denied")

    async def stream(messages, info):
        nonlocal allowed
        yield "Allowed first"
        allowed = False
        yield "SENSITIVE_late"

    model = SourceAuthorizedModel(FunctionModel(stream_function=stream), check)
    observed = []
    with pytest.raises(SourceError):
        async with model.request_stream([], None, ModelRequestParameters()) as response:
            async for event in response:
                observed.append(repr(event))
    assert any("Allowed first" in value for value in observed)
    assert not any("SENSITIVE_late" in value for value in observed)
