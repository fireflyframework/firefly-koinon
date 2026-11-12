# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pyfly.kernel import ConflictException
from test_bulk_native import bulk as bulk
from test_bulk_native import request

from koinon.knowledge.bulk.ports import SourceIntakeAdmission, SourceIntakeItem


async def test_source_admission_without_guard_creates_no_catalog_or_batch(bulk):
    from koinon.knowledge.bulk.repositories import BulkRepository

    records = bulk.context.get_bean(BulkRepository)
    before = await bulk.catalog.catalog_repository.count()
    admission = SourceIntakeAdmission(
        "north",
        "issuer|editor",
        "mapping",
        1,
        1,
        "run",
        tuple(bulk.target[key] for key in ("workspace_id", "project_id", "parent_id")),
        (SourceIntakeItem("object", 1, "v1", "observation", "work", 1, 0, "a" * 64),),
    )
    with pytest.raises(ConflictException, match="source"):
        await bulk.service.create(
            "issuer|editor", "north", request(bulk.target), "source-key", _source_admission=admission
        )
    assert await records.count() == 0
    assert await bulk.catalog.catalog_repository.count() == before
