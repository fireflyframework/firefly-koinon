# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import replace
from types import SimpleNamespace

import pytest
from flyquery.core.services.execution.duckdb_executor import ExecutionResult

from koinon.evidence.dtos import SourceReference
from koinon.knowledge.answer_evidence import answer_facts
from koinon.knowledge.capture_dtos import CapturedEvidence
from koinon.knowledge.capture_receipt import NativeEvidenceReceipt


def result_capture(sql, rows, *, output_rows=None, observed=True):
    receipt = NativeEvidenceReceipt("owner", "tenant")
    identifier = receipt.sql_begin("direct", sql)
    receipt.sql_pins(identifier, {"orders": "snapshot"})
    receipt.sql_tables(identifier, [{"table_id": "table", "name": "orders", "snapshot_id": "snapshot"}])
    receipt.sql_engine(identifier, {"engine": "duckdb"}, executed=True)
    receipt.sql_classified(identifier, "SELECT")
    result = ExecutionResult(rows, list(rows[0]) if rows else ["amount"], len(rows), False)
    receipt.sql_executed(identifier, result)
    data = {
        "query_id": "query",
        "execution_status": "OK",
        "sql": sql,
        "preview": output_rows if output_rows is not None else rows,
        "row_count": len(rows),
        "truncated": False,
        "snapshot_pins": {"orders": "snapshot"},
    }
    receipt.query("tenant", "space", "owner", "dataset", data)
    source = SourceReference(
        id="ref",
        asset_id="dataset",
        source_id="source",
        title="Orders",
        kind="dataset",
        snapshot_id="snapshot",
        query_id="query",
        used_revision="snapshot",
    )
    return CapturedEvidence(
        data,
        (source,),
        receipt.complete,
        sql_attempts=receipt.sql_attempts,
        query_results=tuple(receipt.query_results) if observed else (),
    )


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 999 AS invented FROM orders",
        "SELECT amount*1.2 AS adjusted FROM orders",
        "SELECT upper(amount) AS amount FROM orders",
    ],
)
async def test_executed_table_backed_sql_is_not_itself_fact_lineage(sql):
    assert answer_facts(result_capture(sql, [{"invented": 999}]), "result") == ()


async def test_actual_cells_are_eligible_but_tampered_preview_or_missing_executor_proof_is_not():
    capture = result_capture("SELECT amount AS forecast FROM orders", [{"forecast": 12}])
    facts = answer_facts(capture, "result")
    assert len(facts) == 1 and facts[0].value == 12 and facts[0].label == "orders.amount"
    assert facts[0].kind == "cell" and len(facts[0].lineage_sha256) == 64
    assert answer_facts(replace(capture, query_results=()), "result") == ()
    assert (
        answer_facts(
            result_capture("SELECT amount FROM orders", [{"amount": 12}], output_rows=[{"amount": 999}]),
            "result",
        )
        == ()
    )


async def test_executor_value_types_cannot_be_replaced_by_equal_python_values():
    capture = result_capture("SELECT amount FROM orders", [{"amount": 1}], output_rows=[{"amount": True}])
    assert not capture.complete
    assert answer_facts(capture, "result") == ()


async def test_approved_aggregate_is_labeled_as_a_calculation_and_does_not_promote_a_synthetic_sibling():
    capture = result_capture(
        "SELECT SUM(amount) AS claim, 100 AS invented FROM orders", [{"claim": 42, "invented": 100}]
    )
    facts = answer_facts(capture, "result")
    assert [(f.kind, f.label, f.value) for f in facts] == [("derived", "SUM(orders.amount)", 42)]
    assert all(f.source_refs[0].snapshot_id == "snapshot" for f in facts)


async def test_predicates_can_select_actual_rows_but_subquery_or_union_lineage_is_unavailable():
    assert answer_facts(
        result_capture("SELECT amount FROM orders WHERE region='West'", [{"amount": 12}]), "result"
    )
    for sql in (
        "SELECT 7 AS amount UNION SELECT amount FROM orders",
        "WITH t AS (SELECT 7 AS amount FROM orders) SELECT amount FROM t",
    ):
        assert answer_facts(result_capture(sql, [{"amount": 7}]), "result") == ()


async def test_star_cannot_turn_a_synthetic_sibling_or_positional_column_rename_into_lineage():
    for sql in ("SELECT *, 999 AS invented FROM orders", "SELECT * FROM orders AS renamed(invented)"):
        assert answer_facts(result_capture(sql, [{"invented": 999}]), "result") == ()


async def test_unnamed_count_uses_actual_executor_column_identity_and_an_explicit_calculation_label():
    facts = answer_facts(result_capture("SELECT COUNT(*) FROM orders", [{"count_star()": 3}]), "result")
    assert [(f.kind, f.label, f.value) for f in facts] == [("derived", "COUNT(orders.*)", 3)]


@pytest.mark.parametrize(
    "sql,expected",
    [
        ("SELECT amount AS forecast FROM orders", [2, 3]),
        ("SELECT SUM(amount) AS total FROM orders", [5]),
        ("SELECT 999 AS invented FROM orders", []),
        ("SELECT amount*1.2 AS adjusted FROM orders", []),
    ],
)
async def test_real_native_duckdb_results_bind_cells_and_reject_computed_constants(tmp_path, sql, expected):
    import pyarrow as pa
    import pyarrow.parquet as pq
    from flyquery.core.services.execution.duckdb_executor import DuckDBExecutor
    from flyquery.core.services.query.provenance import observe, resolved

    path = tmp_path / "orders.parquet"
    pq.write_table(pa.table({"amount": [2, 3]}), path)
    receipt = NativeEvidenceReceipt("owner", "tenant")
    executor = DuckDBExecutor(
        SimpleNamespace(duckdb_memory_limit="128MB", default_row_cap=10, default_statement_timeout_ms=3000)
    )
    with observe(receipt, tenant_id="tenant", workspace_id="space", dataset_id="dataset", actor="owner"):
        resolved("dataset", [{"table_id": "table", "name": "orders", "snapshot_id": "snapshot"}])
        result = await executor.execute(sql, {"orders": str(path)})
        assert isinstance(result, ExecutionResult)
        data = {
            "query_id": "native-query",
            "execution_status": "OK",
            "sql": sql,
            "preview": result.rows,
            "row_count": result.row_count,
            "truncated": result.truncated,
            "snapshot_pins": {"orders": "snapshot"},
        }
        receipt.query("tenant", "space", "owner", "dataset", data)
    source = SourceReference(
        id="ref",
        asset_id="dataset",
        source_id="source",
        title="Orders",
        kind="dataset",
        snapshot_id="snapshot",
        query_id="native-query",
        used_revision="snapshot",
    )
    capture = CapturedEvidence(
        data,
        (source,),
        receipt.complete,
        sql_attempts=receipt.sql_attempts,
        query_results=tuple(receipt.query_results),
    )
    assert [f.value for f in answer_facts(capture, "result")] == expected
    assert receipt.sql_attempts[0].executed and receipt.sql_attempts[0].outcome == "executed"
    await executor.close()
