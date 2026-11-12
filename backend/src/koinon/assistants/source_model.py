# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reauthorize every conversational model boundary, including retries and token counts."""

from contextlib import asynccontextmanager

from pydantic_ai.models.wrapper import WrapperModel


class _AuthorizedStream:
    """Preserve the provider response while fencing every event delivered to the agent."""

    def __init__(self, response, check):
        self.response, self.check = response, check

    def __getattr__(self, name):
        return getattr(self.response, name)

    async def __aiter__(self):
        async for event in self.response:
            await self.check()
            yield event


class SourceAuthorizedModel(WrapperModel):
    def __init__(self, wrapped, check):
        super().__init__(wrapped)
        self.check = check

    async def request(self, messages, model_settings, model_request_parameters):
        await self.check()
        result = await self.wrapped.request(messages, model_settings, model_request_parameters)
        await self.check()
        return result

    async def count_tokens(self, messages, model_settings, model_request_parameters):
        await self.check()
        result = await self.wrapped.count_tokens(messages, model_settings, model_request_parameters)
        await self.check()
        return result

    @asynccontextmanager
    async def request_stream(self, messages, model_settings, model_request_parameters, run_context=None):
        await self.check()
        async with self.wrapped.request_stream(
            messages, model_settings, model_request_parameters, run_context
        ) as response:
            yield _AuthorizedStream(response, self.check)
        await self.check()
