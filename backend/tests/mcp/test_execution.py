# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""MCP tasks retain only their installation registry and reauthenticate independently."""

import asyncio

import pytest
from pyfly.context import ApplicationContext
from pyfly.context.request_context import RequestContext
from pyfly.core import Config
from pyfly.data.transaction import TransactionManagerRegistry, bind_registry, installed_registry
from pyfly.data.transaction.context import bind_state, current_state, reset_state
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder

from koinon.mcp.execution import isolated_application_call


async def test_isolation_retains_only_explicit_application_registry():
    owner, peer = TransactionManagerRegistry(), TransactionManagerRegistry()
    context = ApplicationContext(Config({}))
    context.container.register_instance(TransactionManagerRegistry, owner)
    request = RequestContext.init()
    token = bind_state(current_state().with_read_only(True))
    try:
        with bind_registry(peer), SecurityContextHolder.using(SecurityContext(user_id="outer")):

            async def operation():
                assert installed_registry() is owner
                assert RequestContext.current() is None
                assert not current_state().units and not current_state().read_only
                assert SecurityContextHolder.get_context() is None
                return "owned"

            assert await isolated_application_call(context, operation) == "owned"
            assert installed_registry() is peer
            assert RequestContext.current() is request
            assert current_state().read_only
            assert SecurityContextHolder.get_context().user_id == "outer"
    finally:
        reset_state(token)
        RequestContext.clear()


async def test_unowned_task_masks_another_installation_and_cancellation_preserves_caller():
    peer = TransactionManagerRegistry()
    started = asyncio.Event()

    async def operation():
        assert installed_registry() is None
        started.set()
        await asyncio.Event().wait()

    with bind_registry(peer):
        task = asyncio.create_task(isolated_application_call(None, operation))
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert installed_registry() is peer
