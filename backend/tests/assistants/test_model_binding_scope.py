# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio

import pytest
from pydantic_ai.models.test import TestModel
from pyfly.kernel import ServiceUnavailableException


async def test_borrowed_model_scope_is_bound_to_actor_and_expires_in_copied_tasks():
    from koinon.assistants.model_bindings import BorrowedModel, bind_model, current_model_binding

    model = TestModel()
    binding = BorrowedModel(model, {"max_tokens": 256}, "ollama", "chat", "native")
    assert current_model_binding("north", "issuer|viewer") is None
    release = asyncio.Event()

    async def child():
        await release.wait()
        with pytest.raises(ServiceUnavailableException):
            current_model_binding("north", "issuer|viewer")

    with bind_model("north", "issuer|viewer", binding):
        assert current_model_binding("north", "issuer|viewer").model is model
        with pytest.raises(ServiceUnavailableException):
            current_model_binding("south", "issuer|viewer")
        with pytest.raises(ServiceUnavailableException):
            current_model_binding("north", "issuer|other")
        task = asyncio.create_task(child())
    release.set()
    await task
    assert current_model_binding("north", "issuer|viewer") is None
