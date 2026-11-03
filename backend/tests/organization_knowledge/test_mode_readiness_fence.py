# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.data.transaction import current_unit_of_work

from koinon.organization_knowledge.transitions.readiness_fence import (
    ModeReadinessFence,
    ModeReadinessSnapshot,
)
from koinon.security.authority import primary_authority

pytest_plugins = ("test_organization_knowledge_service",)


async def test_readiness_fence_requires_caller_owned_primary_write_transaction():
    primary = SimpleNamespace(matches=AsyncMock(return_value=True))
    fence = ModeReadinessFence(primary, None)
    with pytest.raises(RuntimeError, match="primary write transaction"):
        async with fence.hold("north", ModeReadinessSnapshot(1, 2)):
            pytest.fail("An unowned row lock cannot fence a later primary commit")
    primary.matches.assert_not_awaited()


async def test_native_fence_outlives_primary_commit_with_outer_exit_stack(knowledge):
    from contextlib import AsyncExitStack

    primary = SimpleNamespace(matches=AsyncMock(return_value=True))
    fence = ModeReadinessFence(primary, None)
    events = []

    @asynccontextmanager
    async def hold(tenant, expected):
        events.append("native_locked")
        assert current_unit_of_work("primary") is not None
        yield
        assert current_unit_of_work("primary") is None
        events.append("native_released")

    fence.native = lambda: SimpleNamespace(hold=hold)
    async with AsyncExitStack() as stack:
        async with primary_authority(read_only=False):
            await stack.enter_async_context(fence.hold("north", ModeReadinessSnapshot(1, 2)))
            events.append("primary_work")
        events.append("primary_committed")
        assert events[-1] == "primary_committed" and "native_released" not in events
    assert events == ["native_locked", "primary_work", "primary_committed", "native_released"]
