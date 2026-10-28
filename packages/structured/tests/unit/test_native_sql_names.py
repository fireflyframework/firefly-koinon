# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace

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
