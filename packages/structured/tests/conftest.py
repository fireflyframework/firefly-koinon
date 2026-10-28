# Copyright 2024-2026 Firefly Software Foundation
# Modifications Copyright 2026 Firefly Software Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Shared pytest fixtures for flyquery tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def native_unit_test_resources(monkeypatch):
    """Adapt explicit SQL assertion doubles to the native unit seam in tests only."""
    import sys
    from contextlib import asynccontextmanager

    import pyfly.data.transaction as transactions
    from sqlalchemy.ext.asyncio import async_sessionmaker

    native = transactions.infrastructure_unit

    @asynccontextmanager
    async def unit(factory=None, **options):
        if isinstance(factory, async_sessionmaker) or factory is None or isinstance(factory, str):
            async with native(factory, **options) as session:
                yield session
        else:
            async with factory() as session:
                yield session

    monkeypatch.setattr(transactions, "infrastructure_unit", unit)
    for name, module in tuple(sys.modules.items()):
        if name.startswith("flyquery.") and getattr(module, "infrastructure_unit", None) is native:
            monkeypatch.setattr(module, "infrastructure_unit", unit)


@pytest.fixture(autouse=True)
def reset_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default to disabled migrations and an in-memory SQLite KB for unit tests."""
    monkeypatch.setenv("FLYQUERY_RUN_MIGRATIONS", "false")


@pytest.fixture
async def native_agent_factory():
    """Own native agent resources through a fresh context for cache contract tests."""
    from pyfly.agentic.factory import AgentFactory
    from pyfly.context import ApplicationContext
    from pyfly.core import Config

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
    try:
        yield context.get_bean(AgentFactory)
    finally:
        await context.stop()
