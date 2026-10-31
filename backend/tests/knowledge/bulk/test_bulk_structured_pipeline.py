# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import hashlib
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from pyfly.kernel import ConflictException

from koinon.knowledge.bulk.dtos import BulkDestination
from koinon.knowledge.bulk.queue import BulkLease
from koinon.knowledge.bulk.structured_dtos import (
    StructuredCommitReceipt,
    StructuredOperationIdentity,
    StructuredOperationState,
)


@pytest.mark.parametrize("incomplete", [False, True])
async def test_prepared_dataset_resume_publishes_without_processing_replay(tmp_path, monkeypatch, incomplete):
    from flyquery.core.services.ingestion.reader import ColumnSchema, MaterialiseResult, ProposedTable
    from flyquery.core.services.ingestion.stages.parse import ParsedTable

    from koinon.knowledge.bulk import structured_pipeline as module

    identity = StructuredOperationIdentity(
        operation_id=uuid4(),
        tenant_id="north",
        workspace_id=uuid4(),
        dataset_id=uuid4(),
        file_id=uuid4(),
        actor="owner",
        catalog_source_id="source",
        catalog_dataset_id="asset",
        catalog_file_version_id="version",
        filename="facts.csv",
        sha256=hashlib.sha256(b"original").hexdigest(),
        size_bytes=8,
    )
    lease = BulkLease(
        job_id="job",
        item_id=str(identity.operation_id),
        batch_id="batch",
        tenant_id="north",
        subject="owner",
        token_id=None,
        worker_id="worker",
        attempt=1,
        source_id="source",
        asset_id="asset",
        filename="facts.csv",
        size_bytes=8,
        sha256=identity.sha256,
        mode="dataset",
        destination=BulkDestination(workspace_id="workspace", project_id="project", parent_id="parent"),
    )
    active = {"gate": 0, "unit": 0}
    state = None

    @asynccontextmanager
    async def publication(*args):
        active["gate"] += 1
        try:
            yield
        finally:
            active["gate"] -= 1

    class Unit:
        async def get(self, _):
            return state

        async def admit(self, _):
            nonlocal state
            assert active["gate"] and active["unit"]
            state = StructuredOperationState(identity=identity, status="admitted")
            return state

        async def plan(self, _, plan):
            nonlocal state
            assert active["gate"] and active["unit"]
            state = state.model_copy(update={"plan": plan})
            return state

        async def prepared(self, _, tables):
            nonlocal state
            assert active["gate"] and active["unit"]
            state = state.model_copy(update={"prepared": tables, "status": "prepared"})
            return state

        async def publication(self, _):
            assert active["gate"] and active["unit"]
            return state

        async def commit(self, _):
            nonlocal state
            assert active["gate"] and active["unit"]
            state = state.model_copy(
                update={
                    "status": "committed",
                    "receipt": StructuredCommitReceipt(
                        file_id=identity.file_id,
                        dataset_id=identity.dataset_id,
                        sha256=identity.sha256,
                        size_bytes=8,
                        object_key="raw/owned",
                        tables=state.prepared,
                    ),
                }
            )
            return state

    @asynccontextmanager
    async def write():
        active["unit"] += 1
        try:
            yield Unit()
        finally:
            active["unit"] -= 1

    raw = tmp_path / "raw.csv"
    parquet = tmp_path / "output.parquet"
    receive = AsyncMock()

    async def received(**values):
        assert state.status == "admitted" and active["gate"] and values["file_id"] == identity.file_id
        raw.write_bytes(b"original")
        return SimpleNamespace(
            local_temp_path=str(raw),
            file_format="csv",
            compression="none",
            size_bytes=8,
            file_id=identity.file_id,
            content_hash_sha256=identity.sha256,
        )

    receive.side_effect = received

    async def parsed(**values):
        assert values["extract_only"] is True and values["append_only"] is True and values["max_tables"] == 16
        ids = await values["reserve_tables"]((ProposedTable("facts", None, 1, 1),))
        assert state.plan and ids[0] == state.plan[0].table_id
        parquet.write_bytes(b"parquet")
        return [
            ParsedTable(
                table_id=ids[0],
                name="facts",
                qualified_name="bulk.facts",
                sheet_or_json_path=None,
                parquet_key="parquet/owned",
                result=MaterialiseResult(
                    "parquet/owned", 7, 1, (ColumnSchema("column0", "INTEGER", False, 0),)
                ),
                local_parquet_path=str(parquet),
                lineage_receipt={
                    "run_id": str(uuid4()),
                    "parquet_sha256": hashlib.sha256(b"parquet").hexdigest(),
                    "parquet_byte_size": 7,
                },
            )
        ]

    parse = AsyncMock(side_effect=parsed)

    async def reconciled(**values):
        return SimpleNamespace(snapshot_id=values["snapshot_id"], n_columns=1, n_rows_actual=1)

    embed = AsyncMock(
        return_value={"objects_processed": 2, "embeddings_written": 1 if incomplete else 2, "model": "bound"}
    )
    published = AsyncMock()

    async def publish(**values):
        assert active["gate"] and active["unit"] and values["emit_event"] is False

    published.side_effect = publish
    for name, value in {
        "run_receive": receive,
        "run_parse": parse,
        "run_reconcile": AsyncMock(side_effect=reconciled),
        "run_sample": AsyncMock(),
        "run_profile": AsyncMock(),
        "run_embed": embed,
        "run_publish": published,
    }.items():
        monkeypatch.setattr(module, name, value)
    operations = SimpleNamespace(
        configuration=lambda: SimpleNamespace(default_locale="en-US"),
        native=lambda: SimpleNamespace(sessionmaker=object()),
        write=write,
    )
    queue = SimpleNamespace(
        check=AsyncMock(),
        _check=AsyncMock(),
        publication=publication,
        reserve_tables=AsyncMock(
            side_effect=lambda _, plans: tuple(
                p.model_copy(update={"catalog_table_id": f"catalog-{p.ordinal}"}) for p in plans
            )
        ),
    )
    stores = SimpleNamespace(get=Mock(return_value=object()))
    workspaces = SimpleNamespace(
        get=lambda: SimpleNamespace(
            get=AsyncMock(return_value={"tenant_id": "north", "storage_used_bytes": 0}),
            track_storage=AsyncMock(),
        )
    )
    pipeline = module.StructuredBulkPipeline(
        operations, queue, stores, workspaces, SimpleNamespace(get=lambda: object())
    )
    if incomplete:
        with pytest.raises(ConflictException) as failed:
            await pipeline.prepare(lease, identity, b"original")
        assert failed.value.code == "BULK_EMBEDDING_INCOMPLETE" and state.status == "admitted"
        published.assert_not_awaited()
    else:
        prepared = await pipeline.prepare(lease, identity, b"original")
        assert prepared.status == "prepared" and len(prepared.prepared) == 1
        stores.get.reset_mock()
        receive.reset_mock()
        parse.reset_mock()
        embed.reset_mock()
        final = await pipeline.finalize(lease, identity)
        assert final.status == "committed" and final.receipt.sha256 == identity.sha256
        receive.assert_not_awaited()
        parse.assert_not_awaited()
        embed.assert_not_awaited()
        stores.get.assert_not_called()
        published.assert_awaited_once()
    assert not raw.exists() and not parquet.exists()
