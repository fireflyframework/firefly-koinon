# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bind advertised dataset-qualified names to the executor's local table names."""

import sqlglot
from sqlglot import TokenType, exp
from sqlglot.errors import ParseError, TokenError


def _key(table):
    return tuple(value.casefold() for value in (table.catalog, table.db, table.name))


def _quote_registered_identifiers(sql: str, aliases: dict) -> str:
    """Disambiguate keyword components only in admitted qualified identifier tokens."""
    tokens = sqlglot.Dialect.get_or_raise("duckdb").tokenize(sql)
    patterns = sorted(
        (tuple(part for part in key if part) for key, target in aliases.items() if target),
        key=len, reverse=True,
    )
    replacements = []
    index = 0
    while index < len(tokens):
        for parts in patterns:
            width = len(parts) * 2 - 1
            candidate = tokens[index:index + width]
            if len(candidate) != width:
                continue
            if any(candidate[offset].token_type != TokenType.DOT for offset in range(1, width, 2)):
                continue
            identifiers = candidate[::2]
            if any(token.token_type == TokenType.STRING for token in identifiers):
                continue
            if any(
                token.token_type != TokenType.IDENTIFIER
                and sql[token.start:token.end + 1].casefold() != token.text.casefold()
                for token in identifiers
            ):
                continue
            if tuple(token.text.casefold() for token in identifiers) != parts:
                continue
            quoted = ".".join(exp.to_identifier(token.text, quoted=True).sql(dialect="duckdb") for token in identifiers)
            replacements.append((candidate[0].start, candidate[-1].end + 1, quoted))
            index += width
            break
        else:
            index += 1
    for start, end, quoted in reversed(replacements):
        sql = sql[:start] + quoted + sql[end:]
    return sql


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
        try:
            statements = sqlglot.parse(_quote_registered_identifiers(sql, aliases), read="duckdb")
        except (ParseError, TokenError):
            return sql
    except TokenError:
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
