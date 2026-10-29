# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Exercise production eligibility predicates against controlled persisted examples."""

import sqlite3
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
import sqlglot
from sqlalchemy import text
from sqlglot import exp

from flyquery.core.services.retrieval.search_index import SearchIndex
from flyquery.models.repositories.embedding_set_repository import OBJECTS_SQL
from flyquery.web.conventions.context import TenantContext, set_tenant_context


class Record(dict):
    def __getattr__(self, key):
        return self[key]


class Rows(list):
    def all(self):
        return self


class Result:
    def __init__(self, rows):
        self.rows = Rows(rows)

    def mappings(self):
        return self.rows


class ExampleProtocol:
    """Evaluate actual SQL eligibility; omit only unsupported vector scoring and schema CTEs."""

    def __init__(self, workspace, dataset):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.execute(
            "CREATE TABLE flyquery_examples(id TEXT,tenant_id TEXT,workspace_id TEXT,dataset_id TEXT,quality TEXT,question TEXT,generated_sql TEXT)"
        )
        self.db.executemany(
            "INSERT INTO flyquery_examples VALUES(?,?,?,?,?,?,?)",
            [
                (quality.lower(), "tenant", str(workspace), str(dataset), quality, "question", "SELECT 1")
                for quality in ("APPROVED", "PROPOSED", "REJECTED")
            ],
        )

    async def execute(self, statement, parameters=None):
        sql = str(statement)
        if sql.startswith("SET LOCAL"):
            return Result([])
        parsed = sqlglot.parse_one(sql, read="postgres")
        parameters = {
            key: str(value) if isinstance(value, UUID) else value for key, value in (parameters or {}).items()
        }
        candidates = None
        for select in parsed.find_all(exp.Select):
            source = select.args.get("from_")
            if (
                source is None
                or not isinstance(source.this, exp.Table)
                or source.this.name != "flyquery_examples"
            ):
                continue
            where = select.args.get("where")
            alias = source.this.alias
            query = "SELECT id,question,generated_sql FROM flyquery_examples" + (" " + alias if alias else "")
            if where is not None:
                query += " " + where.sql(dialect="sqlite")
            eligible = {row["id"]: Record(dict(row), score=0.9) for row in self.db.execute(query, parameters)}
            candidates = (
                eligible
                if candidates is None
                else {key: row for key, row in candidates.items() if key in eligible}
            )
        assert candidates is not None, "Production query did not select example eligibility"
        return Result(list(candidates.values()))


@pytest.mark.parametrize("mode", ["lexical", "inline", "versioned"])
async def test_proposed_examples_are_not_grounding_knowledge_until_explicit_approval(monkeypatch, mode):
    workspace, dataset = uuid4(), uuid4()
    protocol = ExampleProtocol(workspace, dataset)
    binding = (
        SimpleNamespace(versioned=True, storage_dimensions=3, space_id="active")
        if mode == "versioned"
        else None
    )
    monkeypatch.setattr("flyquery.core.agents.model_bindings.embedding_for", lambda role: binding)
    token = set_tenant_context(
        TenantContext(tenant_id="tenant", workspace_id=str(workspace), actor="reader", correlation_id="test")
    )
    try:
        index = SearchIndex(protocol)
        vector = None if mode == "lexical" else [0.1, 0.2, 0.3]
        hits = await index.approved_examples("question", vector, workspace, dataset)
        assert [hit.id for hit in hits] == ["approved"]
        protocol.db.execute("UPDATE flyquery_examples SET quality='APPROVED' WHERE id='proposed'")
        hits = await index.approved_examples("question", vector, workspace, dataset)
        assert {hit.id for hit in hits} == {"approved", "proposed"}
    finally:
        token.var.reset(token.token)
        protocol.db.close()


async def test_versioned_index_does_not_admit_unapproved_drafts():
    workspace, dataset = uuid4(), uuid4()
    protocol = ExampleProtocol(workspace, dataset)
    try:
        result = await protocol.execute(
            text(OBJECTS_SQL + " SELECT * FROM objects"), {"tenant": "tenant", "workspace": workspace}
        )
        assert [row["id"] for row in result.mappings()] == ["approved"]
    finally:
        protocol.db.close()
