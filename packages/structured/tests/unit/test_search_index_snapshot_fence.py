# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Execute schema admission SQL against mixed snapshot rows in a private in-memory database."""

import json
from types import SimpleNamespace
from uuid import uuid4

import duckdb
import pytest
from sqlalchemy.dialects.postgresql import dialect

from flyquery.core.services.retrieval.search_index import SearchIndex
from flyquery.models.repositories.embedding_set_repository import OBJECTS_SQL
from flyquery.web.conventions.context import TenantContext, set_tenant_context


class Rows(list):
    def all(self):
        return self


class Session:
    def __init__(self, connection):
        self.connection = connection

    async def execute(self, statement, parameters=None):
        if str(statement).startswith("SET LOCAL hnsw."):
            return None
        compiled = statement.compile(dialect=dialect(paramstyle="numeric_dollar"))
        cursor = self.connection.execute(str(compiled), [parameters[key] for key in compiled.positiontup])
        names = [column[0] for column in cursor.description]
        rows = Rows(dict(zip(names, row, strict=True)) for row in cursor.fetchall())
        for row in rows:
            for key in ("profile_json", "sample_values_json", "governance_json"):
                if isinstance(row.get(key), str):
                    row[key] = json.loads(row[key])
        return SimpleNamespace(mappings=lambda: rows)


@pytest.fixture
def inventory_database():
    connection = duckdb.connect()
    dataset, workspace, space = uuid4(), uuid4(), uuid4()
    context = set_tenant_context(
        TenantContext(tenant_id="tenant", workspace_id=str(workspace), actor="actor", correlation_id="test")
    )
    try:
        connection.execute("CREATE TYPE vector AS FLOAT[3]")
        connection.execute("CREATE MACRO plainto_tsquery(language, query) AS query")
        connection.execute("CREATE MACRO ts_rank(content, query) AS 1.0")
        connection.execute("CREATE MACRO convert_to(value, encoding) AS value")
        connection.execute("CREATE MACRO encode(value, encoding) AS value")
        connection.create_function("@@", lambda content, query: True, ["VARCHAR", "VARCHAR"], "BOOLEAN")
        connection.create_function("jsonb_build_object", lambda *args: json.dumps(dict(zip(args[::2], args[1::2], strict=True)), default=str), return_type="VARCHAR", null_handling="special")
        connection.create_function("jsonb_build_array", lambda *args: json.dumps(args, default=str), return_type="VARCHAR", null_handling="special")
        connection.execute("""CREATE TABLE flyquery_tables (
            id UUID, dataset_id UUID, tenant_id VARCHAR, workspace_id UUID,
            current_snapshot_id UUID, is_active BOOLEAN)""")
        connection.execute("""CREATE TABLE flyquery_schema_objects (
            id UUID, table_id UUID, snapshot_id UUID, tenant_id VARCHAR, workspace_id UUID,
            kind VARCHAR, qualified_name VARCHAR, description VARCHAR, data_type VARCHAR,
            is_active BOOLEAN, profile_json VARCHAR, sample_values_json VARCHAR,
            governance_json VARCHAR, synonyms_json VARCHAR, content_tsv VARCHAR, embedding vector)""")
        connection.execute("""CREATE TABLE flyquery_examples (
            id UUID, tenant_id VARCHAR, workspace_id UUID, question VARCHAR, generated_sql VARCHAR, quality VARCHAR)""")
        connection.execute("""CREATE TABLE flyquery_embedding_vectors (
            set_id UUID, kind VARCHAR, object_id UUID, content_hash VARCHAR,
            tenant_id VARCHAR, workspace_id UUID, embedding vector)""")

        def objects(table, snapshot, name, *, active=True):
            for kind, suffix in (("TABLE", ""), ("COLUMN", ".total")):
                connection.execute(
                    "INSERT INTO flyquery_schema_objects VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [uuid4(), table, snapshot, "tenant", workspace, kind, name + suffix, "Total", "INTEGER",
                     active, "{}", "[11]", "{}", "[]", "total", [0.1, 0.2, 0.3]],
                )

        current_table, current, stale = uuid4(), uuid4(), uuid4()
        connection.execute("INSERT INTO flyquery_tables VALUES (?,?,?,?,?,?)", [current_table, dataset, "tenant", workspace, current, True])
        objects(current_table, current, "owned.current")
        objects(current_table, stale, "a_retired.previous")
        objects(current_table, current, "a_hidden.object", active=False)
        for table_dataset, active, snapshot_pointer, name in (
            (dataset, False, uuid4(), "a_inactive.table"),
            (uuid4(), True, uuid4(), "a_foreign.table"),
            (dataset, True, None, "a_unpublished.table"),
        ):
            table = uuid4()
            connection.execute("INSERT INTO flyquery_tables VALUES (?,?,?,?,?,?)", [table, table_dataset, "tenant", workspace, snapshot_pointer, active])
            objects(table, snapshot_pointer or uuid4(), name)
        session = Session(connection)

        async def populate_vectors():
            from sqlalchemy import text

            await session.execute(
                text(OBJECTS_SQL + """INSERT INTO flyquery_embedding_vectors
                    SELECT :space,kind,id,source_hash,:tenant,:workspace,[0.1,0.2,0.3]::vector FROM objects"""),
                {"space": space, "tenant": "tenant", "workspace": workspace},
            )

        yield SearchIndex(session), dataset, SimpleNamespace(storage_dimensions=3, space_id=space, versioned=True), populate_vectors
    finally:
        context.var.reset(context.token)
        connection.close()


@pytest.mark.parametrize("path", ["inventory", "values", "bm25", "inline_vector", "versioned_vector"])
async def test_schema_reads_admit_only_current_objects_of_active_dataset_tables(inventory_database, monkeypatch, path):
    index, dataset, binding, populate_vectors = inventory_database
    if path == "inventory":
        rows = await index.all_schema_objects(dataset)
    elif path == "values":
        rows = await index.column_value_catalog(dataset)
        assert [row["qualified_name"] for row in rows] == ["owned.current.total"]
        assert rows[0]["values"] == ["11"]
        return
    elif path == "bm25":
        rows = await index.bm25_schema_objects("total", dataset)
    else:
        monkeypatch.setattr("flyquery.core.agents.model_bindings.embedding_for", lambda _: binding if path == "versioned_vector" else None)
        if path == "versioned_vector":
            await populate_vectors()
        rows = await index.vector_schema_objects([0.1, 0.2, 0.3], dataset)
    assert sorted(row.metadata["qualified_name"] for row in rows) == ["owned.current", "owned.current.total"]
    if path == "inventory":
        table = next(row for row in rows if row.metadata["kind"] == "TABLE")
        assert table.metadata["columns"] == ["total"]
