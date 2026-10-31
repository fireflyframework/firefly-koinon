# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Run durable conversations independently of the API and optional user interface."""

import asyncio
from contextlib import suppress
from uuid import uuid4

from koinon.operations.settings import OperationalSettings
from koinon.workers.admission import WorkAdmission, WorkAdmissionUnavailable


async def run_consumers(
    queue,
    executor,
    settings: OperationalSettings,
    *,
    stop: asyncio.Event | None = None,
    admission: WorkAdmission,
):
    worker_id = str(uuid4())

    async def consume(index: int):
        identity = f"{worker_id}-{index}"
        while stop is None or not stop.is_set():
            try:
                async with admission.hold("conversation"):
                    if stop is not None and stop.is_set():
                        return
                    run = await queue.claim(identity)
                    if run is not None:
                        await executor.execute(run.id, identity)
            except WorkAdmissionUnavailable:
                if stop is not None and stop.is_set():
                    return
                run = None
            if run is None:
                if stop is None:
                    await asyncio.sleep(0.5)
                else:
                    with suppress(TimeoutError):
                        await asyncio.wait_for(stop.wait(), 0.5)
                continue

    async with asyncio.TaskGroup() as tasks:
        for index in range(settings.worker_concurrency):
            tasks.create_task(consume(index))


async def run_worker():
    from koinon.worker import run_worker as complete_worker

    await complete_worker()


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(run_worker())
