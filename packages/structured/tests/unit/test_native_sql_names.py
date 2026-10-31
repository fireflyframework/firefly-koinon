# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace

import pytest

from flyquery.core.services.execution.ast_classifier import AstClassifier


def inventory():
    return {"schema_inventory": [SimpleNamespace(metadata={"kind": "TABLE", "qualified_name": "owned_dataset.orders"})]}


def test_only_an_actual_registered_qualified_table_is_bound_to_its_local_name():
    from flyquery.core.services.query.sql_names import bind_registered_table_names

    sql = bind_registered_table_names("SELECT SUM(total) FROM owned_dataset.orders", inventory())
    assert AstClassifier().classify(sql).table_refs == ("orders",)


def test_unregistered_schema_with_same_table_name_is_never_stripped():
    from flyquery.core.services.query.sql_names import bind_registered_table_names

    sql = "SELECT SUM(total) FROM foreign_dataset.orders"
    assert bind_registered_table_names(sql, inventory()) == sql


def test_name_binding_never_drops_a_second_statement_or_a_table_function():
    from flyquery.core.services.query.sql_names import bind_registered_table_names

    for sql in ("SELECT * FROM owned_dataset.orders; DELETE FROM elsewhere", "SELECT * FROM read_csv('/etc/passwd')"):
        assert bind_registered_table_names(sql, inventory()) == sql


def test_cte_and_column_qualifiers_keep_the_registered_table_relationship():
    from flyquery.core.services.query.sql_names import bind_registered_table_names

    sql = bind_registered_table_names("WITH x AS (SELECT owned_dataset.orders.total FROM owned_dataset.orders) SELECT SUM(total) FROM x", inventory())
    assert "owned_dataset" not in sql
    assert "orders.total" in sql


@pytest.mark.parametrize("table_name", ["owned_dataset.values", '"owned_dataset".values', "owned_dataset./* table */values"])
def test_registered_reserved_identifier_preserves_column_qualifiers_and_literals(table_name):
    from flyquery.core.services.query.sql_names import bind_registered_table_names

    bundle = {"schema_inventory": [SimpleNamespace(metadata={"kind": "TABLE", "qualified_name": "owned_dataset.values"})]}
    sql = bind_registered_table_names(
        f"SELECT {table_name}.total, 'owned_dataset.values' AS label FROM {table_name}", bundle,
    )
    classification = AstClassifier().classify(sql)
    assert classification.classification == "SELECT"
    assert classification.single_statement and not classification.unsupported_sql
    assert classification.table_refs == ("values",)
    assert "'owned_dataset.values'" in sql


@pytest.mark.parametrize("sql", [
    "SELECT * FROM foreign_dataset.values",
    "SELECT * FROM foreign_dataset.owned_dataset.values",
    "SELECT * FROM owned_dataset.values; DELETE FROM elsewhere",
    "SELECT * FROM owned_dataset.values CROSS JOIN read_parquet('/etc/private.parquet')",
    "SELECT * FROM owned_dataset.values CROSS JOIN arbitrary_function()",
    "DELETE FROM owned_dataset.values",
])
def test_reserved_identifier_repair_preserves_source_function_statement_and_write_guards(sql):
    from flyquery.core.services.execution.scope_guard import ScopeGuard, ScopeGuardError
    from flyquery.core.services.query.sql_names import bind_registered_table_names

    bundle = {"schema_inventory": [SimpleNamespace(metadata={"kind": "TABLE", "qualified_name": "owned_dataset.values"})]}
    bound = bind_registered_table_names(sql, bundle)
    with pytest.raises(ScopeGuardError):
        ScopeGuard().check(
            classification=AstClassifier().classify(bound), scopes={"flyquery.sql:execute"},
            table_kinds_by_name={"values": "UPLOADED"}, dataset_allowlist={"dataset-owned"},
            dataset_of_table={"values": "dataset-owned"},
        )


def test_unterminated_sql_is_left_for_the_classifier_to_reject():
    from flyquery.core.services.query.sql_names import bind_registered_table_names

    source = "SELECT 'owned_dataset.orders FROM owned_dataset.orders"
    assert bind_registered_table_names(source, inventory()) == source


async def test_reserved_identifier_executes_with_captured_snapshot_and_actual_parquet(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    from flyquery.core.services.execution.duckdb_executor import DuckDBExecutor, ExecutionResult
    from flyquery.core.services.execution.scope_guard import ScopeGuard
    from flyquery.core.services.query.query_service import QueryService
    from flyquery.core.services.query.sql_names import bind_registered_table_names

    path = tmp_path / "values.parquet"
    pq.write_table(pa.table({"total": [11, 17]}), path)
    pin = "00000000-0000-0000-0000-000000000071"

    class Resolver:
        async def current_snapshots(self, dataset_id, names):
            assert dataset_id == "dataset-owned" and names == ["values"]
            return {"values": pin}

        async def resolve(self, dataset_id, names, *, pins):
            assert dataset_id == "dataset-owned" and names == ["values"]
            assert pins == {"values": pin}
            return {"values": str(path)}

    settings = SimpleNamespace(synthesis_function_firewall=True, duckdb_memory_limit="256MB", default_row_cap=10, default_statement_timeout_ms=5000)
    service = object.__new__(QueryService)
    service._settings = settings
    service._ast_classifier = AstClassifier()
    service._scope_guard = ScopeGuard()
    service._table_resolver = Resolver()
    service._executor = DuckDBExecutor(settings)

    async def kinds(names, dataset_id):
        assert names == ["values"] and dataset_id == "dataset-owned"
        return {"values": "UPLOADED"}

    async def datasets(names, dataset_id):
        assert names == ["values"] and dataset_id == "dataset-owned"
        return {"values": "dataset-owned"}

    service._table_kinds_by_name = kinds
    service._dataset_of_tables = datasets
    bundle = {"schema_inventory": [SimpleNamespace(metadata={"kind": "TABLE", "qualified_name": "owned_dataset.values"})]}
    sql = bind_registered_table_names("SELECT SUM(total) AS total_sum FROM owned_dataset.values", bundle)
    run = await service._run_sql_once(sql, "dataset-owned", {"flyquery.sql:execute"}, {"dataset-owned"}, bundle)
    assert run["status"] == "ok"
    assert isinstance(run["result"], ExecutionResult)
    assert run["result"].rows == [{"total_sum": 28}]
    assert bundle["snapshot_pins"] == {"values": pin}
