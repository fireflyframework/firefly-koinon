# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""The native persisted query boundary preserves server-only consumer context."""

import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from flyquery.core.services.query.consumer_context import bind_consumer_context, consumer_context
from flyquery.core.services.query.query_repository import QueryRepository
from pyfly.kernel import ServiceUnavailableException


def test_server_execution_context_is_copied_nested_and_restored():
    original = {"kind": "consumer", "binding": {"generation": "first"}}
    assert consumer_context() is None
    with bind_consumer_context(original):
        original["binding"]["generation"] = "changed"
        assert consumer_context()["binding"]["generation"] == "first"
        with bind_consumer_context({"kind": "other"}):
            assert consumer_context() == {"kind": "other"}
        assert consumer_context()["binding"]["generation"] == "first"
    assert consumer_context() is None


async def test_native_persistence_retains_server_context_and_reads_fail_without_authority(monkeypatch):
    from flyquery.core.services.query import query_repository as module

    identifier, workspace = uuid4(), uuid4()
    context = {"kind": "test_consumer", "binding": {"generation": "fixed"}}
    calls = []

    class Result:
        def mappings(self):
            return self

        def one(self):
            return {"id": identifier}

        def one_or_none(self):
            return {"id": identifier, "consumer_context": context}

    async def execute(statement, parameters):
        calls.append((str(statement), parameters))
        return Result()

    @asynccontextmanager
    async def unit(factory):
        yield SimpleNamespace(execute=execute)

    monkeypatch.setattr(module, "infrastructure_unit", unit)
    repository = object.__new__(QueryRepository)
    repository._factory, repository.consumer_access = object(), None
    with bind_consumer_context(context):
        await repository.create_query(
            tenant_id="north",
            workspace_id=workspace,
            dataset_id=None,
            question="Retained question",
            semantic_path_taken=None,
            candidates_json=[],
            chosen_candidate_index=None,
            executed_sql="SELECT 'remembered'",
            ast_classification="SELECT",
            execution_status="OK",
            retries=0,
            row_count=1,
            elapsed_ms=1,
            clarification_emitted=False,
            clarification_json=None,
            pii_findings_json=None,
            error_json=None,
        )
    assert json.loads(calls[0][1]["consumer_context"]) == context
    assert "consumer_context" in calls[0][0]
    with pytest.raises(ServiceUnavailableException):
        await repository.get_query(identifier, tenant_id="north", workspace_id=workspace)
    access = SimpleNamespace(authorize=AsyncMock())
    repository.consumer_access = SimpleNamespace(get=lambda: access)
    assert (await repository.get_query(identifier, tenant_id="north", workspace_id=workspace))[
        "id"
    ] == identifier
    access.authorize.assert_awaited_once_with((context,), "north", str(workspace))


def test_historical_evidence_hash_material_does_not_backfill_direct_basis():
    from koinon.evidence.dtos import SourceReference
    from koinon.knowledge.curated.dtos import DocumentEvidence

    source = SourceReference(
        id="recorded",
        asset_id="document",
        title="Recorded passage",
        kind="document",
        chunk_id="chunk",
        used_revision="recorded-revision",
    )
    legacy = {"kind": "document_passage", "source": source.model_dump(mode="json")}
    assert DocumentEvidence.model_validate(legacy).model_dump(mode="json") == legacy
    remembered = DocumentEvidence(source=source, basis="remembered_context")
    assert remembered.model_dump(mode="json")["basis"] == "remembered_context"
