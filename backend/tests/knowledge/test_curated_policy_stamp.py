# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from test_curated_intents import curated as curated
from test_curated_native_events import native_lifecycle as native_lifecycle
from test_curated_release_fence import _two_workspace_case


async def test_policy_snapshot_must_match_fresh_authority_cut(curated, native_lifecycle):
    from sqlalchemy import update

    from koinon.catalog.entities import Membership
    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.curated.whole import CuratedWholeVersionReader

    reads, corpus, selected, published, primary = await _two_workspace_case(curated, native_lifecycle)
    reader = curated[3].get_bean(CuratedWholeVersionReader)
    metas = tuple([await reader.pin("issuer|reader", "north", "owned", selection) for selection in selected])

    async def grants(first, second):
        async with primary.engine.begin() as connection:
            await connection.execute(
                update(Membership).where(Membership.id == "reader-0").values(active=first)
            )
            await connection.execute(
                update(Membership).where(Membership.id == "reader-1").values(active=second)
            )

    await grants(True, False)
    original = reader.pin

    async def pin_then_swap(subject, tenant, workspace, selection):
        value = await original(subject, tenant, workspace, selection)
        if selection.item_id == selected[0].item_id:
            await grants(True, True)
        else:
            await grants(True, False)
        return value

    original_observe = reader.release.observe
    calls = 0

    async def observe_then_grant(*args, **kwargs):
        nonlocal calls
        value = await original_observe(*args, **kwargs)
        calls += 1
        if calls == 1:
            await grants(True, True)
        return value

    reader.release.observe = observe_then_grant
    reader.pin = pin_then_swap
    with pytest.raises(AccessDenied) as caught:
        await reader.authorize("issuer|reader", "north", metas)

    assert caught.value.code == "KNOWLEDGE_AUTHORITY_CHANGED"
