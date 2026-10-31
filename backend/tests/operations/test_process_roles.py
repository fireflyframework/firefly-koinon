# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
from datetime import timedelta

import pytest
from pyfly.container import service
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.scheduling import scheduled

from koinon.operations.process import process_configuration


@pytest.mark.parametrize("role", ["api", "worker"])
async def test_process_role_controls_actual_native_scheduled_execution(role):
    fired = asyncio.Event()

    @service
    class Consumer:
        @scheduled(fixed_delay=timedelta(milliseconds=1))
        async def tick(self):
            fired.set()

    original = {"koinon": {"process": {"role": role}}, "pyfly": {"scheduling": {"enabled": role == "api"}}}
    values = process_configuration(original)
    context = ApplicationContext(Config(values))
    context.register_bean(Consumer)
    await context.start()
    try:
        if role == "worker":
            await asyncio.wait_for(fired.wait(), 1)
        else:
            await asyncio.sleep(0.025)
            assert not fired.is_set()
    finally:
        await context.stop()
    assert original["pyfly"]["scheduling"]["enabled"] == (role == "api")


def test_default_api_disables_all_worker_gates_and_worker_enables_complete_set():
    api = process_configuration({})
    assert api["koinon"]["process"]["role"] == "api"
    assert api["pyfly"]["scheduling"]["enabled"] is False
    for role in ("api", "worker"):
        values = process_configuration({"koinon": {"process": {"role": role}}})
        assert values["koinon"]["knowledge"]["indexes"]["enabled"] == (role == "worker")
        assert values["koinon"]["attachments"]["worker_enabled"] == (role == "worker")
        assert values["koinon"]["identity"]["profile_sync"]["worker_enabled"] == (role == "worker")


@pytest.mark.parametrize("role", ["", "both", ["worker"], True])
def test_process_role_rejects_ambiguous_or_untyped_configuration(role):
    with pytest.raises(ValueError, match="process.role"):
        process_configuration({"koinon": {"process": {"role": role}}})
