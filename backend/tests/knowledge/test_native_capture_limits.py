# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import ServiceUnavailableException

from koinon.knowledge.capture_receipt import NativeEvidenceReceipt


async def test_zero_capture_allowance_blocks_domain_before_model_or_sql():
    from koinon.knowledge.capture_dtos import NativeCaptureLimits
    from koinon.knowledge.evidence_capture import NativeEvidenceFailure, NativeKnowledgeEvidence

    asset = SimpleNamespace(id="dataset", kind="dataset", name="Owned", workspace_id="canonical")
    knowledge = SimpleNamespace(
        _chain=AsyncMock(return_value=[asset, SimpleNamespace(id="source")]),
        binding=AsyncMock(
            return_value=SimpleNamespace(native_id="native", native_workspace_id="native-space")
        ),
        query=AsyncMock(),
    )
    with pytest.raises(NativeEvidenceFailure) as failure:
        await NativeKnowledgeEvidence(knowledge, SimpleNamespace()).query(
            "owner",
            "tenant",
            dataset_id="dataset",
            question="Count",
            _limits=NativeCaptureLimits(reads=0, attempts=0, sources=0, receipt_bytes=0),
        )
    assert failure.value.code == "EVIDENCE_BUDGET_EXCEEDED"
    assert not failure.value.capture.complete and failure.value.capture.data == {}
    assert failure.value.capture.native_reads == () and failure.value.capture.sql_attempts == ()
    knowledge.query.assert_not_awaited()


async def test_zero_attempt_allowance_prevents_actual_duckdb_entry(monkeypatch):
    import duckdb
    from flyquery.core.services.execution.duckdb_executor import DuckDBExecutor
    from flyquery.core.services.query.provenance import observe

    from koinon.knowledge.capture_dtos import NativeCaptureLimits

    monkeypatch.setattr(duckdb, "connect", lambda *a, **kw: pytest.fail("Engine must not open"))
    receipt = NativeEvidenceReceipt("owner", "tenant", limits=NativeCaptureLimits(attempts=0))
    settings = SimpleNamespace(
        duckdb_memory_limit="128MB", default_row_cap=10, default_statement_timeout_ms=1000
    )
    with (
        observe(receipt, tenant_id="tenant", workspace_id="workspace", dataset_id="dataset", actor="owner"),
        pytest.raises(ServiceUnavailableException) as failure,
    ):
        await DuckDBExecutor(settings).execute("SELECT 1", {})
    assert failure.value.code == "EVIDENCE_BUDGET_EXCEEDED" and receipt.sql_attempts == ()


async def test_read_and_id_allowances_are_reserved_before_model_input_without_truncation():
    from flyquery.core.services.query.provenance import before_model, observe
    from flyquery.core.services.retrieval.search_index import Hit

    from koinon.knowledge.capture_dtos import NativeCaptureLimits

    hits = [
        Hit(
            "schema_object",
            f"column-{i}",
            "Exact schema",
            1.0,
            {"table_id": "table", "snapshot_id": "snapshot"},
        )
        for i in range(5)
    ]
    receipt = NativeEvidenceReceipt("owner", "tenant", limits=NativeCaptureLimits(reads=2, ids_per_read=2))
    receipt.verify_structured = AsyncMock(return_value=True)
    receipt.authorize_model = AsyncMock()
    with (
        observe(receipt, tenant_id="tenant", workspace_id="workspace", dataset_id="dataset", actor="owner"),
        pytest.raises(ServiceUnavailableException) as failure,
    ):
        await before_model(
            "grounding",
            "Actual prompt",
            {"schema_objects": hits},
            tenant_id="tenant",
            workspace_id="workspace",
            dataset_id="dataset",
        )
    assert failure.value.code == "EVIDENCE_BUDGET_EXCEEDED" and receipt.native_reads == []
    receipt = NativeEvidenceReceipt("owner", "tenant", limits=NativeCaptureLimits(reads=3, ids_per_read=2))
    receipt.verify_structured = AsyncMock(return_value=True)
    receipt.authorize_model = AsyncMock()
    with observe(receipt, tenant_id="tenant", workspace_id="workspace", dataset_id="dataset", actor="owner"):
        await before_model(
            "grounding",
            "Actual prompt",
            {"schema_objects": hits},
            tenant_id="tenant",
            workspace_id="workspace",
            dataset_id="dataset",
        )
    assert len(receipt.native_reads) == 3
    assert {identifier for row in receipt.native_reads for identifier in row.source_ids} == {
        f"column-{i}" for i in range(5)
    }


async def test_source_and_byte_budget_exhaustion_retains_only_previously_admitted_observations():
    from koinon.knowledge.capture_dtos import NativeCaptureLimits

    receipt = NativeEvidenceReceipt("owner", "tenant", limits=NativeCaptureLimits(sources=1))
    receipt.search(
        "tenant", "workspace", "owner", [{"chunk_id": "first", "source_id": "source", "content": "First"}]
    )
    with pytest.raises(ServiceUnavailableException) as failure:
        receipt.search(
            "tenant",
            "workspace",
            "owner",
            [{"chunk_id": "second", "source_id": "source", "content": "Second"}],
        )
    assert failure.value.code == "EVIDENCE_BUDGET_EXCEEDED" and set(receipt.documents) == {"first"}
    receipt = NativeEvidenceReceipt("owner", "tenant", limits=NativeCaptureLimits(receipt_bytes=1000))
    with pytest.raises(ServiceUnavailableException) as failure:
        receipt.search(
            "tenant",
            "workspace",
            "owner",
            [{"chunk_id": "large", "source_id": "source", "content": "x" * 8000}],
        )
    assert failure.value.code == "EVIDENCE_BUDGET_EXCEEDED" and receipt.documents == {}


async def test_exhausted_attempt_budget_blocks_critic_before_model_and_preserves_actual_failure(tmp_path):
    from uuid import uuid4

    import pyarrow as pa
    import pyarrow.parquet as pq
    from flyquery.core.services.execution.duckdb_executor import DuckDBExecutor
    from flyquery.core.services.execution.table_resolver import TableResolver
    from flyquery.core.services.query.provenance import observe
    from flyquery.core.services.retrieval.search_index import Hit
    from test_native_provenance import pipeline_fixture

    from koinon.knowledge.capture_dtos import NativeCaptureLimits

    fixture = pipeline_fixture()
    workspace, dataset, table, snapshot, column = [str(uuid4()) for _ in range(5)]
    pq.write_table(pa.table({"total": [5, 7]}), tmp_path / "orders.parquet")
    settings = SimpleNamespace(
        duckdb_memory_limit="128MB",
        default_row_cap=10,
        default_statement_timeout_ms=1000,
        object_store_base=str(tmp_path),
    )

    class Rows:
        def mappings(self):
            return iter(
                [
                    {
                        "name": "orders",
                        "parquet_object_key": "orders.parquet",
                        "snapshot_id": snapshot,
                        "table_id": table,
                    }
                ]
            )

    resolver = TableResolver(SimpleNamespace(execute=AsyncMock(return_value=Rows())), settings)
    resolver.current_snapshots = AsyncMock(return_value={"orders": snapshot})
    service = fixture._make_service(
        executor=DuckDBExecutor(settings),
        table_resolver=resolver,
        candidates=fixture._make_candidates("SELECT missing FROM orders"),
    )
    hit = Hit(
        "schema_object",
        column,
        "Orders total",
        1.0,
        {"table_id": table, "snapshot_id": snapshot, "kind": "COLUMN"},
    )
    service._retriever.retrieve = AsyncMock(return_value={"schema_objects": [hit], "schema_inventory": [hit]})
    service._table_kinds_by_name = AsyncMock(return_value={"orders": "UPLOADED"})
    service._dataset_of_tables = AsyncMock(return_value={"orders": dataset})
    service._critic_agent.run = AsyncMock()
    receipt = NativeEvidenceReceipt("owner", "tenant", limits=NativeCaptureLimits(attempts=1))
    receipt.verify_structured = AsyncMock(return_value=True)
    receipt.authorize_model = AsyncMock()
    with (
        observe(receipt, tenant_id="tenant", workspace_id=workspace, dataset_id=dataset, actor="owner"),
        pytest.raises(ServiceUnavailableException) as failure,
    ):
        await service.answer(
            tenant_id="tenant",
            workspace_id=workspace,
            dataset_id=dataset,
            question="Count",
            scopes={"flyquery.sql:execute"},
        )
    assert failure.value.code == "EVIDENCE_BUDGET_EXCEEDED"
    service._critic_agent.run.assert_not_awaited()
    assert len(receipt.sql_attempts) == 1 and receipt.sql_attempts[0].executed
    assert receipt.sql_attempts[0].outcome == "failed"
    assert [row.stage for row in receipt.native_reads] == ["rerank", "grounding", "generation"]


async def test_actual_final_envelope_overflow_is_typed_partial_without_raw_result_data():
    from hashlib import sha256

    from koinon.knowledge.capture_dtos import NativeCaptureLimits
    from koinon.knowledge.evidence_capture import NativeEvidenceFailure, NativeKnowledgeEvidence

    asset = SimpleNamespace(id="asset", kind="document", name="Owned", workspace_id="canonical")
    source = SimpleNamespace(id="source")
    text = "x" * 600000

    async def search(subject, tenant, **kwargs):
        receipt = kwargs["_capture"]
        receipt.admit_documents(tenant, "native-space", subject, {"native-source": (asset, source)})
        receipt.search(
            tenant,
            "native-space",
            subject,
            [{"chunk_id": "chunk", "source_id": "native-source", "content": text}],
        )
        return {
            "hits": [
                {"id": "chunk", "asset_id": "asset", "source_id": "source", "title": "Owned", "text": text}
            ]
        }

    knowledge = SimpleNamespace(
        search=search,
        _chain=AsyncMock(return_value=[asset, source]),
        binding=AsyncMock(
            return_value=SimpleNamespace(native_id="native-source", native_workspace_id="native-space")
        ),
    )
    with pytest.raises(NativeEvidenceFailure) as caught:
        await NativeKnowledgeEvidence(knowledge, SimpleNamespace()).search(
            "owner", "tenant", question="Read", _limits=NativeCaptureLimits()
        )
    failure = caught.value
    assert failure.code == "EVIDENCE_BUDGET_EXCEEDED" and not failure.capture.complete
    assert failure.capture.data == {} and len(failure.capture.sources) == 1
    assert failure.capture.sources[0].used_revision == "chunk-sha256:" + sha256(text.encode()).hexdigest()
    assert len(failure.capture.sources[0].quote) == 8000


async def test_observed_result_overflow_stops_before_native_explainer(tmp_path):
    from uuid import uuid4

    import pyarrow as pa
    import pyarrow.parquet as pq
    from flyquery.core.services.execution.duckdb_executor import DuckDBExecutor
    from flyquery.core.services.execution.table_resolver import TableResolver
    from flyquery.core.services.query.provenance import observe
    from flyquery.core.services.retrieval.search_index import Hit
    from test_native_provenance import pipeline_fixture

    from koinon.knowledge.capture_dtos import NativeCaptureLimits

    fixture = pipeline_fixture()
    workspace, dataset, table, snapshot, column = [str(uuid4()) for _ in range(5)]
    pq.write_table(pa.table({"total": ["x" * 30000]}), tmp_path / "orders.parquet")
    settings = SimpleNamespace(
        duckdb_memory_limit="128MB",
        default_row_cap=10,
        default_statement_timeout_ms=1000,
        object_store_base=str(tmp_path),
    )

    class Rows:
        def mappings(self):
            return iter(
                [
                    {
                        "name": "orders",
                        "parquet_object_key": "orders.parquet",
                        "snapshot_id": snapshot,
                        "table_id": table,
                    }
                ]
            )

    resolver = TableResolver(SimpleNamespace(execute=AsyncMock(return_value=Rows())), settings)
    resolver.current_snapshots = AsyncMock(return_value={"orders": snapshot})
    service = fixture._make_service(
        executor=DuckDBExecutor(settings),
        table_resolver=resolver,
        candidates=fixture._make_candidates("SELECT total FROM orders"),
    )
    hit = Hit(
        "schema_object",
        column,
        "Orders total",
        1.0,
        {"table_id": table, "snapshot_id": snapshot, "kind": "COLUMN"},
    )
    service._retriever.retrieve = AsyncMock(return_value={"schema_objects": [hit], "schema_inventory": [hit]})
    service._table_kinds_by_name = AsyncMock(return_value={"orders": "UPLOADED"})
    service._dataset_of_tables = AsyncMock(return_value={"orders": dataset})
    service._explainer_agent.run = AsyncMock()
    receipt = NativeEvidenceReceipt("owner", "tenant", limits=NativeCaptureLimits(receipt_bytes=20000))
    receipt.verify_structured = AsyncMock(return_value=True)
    receipt.authorize_model = AsyncMock()
    with (
        observe(receipt, tenant_id="tenant", workspace_id=workspace, dataset_id=dataset, actor="owner"),
        pytest.raises(ServiceUnavailableException) as failure,
    ):
        await service.answer(
            tenant_id="tenant",
            workspace_id=workspace,
            dataset_id=dataset,
            question="Read total",
            scopes={"flyquery.sql:execute"},
        )
    assert failure.value.code == "EVIDENCE_BUDGET_EXCEEDED"
    service._explainer_agent.run.assert_not_awaited()
    assert receipt.sql_attempts[0].executed and receipt.sql_attempts[0].outcome == "executed"
    assert receipt.sql_attempts[0].row_count == 1


async def test_explicit_allowance_retains_every_accepted_failure_read_above_old_default():
    from koinon.knowledge.capture_dtos import NativeCaptureLimits, NativeReadFingerprint
    from koinon.knowledge.evidence_capture import failed_receipt

    receipt = NativeEvidenceReceipt("owner", "tenant", limits=NativeCaptureLimits(reads=1000))
    receipt.document_origins[("native-space", "native-source")] = ("asset", "space", "source", "Owned")
    receipt.native_reads = [
        NativeReadFingerprint(
            "rag", "canon", "tenant", "native-space", "native-source", "a" * 64, ("native-source",), ()
        )
        for _ in range(600)
    ]
    failure = failed_receipt(ServiceUnavailableException("Stopped"), receipt, "tenant")
    assert len(failure.capture.native_reads) == 600
    assert all(
        row.entity_id == "asset" and row.workspace_id == "space" for row in failure.capture.native_reads
    )
