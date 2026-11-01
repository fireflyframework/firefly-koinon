# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Keep application ownership in fresh tasks without borrowing request or transaction state."""

import asyncio
import contextvars
from collections.abc import Awaitable, Callable

from pyfly.context import ApplicationContext
from pyfly.data.transaction import TransactionManagerRegistry, bind_registry


async def isolated_application_call[T](
    context: ApplicationContext | None, operation: Callable[[], Awaitable[T]]
) -> T:
    async def owned() -> T:
        registry = context.get_bean(TransactionManagerRegistry) if context is not None else None
        with bind_registry(registry):
            return await operation()

    return await asyncio.create_task(owned(), context=contextvars.Context())
