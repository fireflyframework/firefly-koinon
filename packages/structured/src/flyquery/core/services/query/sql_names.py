# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bind advertised dataset-qualified names to the executor's local table names."""

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError


def _key(table):
    return tuple(value.casefold() for value in (table.catalog, table.db, table.name))


def bind_registered_table_names(sql: str, bundle: dict) -> str:
    aliases = {}
    for hit in bundle.get("schema_inventory") or []:
        metadata = hit.get("metadata", hit) if isinstance(hit, dict) else getattr(hit, "metadata", {})
        if metadata.get("kind") != "TABLE" or not metadata.get("qualified_name"):
            continue
        try:
            table = exp.to_table(metadata["qualified_name"], dialect="duckdb")
        except ParseError:
            continue
        if table.db or table.catalog:
            key = _key(table)
            aliases[key] = table.name if key not in aliases or aliases[key] == table.name else None
    if not aliases:
        return sql
    try:
        statements = sqlglot.parse(sql, read="duckdb")
    except ParseError:
        return sql
    if len(statements) != 1 or statements[0] is None:
        return sql
    tree = statements[0]
    changed = set()
    for table in tree.find_all(exp.Table):
        key = _key(table)
        if aliases.get(key):
            table.set("db", None)
            table.set("catalog", None)
            changed.add(key)
    if not changed:
        return sql
    for column in tree.find_all(exp.Column):
        key = tuple(value.casefold() for value in (column.catalog, column.db, column.table))
        if key in changed:
            column.set("db", None)
            column.set("catalog", None)
    return tree.sql(dialect="duckdb")
