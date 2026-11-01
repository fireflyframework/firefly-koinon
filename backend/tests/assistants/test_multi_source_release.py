# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""A useful mixed answer preserves two exact documents and a real native SQL aggregate."""

from hashlib import sha256
from types import SimpleNamespace

import pyarrow as pa
import pyarrow.parquet as pq
from flyquery.core.services.execution.duckdb_executor import DuckDBExecutor, ExecutionResult
from flyquery.core.services.query.provenance import observe, resolved
from test_evidence_capture_consumer import fixture
from test_service import assistants as assistants

from koinon.answers.dtos import EvidenceAnswerPlan
from koinon.assistants.audit import AnswerAudits
from koinon.assistants.memory.service import PersonalConversationMemory
from koinon.assistants.queue import AssistantQueue
from koinon.evidence.dtos import SourceReference
from koinon.evidence.ports import ConversationOutputPort, ConversationSnapshotPort, SourceResolverPort
from koinon.knowledge.capture_dtos import CapturedEvidence
from koinon.knowledge.capture_receipt import NativeEvidenceReceipt


async def test_two_document_quotes_and_native_sum_release_with_separate_source_lineage(assistants, tmp_path):
    service, context, run, first, _, _ = await fixture(assistants)
    second = await service.catalog.create(
        "issuer|admin", "north", kind="document", name="Accounting policy", parent_id=first.parent_id
    )
    dataset = await service.catalog.create(
        "issuer|admin", "north", kind="dataset", name="Invoices", parent_id=first.parent_id
    )
    run.scope = {"asset_ids": [first.id, second.id, dataset.id]}
    await service.runs.save(run)
    thread = await service.threads.find_by_id(run.thread_id)
    thread.scope = run.scope
    await service.threads.save(thread)
    queue = context.get_bean(AssistantQueue)
    generation = await queue.begin_generation(
        run.id, "proposal-worker", model_id="controlled", model_class="controlled", api="chat"
    )
    await context.get_bean(PersonalConversationMemory).build(run, generation_id=generation)
    hits, references = [], []
    for entry, filename, passage in (
        (first, "Operations.txt", "Service reviews are owned by the Operations team."),
        (second, "Accounting.txt", "Invoice amounts in the approved dataset are recorded in EUR."),
    ):
        path = tmp_path / filename
        path.write_text(passage)
        text = path.read_text()
        hits.append({"asset_id": entry.id, "id": filename, "title": entry.name, "text": text})
        references.append(
            SourceReference(
                id=filename,
                asset_id=entry.id,
                source_id=entry.parent_id,
                title=entry.name,
                kind="document",
                chunk_id=filename,
                quote=text,
                used_revision="chunk-sha256:" + sha256(text.encode()).hexdigest(),
            )
        )
    data = {"hits": hits}
    await queue.evidence(
        run.id,
        "proposal-worker",
        "search",
        data,
        [first.id, second.id],
        capture=CapturedEvidence(data, tuple(references), True),
    )
    parquet = tmp_path / "orders.parquet"
    pq.write_table(pa.table({"amount": [1250, 2750]}), parquet)
    sql = "SELECT SUM(amount) AS total, 999 AS invented FROM orders"
    native = NativeEvidenceReceipt("issuer|admin", "north")
    executor = DuckDBExecutor(
        SimpleNamespace(duckdb_memory_limit="128MB", default_row_cap=10, default_statement_timeout_ms=3000)
    )
    try:
        with observe(
            native,
            tenant_id="north",
            workspace_id=dataset.workspace_id,
            dataset_id=dataset.id,
            actor="issuer|admin",
        ):
            resolved(
                dataset.id, [{"table_id": "orders-table", "name": "orders", "snapshot_id": "orders-snapshot"}]
            )
            output = await executor.execute(sql, {"orders": str(parquet)})
            assert isinstance(output, ExecutionResult)
            query_data = {
                "query_id": "native-invoice-query",
                "execution_status": "OK",
                "sql": sql,
                "preview": output.rows,
                "row_count": output.row_count,
                "truncated": output.truncated,
                "snapshot_pins": {"orders": "orders-snapshot"},
            }
            native.query("north", dataset.workspace_id, "issuer|admin", dataset.id, query_data)
    finally:
        await executor.close()
    source = SourceReference(
        id="invoice-source",
        asset_id=dataset.id,
        source_id=dataset.parent_id,
        title=dataset.name,
        kind="dataset",
        snapshot_id="orders-snapshot",
        query_id="native-invoice-query",
        used_revision="orders-snapshot",
    )
    query_id = await queue.evidence(
        run.id,
        "proposal-worker",
        "query",
        query_data,
        [dataset.id],
        capture=CapturedEvidence(
            query_data,
            (source,),
            native.complete,
            native_reads=tuple(native.native_reads),
            sql_attempts=native.sql_attempts,
            query_results=tuple(native.query_results),
        ),
    )
    facts = await queue.fact_pool(run.id, "proposal-worker")
    assert [(fact.label, fact.value) for fact in facts if fact.kind == "derived"] == [
        ("SUM(orders.amount)", 4000)
    ]
    assert all(fact.value != 999 for fact in facts)
    plan = EvidenceAnswerPlan(
        outcome="answer",
        quotes=[{"fact_id": fact.id, "quote": fact.text} for fact in facts if fact.kind == "quote"],
        values=[{"fact_id": fact.id} for fact in facts if fact.kind == "derived"],
    )
    await queue.release_answer(run.id, "proposal-worker", plan, "en")
    await queue.finish(run.id, "proposal-worker")
    message = await service.message_repository.find_by_id(run.message_id)
    assert all(
        passage in message.text for passage in (hits[0]["text"], hits[1]["text"], "SUM(orders.amount): 4000")
    )
    assert "999" not in message.text
    async def resolve_sources(subject, tenant_id, values):
        assert subject == "issuer|admin" and tenant_id == "north"
        return tuple(value.model_copy(update={"availability": "available"}) for value in values)

    context.container.register_instance(SourceResolverPort, SimpleNamespace(resolve=resolve_sources))
    audit = await context.get_bean(AnswerAudits).get("issuer|admin", "north", run.id)
    assert {ref["asset_id"] for ref in audit["output_release"]["source_refs"]} == {
        first.id,
        second.id,
        dataset.id,
    }
    assert audit["sql_attempts"][0]["executed"] and audit["sql_attempts"][0]["statement"] == sql
    result = await service.result("issuer|admin", "north", run.id, query_id)
    assert result["data"]["preview"] == [{"field": "SUM(orders.amount)", "value": 4000}]
    snapshot = await context.get_bean(ConversationSnapshotPort).snapshot(
        "issuer|admin", "north", run.thread_id, [run.message_id]
    )
    assert snapshot.source_manifest_complete and len(snapshot.sources) == 3
    await context.get_bean(ConversationOutputPort).authorize_output(
        "issuer|admin", "north", run.thread_id, [run.message_id], snapshot=snapshot
    )
