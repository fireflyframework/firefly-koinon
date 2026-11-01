# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Conservative AST lineage for answer facts; it does not change raw SQL execution."""

import json
from hashlib import sha256

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError, TokenError

from koinon.knowledge.answer_evidence import QueryColumnEligibility
from koinon.knowledge.capture_dtos import NativeQueryResult, NativeSqlAttempt


def query_columns(attempt: NativeSqlAttempt, proof: NativeQueryResult) -> tuple[QueryColumnEligibility, ...]:
    if (
        not attempt.executed
        or attempt.outcome != "executed"
        or attempt.classification != "SELECT"
        or not attempt.statement
        or not attempt.snapshot_pins
        or len(attempt.tables) != 1
        or attempt.statement_sha256 != proof.statement_sha256
        or sha256(attempt.statement.encode()).hexdigest() != proof.statement_sha256
        or attempt.snapshot_pins != dict(proof.snapshot_pins)
        or len(proof.columns) != len(set(proof.columns))
    ):
        return ()
    try:
        statements = sqlglot.parse(attempt.statement, read="duckdb")
    except (ParseError, TokenError):
        return ()
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        return ()
    tree = statements[0]
    tables = list(tree.find_all(exp.Table))
    if (
        len(tables) != 1
        or tree.args.get("with_")
        or tree.args.get("joins")
        or any(tree.find_all(exp.Subquery))
        or any(tree.find_all(exp.Window))
        or any(tree.find_all(exp.Pivot))
    ):
        return ()
    native = attempt.tables[0]
    table = tables[0]
    alias = table.args.get("alias")
    if alias is not None and alias.args.get("columns"):
        return ()
    if table.name.casefold() != native.table_name.casefold() or table.db or table.catalog:
        return ()
    if attempt.snapshot_pins != {native.table_name: native.snapshot_id}:
        return ()
    qualifiers = {table.name.casefold(), table.alias_or_name.casefold()}

    def column(node):
        if not isinstance(node, exp.Column) or isinstance(node.this, exp.Star):
            return None
        if node.db or node.catalog or (node.table and node.table.casefold() not in qualifiers):
            return None
        return native.table_name + "." + node.name if node.name else None

    eligible = []
    for index, projection in enumerate(tree.expressions):
        expression = projection.this if isinstance(projection, exp.Alias) else projection
        key = projection.alias_or_name
        if not projection.alias and len(tree.expressions) == len(proof.columns):
            key = proof.columns[index]
        source = column(expression)
        kind = "cell"
        label = source
        if isinstance(expression, (exp.Sum, exp.Avg, exp.Min, exp.Max, exp.Count)):
            source = column(expression.this)
            if isinstance(expression, exp.Count) and isinstance(expression.this, exp.Star):
                source = native.table_name + ".*"
            if source and not expression.args.get("expressions"):
                kind = "derived"
                label = expression.key.upper() + "(" + source + ")"
        if (
            isinstance(expression, exp.Star)
            and not any(expression.args.values())
            and len(tree.expressions) == 1
        ):
            for name in proof.columns:
                eligible.append(
                    (name, native.table_name + "." + name, "cell", (native.table_name + "." + name,))
                )
        elif source and label and key in proof.columns:
            eligible.append((key, label, kind, (source,)))
    if len({entry[0] for entry in eligible}) != len(eligible):
        return ()
    return tuple(
        QueryColumnEligibility(
            key,
            label,
            kind,
            columns,
            sha256(
                json.dumps(
                    [proof.statement_sha256, proof.snapshot_pins, key, label, columns],
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest(),
        )
        for key, label, kind, columns in eligible
    )
