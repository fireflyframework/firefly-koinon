# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""One native consumer-phase lifecycle supervises the complete worker role."""

import asyncio
from contextlib import suppress

from pyfly.container import Container, service
from pyfly.container.exceptions import NoSuchBeanError
from pyfly.context.conditions import conditional_on_property
from pyfly.kernel.lifecycle import CONSUMER_PHASE

from koinon.assistants.execution import AssistantExecutor
from koinon.assistants.queue import AssistantQueue
from koinon.assistants.worker import run_consumers
from koinon.operations.settings import OperationalSettings
from koinon.workers.admission import WorkAdmission


@service(name="operations.worker_runtime")
@conditional_on_property("koinon.process.role", having_value="worker")
class WorkerRuntime:
    phase = CONSUMER_PHASE

    def __init__(
        self,
        queue: AssistantQueue,
        executor: AssistantExecutor,
        settings: OperationalSettings,
        container: Container,
        admission: WorkAdmission,
    ):
        self.queue, self.executor, self.settings, self.container = queue, executor, settings, container
        self.admission = admission
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._native = []

    async def start(self):
        from flyquery.core.services.callbacks.access import CallbackDeliveryAccess
        from flyquery.core.services.callbacks.admission import CallbackWorkAdmission
        from flyquery.core.services.callbacks.callback_worker import CallbackWorker

        if self.container.contains_type(CallbackWorker):
            try:
                self.container.resolve(CallbackDeliveryAccess)
            except NoSuchBeanError:
                raise RuntimeError("The managed worker requires callback delivery authority") from None
            try:
                self.container.resolve(CallbackWorkAdmission)
            except NoSuchBeanError:
                raise RuntimeError("The managed worker requires callback work admission") from None
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="koinon-worker")

    async def _run(self):
        from flyquery.core.services.callbacks.callback_worker import CallbackWorker
        from flyquery.core.services.retention.retention_worker import RetentionWorker

        async with asyncio.TaskGroup() as tasks:
            tasks.create_task(
                run_consumers(
                    self.queue, self.executor, self.settings, stop=self._stop, admission=self.admission
                )
            )
            for kind in (CallbackWorker, RetentionWorker):
                if self.container.contains_type(kind):
                    consumer = self.container.resolve(kind)
                    self._native.append(consumer)
                    tasks.create_task(consumer.run_forever())

    async def wait(self):
        if self._task is None:
            raise RuntimeError("Worker runtime has not started")
        await asyncio.shield(self._task)

    async def stop(self):
        self._stop.set()
        self.admission.close_workers()
        for consumer in self._native:
            request_stop = getattr(consumer, "request_stop", None)
            if request_stop is not None:
                request_stop()
            else:
                await consumer.stop()
        if self._task is not None:
            try:
                async with asyncio.timeout(20):
                    await asyncio.shield(self._task)
            except (TimeoutError, asyncio.CancelledError):
                self._task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._task
            finally:
                self._task = None
