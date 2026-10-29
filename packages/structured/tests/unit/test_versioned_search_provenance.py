# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import sqlglot
from sqlglot import exp

from flyquery.core.services.retrieval.search_index import _schema_hit
from flyquery.core.services.retrieval.versioned_search import schema_rows
from flyquery.web.conventions.context import TenantContext, set_tenant_context


async def test_versioned_schema_search_returns_the_recorded_snapshot_identity():
    workspace, dataset, snapshot, table = (uuid4() for _ in range(4))
    row = {
        "id": uuid4(),
        "qualified_name": "values.total",
        "description": "Recorded total",
        "data_type": "INTEGER",
        "table_id": table,
        "kind": "COLUMN",
        "snapshot_id": snapshot,
        "profile_json": {},
        "sample_values_json": [],
        "governance_json": {},
        "score": 0.9,
    }
    result = SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: [row]))
    session = SimpleNamespace(execute=AsyncMock(return_value=result))
    context = set_tenant_context(
        TenantContext(tenant_id="tenant", workspace_id=str(workspace), actor="actor", correlation_id="test")
    )
    try:
        rows = await schema_rows(
            session,
            SimpleNamespace(storage_dimensions=3, space_id="verified-space"),
            [0.1, 0.2, 0.3],
            dataset,
            12,
        )
    finally:
        context.var.reset(context.token)

    query, parameters = session.execute.await_args.args
    projected = sqlglot.parse_one(str(query), read="postgres").expressions
    assert any(
        isinstance(column, exp.Column) and column.table == "o" and column.name == "snapshot_id"
        for column in projected
    ), "Versioned retrieval must project the immutable snapshot used by the provenance receipt"
    assert parameters["workspace"] == workspace and parameters["ds"] == dataset
    assert parameters["set_id"] == "verified-space"
    hit = _schema_hit(rows[0], float(rows[0]["score"]))
    assert hit.metadata["snapshot_id"] == str(snapshot)
    assert hit.metadata["table_id"] == str(table)
