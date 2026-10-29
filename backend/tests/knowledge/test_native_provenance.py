# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pyfly.kernel import ServiceUnavailableException

from koinon.knowledge.capture_receipt import NativeEvidenceReceipt


def pipeline_fixture():
    path = Path(__file__).resolve().parents[3] / "packages/structured/tests/unit/test_query_service.py"
    spec = spec_from_file_location("_native_query_fixture", path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def test_product_pipeline_records_native_context_before_each_model_and_rejects_unpinned_schema(
    tmp_path,
):
    from flyquery.core.services.query.provenance import observe
    from flyquery.core.services.retrieval.search_index import Hit

    fixture = pipeline_fixture()
    workspace, dataset, table, snapshot, column = [str(uuid4()) for _ in range(5)]
    receipt = NativeEvidenceReceipt("owner", "tenant")
    receipt.authorize_model = AsyncMock(return_value=True)
    receipt.verify_structured = AsyncMock(return_value=True)
    hit = Hit(
        "schema_object",
        column,
        "orders.total: INTEGER",
        1.0,
        {"table_id": table, "snapshot_id": snapshot, "kind": "COLUMN", "qualified_name": "orders.total"},
    )
    import pyarrow as pa
    import pyarrow.parquet as pq
    from flyquery.core.agents.critic_agent import RefinedSql
    from flyquery.core.services.execution.duckdb_executor import DuckDBExecutor
    from flyquery.core.services.execution.table_resolver import TableResolver

    pq.write_table(pa.table({"total": [5, 7]}), tmp_path / "orders.parquet")
    settings = SimpleNamespace(
        duckdb_memory_limit="128MB",
        default_row_cap=10,
        default_statement_timeout_ms=3000,
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
        critic_agent=fixture._FakeAgent(
            RefinedSql(sql="SELECT sum(total) AS val FROM orders", reasoning="Repair", confidence=1.0)
        ),
    )
    service._table_kinds_by_name = AsyncMock(return_value={"orders": "UPLOADED"})
    service._dataset_of_tables = AsyncMock(return_value={"orders": dataset})
    service._retriever.retrieve = AsyncMock(return_value={"schema_objects": [hit], "schema_inventory": [hit]})
    original = service._grounding_agent.run

    async def grounded(prompt):
        assert receipt.native_reads[-1].stage == "grounding"
        assert receipt.native_reads[-1].content_sha256 == sha256(prompt.encode()).hexdigest()
        assert receipt.native_reads[-1].snapshot_ids == (snapshot,)
        return await original(prompt)

    service._grounding_agent.run = grounded
    with observe(receipt, tenant_id="tenant", workspace_id=workspace, dataset_id=dataset, actor="owner"):
        await service.answer(
            tenant_id="tenant",
            workspace_id=workspace,
            dataset_id=dataset,
            question="Count",
            scopes={"flyquery.query:read", "flyquery.sql:execute"},
        )
    assert [read.stage for read in receipt.native_reads] == [
        "rerank",
        "grounding",
        "generation",
        "critic",
        "explainer",
    ]
    receipt.verify_structured.assert_awaited()

    receipt = NativeEvidenceReceipt("owner", "tenant")
    receipt.authorize_model = AsyncMock(return_value=True)
    receipt.verify_structured = AsyncMock(return_value=True)
    hit.metadata.pop("snapshot_id")
    service._grounding_agent.run = AsyncMock()
    with (
        observe(receipt, tenant_id="tenant", workspace_id=workspace, dataset_id=dataset, actor="owner"),
        pytest.raises(ServiceUnavailableException, match="provenance"),
    ):
        await service.answer(
            tenant_id="tenant",
            workspace_id=workspace,
            dataset_id=dataset,
            question="Count",
            scopes={"flyquery.query:read", "flyquery.sql:execute"},
        )
    service._grounding_agent.run.assert_not_awaited()


async def test_sql_receipt_observes_real_execution_failure_repair_and_validation_order(
    tmp_path,
):
    import pyarrow as pa
    import pyarrow.parquet as pq
    from flyquery.core.services.execution.duckdb_executor import DuckDBExecutor
    from flyquery.core.services.execution.table_resolver import TableResolver
    from flyquery.core.services.query.provenance import observe

    fixture = pipeline_fixture()
    dataset, workspace, snapshot = [str(uuid4()) for _ in range(3)]
    pq.write_table(pa.table({"n": [5, 7]}), tmp_path / "table.parquet")
    receipt = NativeEvidenceReceipt("owner", "tenant")
    settings = SimpleNamespace(
        duckdb_memory_limit="128MB",
        default_row_cap=10,
        default_statement_timeout_ms=3000,
        object_store_base=str(tmp_path),
    )

    class Rows:
        def mappings(self):
            return iter(
                [
                    {
                        "name": "t",
                        "parquet_object_key": "table.parquet",
                        "snapshot_id": snapshot,
                        "table_id": str(uuid4()),
                    }
                ]
            )

    resolver = TableResolver(SimpleNamespace(execute=AsyncMock(return_value=Rows())), settings)
    service = fixture._make_service(executor=DuckDBExecutor(settings), table_resolver=resolver)
    service._table_kinds_by_name = AsyncMock(return_value={"t": "UPLOADED"})
    service._dataset_of_tables = AsyncMock(return_value={"t": dataset})
    service._settings.synthesis_function_firewall = True
    bundle = {"snapshot_pins": {"t": snapshot}}
    with observe(receipt, tenant_id="tenant", workspace_id=workspace, dataset_id=dataset, actor="owner"):
        await service._run_sql_once("SELECT missing FROM t", dataset, {"flyquery.sql:execute"}, None, bundle)
        await service._run_sql_once(
            "SELECT sum(n) AS n FROM t",
            dataset,
            {"flyquery.sql:execute"},
            None,
            bundle,
            _evidence_stage="critic",
        )
        await service._run_sql_once(
            "SELECT * FROM read_csv_auto('/private/path')", dataset, {"flyquery.sql:execute"}, None, bundle
        )
    attempts = receipt.sql_attempts
    assert [(a.ordinal, a.stage, a.outcome, a.executed) for a in attempts] == [
        (1, "candidate", "failed", True),
        (2, "critic", "executed", True),
        (3, "candidate", "blocked", False),
    ]
    assert attempts[0].snapshot_pins == attempts[1].snapshot_pins == {"t": snapshot}
    assert attempts[1].row_count == 1 and attempts[1].truncated is False
    assert attempts[2].reason_code == "SQL_FUNCTION_FIREWALL"
    assert attempts[0].statement == "SELECT missing FROM t"
    assert attempts[1].statement == "SELECT sum(n) AS n FROM t"
    assert attempts[2].statement_sha256 == sha256(attempts[2].statement.encode()).hexdigest()
    assert attempts[1].engine == "duckdb" and attempts[1].database == "memory"
    assert attempts[1].catalog == "memory" and attempts[1].schema == "main"
    assert attempts[1].execution_kind == "imported_snapshot"
    assert attempts[1].native_dataset_id == dataset
    assert attempts[1].tables[0].snapshot_id == snapshot and attempts[1].tables[0].table_name == "t"
    assert attempts[2].engine is None and attempts[2].execution_kind is None


async def test_document_premodel_attests_exact_chunk_and_rejects_missing_identity_before_model():
    from flycanon.core.services.query.provenance import before_model, observe

    receipt = NativeEvidenceReceipt("owner", "tenant")
    receipt.authorize_model = AsyncMock(return_value=True)
    hit = SimpleNamespace(chunk_id="chunk", source_id="source", content="Exact text 😀", metadata={"page": 2})
    with observe(receipt, tenant_id="tenant", workspace_id="workspace", dataset_id="", actor="owner"):
        await before_model(
            "answer", "actual system+question+text", [hit], tenant_id="tenant", workspace_id="workspace"
        )
    assert receipt.documents["chunk"].digest == sha256(hit.content.encode()).hexdigest()
    assert receipt.native_reads[0].source_ids == ("source",)
    assert receipt.native_reads[0].content_sha256 == sha256(b"actual system+question+text").hexdigest()
    hit.chunk_id = ""
    with (
        observe(receipt, tenant_id="tenant", workspace_id="workspace", dataset_id="", actor="owner"),
        pytest.raises(ServiceUnavailableException, match="provenance"),
    ):
        await before_model(
            "answer", "must not reach model", [hit], tenant_id="tenant", workspace_id="workspace"
        )


@pytest.mark.parametrize("domain,package", [("canon", "flycanon"), ("structured", "flyquery")])
async def test_product_model_scope_without_provenance_observer_fails_closed(domain, package):
    from importlib import import_module

    from koinon.knowledge.adapters import native_scope

    bindings = import_module(package + ".core.agents.model_bindings")
    provenance = import_module(package + ".core.services.query.provenance")
    with native_scope(domain, "tenant", "workspace", "owner"):
        token = bindings.push_bindings(
            tenant_id="tenant", workspace_id="workspace", subject="owner", bindings={}
        )
        try:
            kwargs = {"dataset_id": "dataset"} if domain == "structured" else {}
            with pytest.raises(ServiceUnavailableException, match="observer"):
                await provenance.before_model(
                    "grounding", "factual data", {}, tenant_id="tenant", workspace_id="workspace", **kwargs
                )
        finally:
            bindings.reset_bindings(token)


async def test_inherited_and_expired_native_observation_cannot_reach_model():
    import asyncio

    from flyquery.core.services.query.provenance import before_model, observe

    receipt = NativeEvidenceReceipt("owner", "tenant")
    with (
        observe(receipt, tenant_id="tenant", workspace_id="workspace", dataset_id="dataset", actor="owner"),
        pytest.raises(ServiceUnavailableException, match="expired"),
    ):
        await asyncio.create_task(
            before_model(
                "grounding",
                "must not run",
                {},
                tenant_id="tenant",
                workspace_id="workspace",
                dataset_id="dataset",
            )
        )
    assert receipt.native_reads == []


async def test_real_native_executor_cancellation_is_recorded_after_worker_cleanup(tmp_path, monkeypatch):
    import asyncio
    from threading import Event

    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    from flyquery.core.services.execution.duckdb_executor import DuckDBExecutor
    from flyquery.core.services.query.provenance import observe, resolved

    parquet = tmp_path / "owned.parquet"
    pq.write_table(pa.table({"id": list(range(1000))}), parquet)
    started, closed = Event(), Event()
    original = duckdb.connect

    class Connection:
        def __init__(self, native):
            self.native = native

        def __getattr__(self, key):
            return getattr(self.native, key)

        def execute(self, sql, *args):
            if "CROSS JOIN" in sql:
                started.set()
            return self.native.execute(sql, *args)

        def close(self):
            self.native.close()
            closed.set()

    monkeypatch.setattr(duckdb, "connect", lambda *args, **kwargs: Connection(original(*args, **kwargs)))
    settings = SimpleNamespace(
        duckdb_memory_limit="128MB", default_row_cap=10, default_statement_timeout_ms=3000
    )
    holder = []

    async def work():
        receipt = NativeEvidenceReceipt("owner", "tenant")
        holder.append(receipt)
        with observe(
            receipt, tenant_id="tenant", workspace_id="workspace", dataset_id="dataset", actor="owner"
        ):
            resolved("dataset", [{"name": "orders", "snapshot_id": "snapshot", "table_id": "table"}])
            await DuckDBExecutor(settings).execute(
                "SELECT sum((a.id*b.id*c.id)%997) FROM orders a CROSS JOIN orders b CROSS JOIN orders c",
                {"orders": str(parquet)},
            )

    task = asyncio.create_task(work())
    for _ in range(2000):
        if started.is_set():
            break
        await asyncio.sleep(0.001)
    assert started.is_set()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    (attempt,) = holder[0].sql_attempts
    assert attempt.executed and attempt.outcome == "cancelled" and closed.is_set()
    assert attempt.reason_code == "SQL_ATTEMPT_CANCELLED"


async def test_rlm_legacy_original_remains_unknown_and_never_enters_model_input():
    import asyncio
    from unittest.mock import Mock

    from flycanon.core.services.ingestion.loaders import default_registry
    from flycanon.core.services.query import provenance
    from flycanon.core.services.query.rlm.corpus import CanonDocStore, SourceMeta

    receipt = NativeEvidenceReceipt("owner", "tenant")
    receipt.authorize_model = AsyncMock(return_value=True)
    text = "Exact private-independent native text 😀"
    docs = CanonDocStore(
        {
            "source.txt": SourceMeta(
                "source",
                "source.txt",
                "Title",
                "text",
                "owned-key",
                "stale-hint",
                tenant_id="tenant",
                workspace_id="workspace",
            )
        },
        object_store=SimpleNamespace(get_sync=Mock(return_value=text.encode())),
        registry=default_registry(),
    )

    @provenance.worker
    def run():
        return docs["source.txt"]

    with provenance.observe(receipt, tenant_id="tenant", workspace_id="workspace", actor="owner"):
        await provenance.corpus(docs)
        with pytest.raises(ServiceUnavailableException) as error:
            await asyncio.to_thread(run)
    assert error.value.code == "RLM_DOCUMENT_VIEWS_REQUIRED"
    assert [row.stage for row in receipt.native_reads] == ["rlm.corpus"]
    assert receipt.documents == {} and receipt.document_extractions == {}
    docs._object_store.get_sync.assert_not_called()


async def test_direct_native_controller_receives_only_exact_server_bound_internal_context():
    from flyquery.core.services.query.provenance import observe, request_context
    from starlette.requests import Request

    from koinon.knowledge.adapters import native_scope

    receipt = NativeEvidenceReceipt("owner", "tenant")
    with (
        native_scope("structured", "tenant", "workspace", "owner") as request,
        observe(receipt, tenant_id="tenant", workspace_id="workspace", dataset_id="dataset", actor="owner"),
    ):
        assert request_context(request).actor == "owner"
        other = Request({"type": "http", "headers": [], "state": {"legacy_tenant_context": object()}})
        with pytest.raises(ServiceUnavailableException):
            request_context(other)
    assert request_context(request) is None


async def test_current_canonical_membership_or_pat_revocation_blocks_next_native_stage():
    from flyquery.core.services.query.provenance import observe
    from flyquery.core.services.retrieval.search_index import Hit

    from koinon.catalog.errors import AccessDenied

    fixture = pipeline_fixture()
    workspace, dataset, table, snapshot, column = [str(uuid4()) for _ in range(5)]
    receipt = NativeEvidenceReceipt("owner", "tenant")
    receipt.verify_structured = AsyncMock(return_value=True)
    receipt.authorize_model = AsyncMock(side_effect=[None, None, AccessDenied("Current authority revoked")])
    hit = Hit(
        "schema_object",
        column,
        "Orders total",
        1.0,
        {"table_id": table, "snapshot_id": snapshot, "kind": "COLUMN"},
    )
    service = fixture._make_service()
    service._retriever.retrieve = AsyncMock(return_value={"schema_objects": [hit], "schema_inventory": [hit]})
    service._generation_agent.run = AsyncMock()
    with (
        observe(receipt, tenant_id="tenant", workspace_id=workspace, dataset_id=dataset, actor="owner"),
        pytest.raises(AccessDenied, match="revoked"),
    ):
        await service.answer(
            tenant_id="tenant",
            workspace_id=workspace,
            dataset_id=dataset,
            question="Count",
            scopes={"flyquery.query:read"},
        )
    service._generation_agent.run.assert_not_awaited()
    assert [row.stage for row in receipt.native_reads] == ["rerank", "grounding"]


async def test_executor_admission_failure_never_claims_engine_statement_execution():
    from flyquery.core.services.execution.duckdb_executor import DuckDBExecutor
    from flyquery.core.services.query.provenance import observe

    receipt = NativeEvidenceReceipt("owner", "tenant")
    settings = SimpleNamespace(
        duckdb_memory_limit="128MB", default_row_cap=10, default_statement_timeout_ms=3000
    )
    with observe(receipt, tenant_id="tenant", workspace_id="workspace", dataset_id="dataset", actor="owner"):
        await DuckDBExecutor(settings).execute("SELECT * FROM read_csv_auto('/not-admitted')", {})
    (attempt,) = receipt.sql_attempts
    assert not attempt.executed and attempt.engine is None
    assert attempt.outcome == "failed"
