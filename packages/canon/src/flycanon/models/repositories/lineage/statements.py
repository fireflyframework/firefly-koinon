# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Scoped SQL statements; application services exchange query values only."""

from sqlalchemy import select

from flycanon.core.services.sources.lineage.ports import LineageQuery
from flycanon.models.entities.source import SourceRow
from flycanon.models.entities.source_lineage import (
    source_artifacts,
    source_events,
    source_extractions,
    source_heads,
    source_parts,
    source_steps,
    source_versions,
)

TABLES = {
    "head": source_heads,
    "version": source_versions,
    "artifact": source_artifacts,
    "extraction": source_extractions,
    "part": source_parts,
    "step": source_steps,
    "event": source_events,
    "source": SourceRow.__table__,
}


def conditions(table, scope, source_id=None):
    result = [table.c.tenant_id == scope.tenant_id, table.c.workspace_id == scope.workspace_id]
    if source_id is not None:
        result.append(table.c.source_id == source_id)
    return result


def statement(query: LineageQuery):
    table = TABLES[query.entity]
    scope_columns = (
        table.c.tenant_id == query.scope.tenant_id,
        table.c.workspace_id == query.scope.workspace_id,
    )
    clauses = list(scope_columns)
    if query.source_id is not None:
        clauses.append(table.c.source_id == query.source_id)
    clauses.extend(table.c[key] == value for key, value in query.equal.items())
    clauses.extend(table.c[key].in_(values) for key, values in query.included.items())
    selected = select(SourceRow if query.entity == "source" else table).where(*clauses)
    if query.order:
        selected = selected.order_by(
            *(table.c[key[1:]].desc() if key.startswith("-") else table.c[key] for key in query.order)
        )
    if query.limit is not None:
        selected = selected.limit(query.limit)
    if query.offset is not None:
        selected = selected.offset(query.offset)
    if query.lock is not None:
        selected = selected.with_for_update(read=query.lock == "share")
    return selected
