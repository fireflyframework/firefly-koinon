# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import ServiceUnavailableException
from test_facade import context as context
from test_facade import upload
from test_policy_runtime_scope import snapshot

from koinon.catalog.errors import AccessDenied
from koinon.organization_knowledge.runtime import bind_snapshot


async def test_direct_search_records_and_forwards_one_authorized_settings_snapshot(context):
    facade, _, domains, tree, _ = context
    await upload(context)
    selected = snapshot(revision=2)
    facade.knowledge_settings = SimpleNamespace(snapshot=AsyncMock(return_value=selected))
    result = await facade.search(
        "issuer|admin", "north", question="What is recorded?", workspace_id=tree["workspace"].id
    )
    facade.knowledge_settings.snapshot.assert_awaited_once_with("issuer|admin", "north")
    assert domains.search.await_args.kwargs["_knowledge_settings_snapshot"] == selected
    assert result["knowledge_settings_snapshot"] == selected.model_dump(mode="json")


async def test_direct_query_records_policy_without_changing_query_authority(context):
    facade, _, domains, _, _ = context
    dataset = await upload(context, mode="dataset")
    selected = snapshot(revision=2)
    facade.knowledge_settings = SimpleNamespace(snapshot=AsyncMock(return_value=selected))
    result = await facade.query(
        "issuer|admin", "north", dataset_id=dataset["assets"][0]["id"], question="Add the totals"
    )
    assert domains.query.await_args.kwargs["_knowledge_settings_snapshot"] == selected
    assert result["knowledge_settings_snapshot"] == selected.model_dump(mode="json")
    assert result["query_id"] == "native-query"


async def test_admitted_run_policy_wins_over_later_organization_edits(context):
    facade, _, domains, tree, _ = context
    await upload(context)
    admitted, current = snapshot(revision=1), snapshot(mode="rlm", revision=2)
    facade.knowledge_settings = SimpleNamespace(snapshot=AsyncMock(return_value=current))
    with bind_snapshot(admitted, "issuer|admin"):
        result = await facade.search(
            "issuer|admin", "north", question="What is recorded?", workspace_id=tree["workspace"].id
        )
    facade.knowledge_settings.snapshot.assert_not_awaited()
    assert domains.search.await_args.kwargs["_knowledge_settings_snapshot"] == admitted
    assert result["knowledge_settings_snapshot"]["revision"] == 1


async def test_other_subject_cannot_borrow_admitted_settings_or_reload_defaults(context):
    facade, _, domains, tree, _ = context
    await upload(context)
    facade.knowledge_settings = SimpleNamespace(snapshot=AsyncMock(return_value=snapshot()))
    with bind_snapshot(snapshot(), "issuer|admin"), pytest.raises(AccessDenied):
        await facade.search(
            "issuer|reader", "north", question="What is recorded?", workspace_id=tree["workspace"].id
        )
    facade.knowledge_settings.snapshot.assert_not_awaited()
    domains.search.assert_not_awaited()


async def test_missing_policy_service_blocks_inference_instead_of_guessing_defaults(context):
    facade, _, domains, tree, _ = context
    await upload(context)
    facade.knowledge_settings = None
    with pytest.raises(ServiceUnavailableException, match="knowledge settings"):
        await facade.search(
            "issuer|admin", "north", question="What is recorded?", workspace_id=tree["workspace"].id
        )
    domains.search.assert_not_awaited()
