# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import contextvars
from types import SimpleNamespace

from koinon.assistants.worker import run_consumers
from koinon.corporate_profiles.worker import CorporateProfileWorker
from koinon.knowledge.attachments.worker import AttachmentWorker
from koinon.knowledge.indexes.worker import IndexWorker
from koinon.operations.settings import OperationalSettings
from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings
from koinon.workers.ingestion import IngestionDrain


async def test_all_worker_entrypoints_wait_before_claiming_or_loading_job_payloads():
    from flyquery.config import FlyquerySettings
    from flyquery.core.services.callbacks.callback_worker import CallbackWorker

    gate = WorkAdmission(WorkAdmissionSettings())
    claims = []
    stop = asyncio.Event()

    async def claim_conversation(owner):
        claims.append("conversation")
        stop.set()

    async def claim_index(*args):
        claims.append("index")

    async def claim_attachment():
        claims.append("attachment")

    async def claim_profile(*args, **kwargs):
        claims.append("profile")
        return []

    async def claim_callback(**kwargs):
        claims.append("callback")
        assert kwargs["limit"] == 1, "Never reserve an unadmitted local callback batch"
        return []

    async def scopes():
        return [{"tenant_id": "fixture", "id": "00000000-0000-0000-0000-000000000001"}]

    index = IndexWorker(
        None,
        SimpleNamespace(claim=claim_index),
        SimpleNamespace(enabled=True, validate=lambda: None, lease_seconds=120),
        gate,
    )
    attachment = AttachmentWorker(
        SimpleNamespace(
            reader=SimpleNamespace(settings=SimpleNamespace(worker_enabled=True, validate=lambda: None))
        ),
        None,
        SimpleNamespace(),
        gate,
    )
    attachment.claim = claim_attachment
    profile = CorporateProfileWorker(
        SimpleNamespace(claim=claim_profile), SimpleNamespace(worker_enabled=True), gate
    )
    drain = IngestionDrain(None, None, None, gate)

    async def discover(domain):
        claims.append(domain)

    drain._execute_one = discover
    callback = CallbackWorker(
        SimpleNamespace(claim_due_batch=claim_callback),
        FlyquerySettings(),
        SimpleNamespace(scopes=scopes),
        work_admission=lambda: SimpleNamespace(admit=lambda: gate.hold("callback")),
    )
    async with gate.hold("index"):
        coroutines = [
            run_consumers(
                SimpleNamespace(claim=claim_conversation),
                None,
                OperationalSettings(),
                stop=stop,
                admission=gate,
            ),
            index.tick(),
            attachment.tick(),
            profile.tick(),
            drain._one("canon"),
            drain._one("structured"),
            callback._drain_scopes(None),
        ]
        tasks = [asyncio.create_task(c, context=contextvars.Context()) for c in coroutines]
        await asyncio.sleep(0.01)
        assert claims == [] and gate.worker_waiting >= 7
    await asyncio.wait_for(asyncio.gather(*tasks), 1)
    assert sorted(claims) == sorted(
        ["conversation", "index", "attachment", "profile", "canon", "structured", "callback"]
    )
    assert gate.worker_active == gate.worker_waiting == 0


async def test_native_api_query_waits_before_opening_models_and_preserves_separate_pool():
    from contextlib import asynccontextmanager

    from koinon.knowledge.adapters import NativeDomains, model_bound

    opened = []
    release = asyncio.Event()
    gate = WorkAdmission(WorkAdmissionSettings())

    class Domain(NativeDomains):
        def model_requirements(self, *args):
            return "search", ()

        @asynccontextmanager
        async def model_connections(self, *args, **kwargs):
            opened.append("model-open")
            yield

        @model_bound("canon")
        async def operation(self, **kwargs):
            await release.wait()

    domain = Domain(None, gate)
    first = asyncio.create_task(domain.operation(tenant_id="fixture", workspace_id="one", actor="reader"))
    await asyncio.sleep(0)
    second = asyncio.create_task(domain.operation(tenant_id="fixture", workspace_id="one", actor="reader"))
    await asyncio.sleep(0)
    assert opened == ["model-open"] and gate.api_active == 1
    async with gate.hold("index"):
        assert gate.worker_active == 1
    release.set()
    await asyncio.gather(first, second)
    assert opened == ["model-open", "model-open"] and gate.api_active == 0


async def test_native_composition_injects_one_configured_budget_into_api_and_callback_adapters():
    from flyquery.core.services.callbacks.admission import CallbackWorkAdmission
    from pyfly.context import ApplicationContext
    from pyfly.core import Config

    from koinon.knowledge.adapters import NativeDomains
    from koinon.workers.callbacks import ManagedCallbackWorkAdmission

    context = ApplicationContext(
        Config({"koinon": {"operations": {"admission": {"worker_capacity": 2, "api_capacity": 3}}}})
    )
    for kind in (WorkAdmissionSettings, WorkAdmission, NativeDomains, ManagedCallbackWorkAdmission):
        context.register_bean(kind)
    context.container.bind(CallbackWorkAdmission, ManagedCallbackWorkAdmission)
    await context.start()
    try:
        gate = context.get_bean(WorkAdmission)
        assert gate is context.get_bean(NativeDomains).admission
        assert context.get_bean(CallbackWorkAdmission).admission is gate
        assert gate._workers.bulkhead.max_concurrent == 2 and gate._api.bulkhead.max_concurrent == 3
    finally:
        await context.stop()
