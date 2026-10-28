# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from test_facade import context as context
from test_facade import upload
from test_legacy_read import admission, request


@pytest.mark.parametrize("status", ["pending", "error"])
@pytest.mark.parametrize("target", ["dataset", "unbound_table", "workspace"])
async def test_retained_reads_cannot_observe_unfinished_dataset_sections(context, status, target):
    from pyfly.kernel import ConflictException

    facade, catalog, _, tree, _ = context
    dataset = (await upload(context, "dataset"))["assets"][0]["id"]
    await catalog.update("issuer|admin", "north", dataset, {"status": status})
    guard, _ = admission(facade)

    async def lookup(domain, kind, identifier, tenant, workspace):
        return {
            "id": identifier,
            "tenant_id": tenant,
            "workspace_id": workspace,
            **({"dataset_id": "native-dataset"} if kind == "table" else {}),
        }

    guard._lookup = AsyncMock(side_effect=lookup)
    parameters = (
        {"dataset_id": "native-dataset"}
        if target == "dataset"
        else {"table_id": "new-unbound-table"}
        if target == "unbound_table"
        else {}
    )
    with pytest.raises(ConflictException) as error:
        await guard.verify(
            "structured",
            request(),
            SimpleNamespace(subject="issuer|reader"),
            "north",
            tree["workspace"].id,
            parameters,
        )
    assert error.value.code == "DATASET_NOT_READY"
    if target != "unbound_table":
        guard._lookup.assert_not_awaited()


async def test_specific_ready_dataset_remains_readable_when_another_dataset_is_unfinished(context):
    facade, catalog, domains, tree, _ = context
    failed = (await upload(context, "dataset"))["assets"][0]["id"]
    await catalog.update("issuer|admin", "north", failed, {"status": "error"})
    native = str(uuid4())
    domains.ingest_dataset.return_value = {"dataset_id": native, "file_id": str(uuid4()), "tables": []}
    await upload(context, "dataset")
    guard, _ = admission(facade)
    guard._lookup = AsyncMock(
        return_value={
            "id": native,
            "tenant_id": "north",
            "workspace_id": "native-workspace",
        }
    )
    await guard.verify(
        "structured",
        request(),
        SimpleNamespace(subject="issuer|reader"),
        "north",
        tree["workspace"].id,
        {"dataset_id": native},
    )


async def test_ignored_query_selectors_cannot_turn_a_workspace_list_into_a_scoped_read(context):
    from pyfly.kernel import ConflictException

    facade, catalog, domains, tree, _ = context
    failed = (await upload(context, "dataset"))["assets"][0]["id"]
    await catalog.update("issuer|admin", "north", failed, {"status": "error"})
    native = str(uuid4())
    domains.ingest_dataset.return_value = {"dataset_id": native, "file_id": str(uuid4()), "tables": []}
    await upload(context, "dataset")
    guard, _ = admission(facade)

    async def lookup(domain, kind, identifier, tenant, workspace):
        return {
            "id": identifier,
            "tenant_id": tenant,
            "workspace_id": workspace,
            **({"dataset_id": native} if kind == "query" else {}),
        }

    guard._lookup = AsyncMock(side_effect=lookup)
    with pytest.raises(ConflictException) as error:
        await guard.verify(
            "structured",
            request(b"query_id=unrelated-ready-query"),
            SimpleNamespace(subject="issuer|reader"),
            "north",
            tree["workspace"].id,
            {},
        )
    assert error.value.code == "DATASET_NOT_READY"
    guard._lookup.assert_not_awaited()
