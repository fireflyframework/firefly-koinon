# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import importlib
import runpy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.mark.parametrize("domain", ["bulk", "bulk_queries"])
async def test_module_entrypoint_resolves_canonical_managed_worker_without_starting_any_service(
    domain, monkeypatch
):
    from pyfly.container import Container

    import koinon.app
    import koinon.operations.configuration
    from koinon.knowledge.bulk.settings import BulkSettings

    module = importlib.import_module("koinon.knowledge." + domain + ".worker")
    worker_type = module.BulkWorker if domain == "bulk" else module.QueryWorker
    queue_type = module.BulkQueue if domain == "bulk" else module.QueryBatchQueue
    namespace = runpy.run_path(module.__file__, run_name="isolated_worker_entrypoint")
    assert namespace[worker_type.__name__] is not worker_type
    worker = SimpleNamespace(settings=BulkSettings(), tick=AsyncMock(side_effect=asyncio.CancelledError))
    container = Container()
    container.register_instance(worker_type, worker)
    container.register_instance(queue_type, SimpleNamespace())
    context = SimpleNamespace(start=AsyncMock(), stop=AsyncMock(), get_bean=container.resolve)
    monkeypatch.setattr(
        koinon.app, "create_application", lambda _: SimpleNamespace(state=SimpleNamespace(context=context))
    )
    monkeypatch.setattr(koinon.operations.configuration, "environment_configuration", lambda: {})
    with pytest.raises(asyncio.CancelledError):
        await namespace["run_worker"]()
    worker.tick.assert_awaited_once()
    context.stop.assert_awaited_once()
