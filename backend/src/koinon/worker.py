# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Run all durable consumers without an HTTP listener."""

import asyncio
import signal
from contextlib import suppress


async def run_worker():
    from koinon.app import create_application
    from koinon.operations.configuration import environment_configuration
    from koinon.workers.runtime import WorkerRuntime

    application = create_application(environment_configuration(), role="worker")
    context = application.state.context
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    installed = []
    for event in (signal.SIGTERM, signal.SIGINT):
        with suppress(NotImplementedError):
            loop.add_signal_handler(event, stopping.set)
            installed.append(event)
    try:
        await context.start()
        wait = asyncio.create_task(stopping.wait())
        runtime = asyncio.create_task(context.get_bean(WorkerRuntime).wait())
        try:
            done, _ = await asyncio.wait({wait, runtime}, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        finally:
            wait.cancel()
            runtime.cancel()
            await asyncio.gather(wait, runtime, return_exceptions=True)
    finally:
        await context.stop()
        for event in installed:
            loop.remove_signal_handler(event)


if __name__ == "__main__":
    asyncio.run(run_worker())
