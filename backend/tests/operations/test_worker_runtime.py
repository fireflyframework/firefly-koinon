# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
from types import SimpleNamespace

import pytest
from pyfly.container import Container
from pyfly.context import ApplicationContext
from pyfly.core import Config

from koinon.assistants.execution import AssistantExecutor
from koinon.assistants.queue import AssistantQueue
from koinon.operations.process import process_configuration
from koinon.operations.settings import OperationalSettings
from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings
from koinon.workers.runtime import WorkerRuntime


async def test_worker_stops_claiming_and_finishes_inflight_before_context_resources_close():
    entered, release = asyncio.Event(), asyncio.Event()
    claims, events = [], []

    class Queue:
        async def claim(self, owner):
            claims.append(owner)
            return SimpleNamespace(id="one")

    class Executor:
        async def execute(self, run_id, owner):
            entered.set()
            await release.wait()
            events.append("finished")

    class Resource:
        async def start(self):
            pass

        async def stop(self):
            events.append("resource closed")

    context = ApplicationContext(Config(process_configuration({"koinon": {"process": {"role": "worker"}}})))
    context.container.register_instance(AssistantQueue, Queue())
    context.container.register_instance(AssistantExecutor, Executor())
    context.container.register_instance(OperationalSettings, OperationalSettings())
    context.container.register_instance(Resource, Resource())
    context.container.register_instance(WorkAdmission, WorkAdmission(WorkAdmissionSettings()))
    context.register_bean(WorkerRuntime)
    await context.start()
    await asyncio.wait_for(entered.wait(), 1)
    stop = asyncio.create_task(context.stop())
    await asyncio.sleep(0.025)
    assert len(claims) == 1 and "resource closed" not in events
    release.set()
    await asyncio.wait_for(stop, 1)
    assert events == ["finished", "resource closed"]


async def test_api_context_never_instantiates_complete_worker_runtime():
    context = ApplicationContext(Config(process_configuration({})))
    context.container.register_instance(WorkAdmission, WorkAdmission(WorkAdmissionSettings()))
    context.register_bean(WorkerRuntime)
    await context.start()
    try:
        assert not context.container.contains_type(WorkerRuntime)
    finally:
        await context.stop()


async def test_managed_worker_refuses_missing_callback_authority_before_starting_consumers():
    from flyquery.core.services.callbacks.callback_worker import CallbackWorker

    container = Container()
    container.register(CallbackWorker)
    runtime = WorkerRuntime(
        SimpleNamespace(),
        SimpleNamespace(),
        OperationalSettings(),
        container,
        WorkAdmission(WorkAdmissionSettings()),
    )
    with pytest.raises(RuntimeError, match="requires callback delivery authority"):
        await runtime.start()
    assert runtime._task is None


async def test_complete_worker_accepts_native_interface_binding_and_supervises_callback_consumer():
    from flyquery.core.services.callbacks.access import CallbackDeliveryAccess
    from flyquery.core.services.callbacks.callback_worker import CallbackWorker

    entered, stopped = asyncio.Event(), asyncio.Event()

    class Access(CallbackDeliveryAccess):
        async def authorize(self, claim):
            pass

    class Callback:
        async def run_forever(self):
            entered.set()
            await stopped.wait()

        async def stop(self):
            stopped.set()

    class Queue:
        async def claim(self, worker):
            return None

    container = Container()
    container.register(Access)
    container.bind(CallbackDeliveryAccess, Access)
    from flyquery.core.services.callbacks.admission import CallbackWorkAdmission

    from koinon.workers.callbacks import ManagedCallbackWorkAdmission

    container.register_instance(
        CallbackWorkAdmission, ManagedCallbackWorkAdmission(WorkAdmission(WorkAdmissionSettings()))
    )
    container.register_instance(CallbackWorker, Callback())
    runtime = WorkerRuntime(
        Queue(), SimpleNamespace(), OperationalSettings(), container, WorkAdmission(WorkAdmissionSettings())
    )
    await runtime.start()
    try:
        await asyncio.wait_for(entered.wait(), 1)
        assert not container.contains_type(CallbackDeliveryAccess)
    finally:
        await runtime.stop()
    assert stopped.is_set()


async def test_managed_worker_refuses_missing_callback_admission_before_claims():
    from flyquery.core.services.callbacks.access import CallbackDeliveryAccess
    from flyquery.core.services.callbacks.callback_worker import CallbackWorker

    class Access(CallbackDeliveryAccess):
        async def authorize(self, claim):
            pass

    container = Container()
    container.register(CallbackWorker)
    container.register(Access)
    container.bind(CallbackDeliveryAccess, Access)
    runtime = WorkerRuntime(
        SimpleNamespace(),
        SimpleNamespace(),
        OperationalSettings(),
        container,
        WorkAdmission(WorkAdmissionSettings()),
    )
    with pytest.raises(RuntimeError, match="requires callback work admission"):
        await runtime.start()
    assert runtime._task is None
