# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Run durable conversations independently of the API and optional user interface."""

import asyncio
from contextlib import suppress
from uuid import uuid4

from koinon.operations.settings import OperationalSettings


async def run_consumers(queue, executor, settings: OperationalSettings):
    worker_id = str(uuid4())

    async def consume(index: int):
        identity = f"{worker_id}-{index}"
        while True:
            run = await queue.claim(identity)
            if run is None:
                await asyncio.sleep(0.5)
                continue
            await executor.execute(run.id, identity)

    async with asyncio.TaskGroup() as tasks:
        for index in range(settings.worker_concurrency):
            tasks.create_task(consume(index))


async def run_worker():
    from koinon.assistants.execution import AssistantExecutor
    from koinon.assistants.queue import AssistantQueue
    from koinon.main import app

    context = app.state.context
    await context.start()
    try:
        await run_consumers(
            context.get_bean(AssistantQueue),
            context.get_bean(AssistantExecutor),
            context.get_bean(OperationalSettings),
        )
    finally:
        await context.stop()


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(run_worker())
