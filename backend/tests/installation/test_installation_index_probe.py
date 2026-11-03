# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Installation qualification must release authority before provider I/O."""

import pytest
from pyfly.data.transaction import current_unit_of_work
from test_installation_index_roundtrip import persisted_indexes as persisted_indexes

from koinon.installation.authority import InstallationError


@pytest.mark.parametrize("changed", [False, True])
async def test_installation_probe_releases_primary_and_rechecks_provider(
    persisted_indexes, monkeypatch, changed
):
    state = persisted_indexes
    calls = []

    async def qualify(provider, value):
        assert current_unit_of_work("primary") is None
        calls.append(provider.id)
        if changed:
            repository = state.reader.planner.providers
            fresh = await repository.find_by_id(provider.id)
            fresh.revision += 1
            await repository.save(fresh)
        return {"dimensions": 1536, "storage_dimensions": 1536}

    async def prepare(tenant, value):
        provider = await state.reader.planner.provider(tenant, value.provider_id, value.model_id)
        return provider, await qualify(provider, value)

    monkeypatch.setattr(state.reader.planner, "prepare", prepare)
    monkeypatch.setattr(state.reader.planner, "qualify", qualify)
    if changed:
        with pytest.raises(InstallationError, match="INSTALLATION_PROVIDER_CHANGED"):
            await state.writer.intent(state.permit, state.value)
        assert await state.reader.records.find_all() == []
    else:
        identifier = await state.writer.intent(state.permit, state.value)
        assert await state.writer.intent(state.permit, state.value) == identifier
    assert len(calls) == 1
