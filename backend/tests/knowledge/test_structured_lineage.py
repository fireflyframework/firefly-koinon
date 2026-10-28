# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


async def test_native_lineage_scope_expires_in_inherited_child_work_and_standalone_is_optional():
    import asyncio

    from flyquery.core.services.ingestion import lineage

    assert await lineage.emit("receive", file_id="standalone") is None
    seen = []

    class Sink:
        async def emit(self, event, **values):
            seen.append((event, values))
            return "receipt"

    released = asyncio.Event()

    async def child():
        await released.wait()
        await lineage.emit("model_input", run_id="run")

    with lineage.observe(Sink()):
        assert await lineage.emit("receive", file_id="owned") == "receipt"
        task = asyncio.create_task(child())
    released.set()
    with pytest.raises(lineage.LineageError, match="expired"):
        await task
    assert seen == [("receive", {"file_id": "owned"})]


async def test_product_lineage_failure_cannot_be_swallowed_by_header_naming_fallback(tmp_path, monkeypatch):
    from flyquery.core.services.ingestion import lineage
    from flyquery.core.services.ingestion.reader import ColumnSchema, MaterialiseResult
    from flyquery.core.services.ingestion.stages import parse

    class Sink:
        async def emit(self, event, **values):
            raise lineage.LineageError("Durable lineage is unavailable")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-no-network")
    monkeypatch.setattr(parse, "_read_parquet_sample", AsyncMock(return_value=(["column0"], [[1]])))
    agent = SimpleNamespace(run=AsyncMock())
    monkeypatch.setattr(parse, "build_column_name_proposer_agent", lambda _: agent)
    materialized = MaterialiseResult("out.parquet", 10, 1, (ColumnSchema("column0", "INTEGER", True, 0),))
    with lineage.observe(Sink()), pytest.raises(lineage.LineageError):
        await parse._propose_meaningful_column_names(
            section_label="Orders",
            mat_result=materialized,
            parquet_path=str(tmp_path / "out.parquet"),
            settings=SimpleNamespace(),
            logger_=parse.logger,
        )
    agent.run.assert_not_awaited()


async def test_immutable_snapshot_binding_and_unknown_origin_are_distinct(tmp_path, monkeypatch):
    from contextlib import asynccontextmanager
    from uuid import uuid4

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from koinon.knowledge.lineage import service as module
    from koinon.knowledge.lineage.entities import (
        SnapshotLineageRow,
        SourceArtifactRow,
        TransformRunRow,
        TransformStepRow,
    )

    engine = create_async_engine("sqlite+aiosqlite://")
    tables = [
        entity.__table__
        for entity in (SourceArtifactRow, TransformRunRow, TransformStepRow, SnapshotLineageRow)
    ]
    async with engine.begin() as connection:
        for table in tables:
            await connection.run_sync(table.create)
    from flyquery.models.entities.file import File
    from flyquery.models.entities.schema import SchemaSnapshot
    from flyquery.models.entities.table import Table
    from sqlalchemy import JSON, Column, MetaData
    from sqlalchemy import Table as SQLTable
    from sqlalchemy.dialects.postgresql import JSONB

    metadata = MetaData()
    for entity in (SchemaSnapshot, Table, File):
        SQLTable(
            entity.__tablename__,
            metadata,
            *[
                Column(
                    c.name,
                    JSON() if isinstance(c.type, JSONB) else c.type,
                    primary_key=c.primary_key,
                    nullable=c.nullable,
                )
                for c in entity.__table__.columns
            ],
        )
    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def unit(*args, **kwargs):
        async with factory.begin() as session:
            yield session

    monkeypatch.setattr(module, "infrastructure_unit", unit)
    scope = {"tenant_id": "north", "workspace_id": str(uuid4()), "dataset_id": str(uuid4()), "actor": "owner"}
    service = module.NativeStructuredLineage(SimpleNamespace(get=lambda _: object()))
    artifact_id, snapshot_id, table_id = [uuid4() for _ in range(3)]
    sink = service.sink(**scope, operation="upload", authorize=AsyncMock())
    from datetime import UTC, datetime
    from uuid import UUID

    async with factory.begin() as session:
        session.add(
            File(
                id=artifact_id,
                tenant_id=scope["tenant_id"],
                workspace_id=UUID(scope["workspace_id"]),
                dataset_id=UUID(scope["dataset_id"]),
                original_filename="books.xlsx",
                file_format="xlsx",
                compression="none",
                size_bytes=100,
                content_hash_sha256="a" * 64,
                object_store_key="owned/books.xlsx",
                uploaded_by="owner",
                uploaded_at=datetime.now(UTC),
                table_extraction_rules_json={},
                status="RECEIVED",
            )
        )
        await session.flush()
        await sink.emit(
            "received",
            session=session,
            file_id=artifact_id,
            **scope,
            original_filename="books.xlsx",
            sha256="a" * 64,
            byte_size=100,
            file_format="xlsx",
            compression="none",
        )
    from flyquery.core.services.ingestion.lineage import LineageError

    with pytest.raises(LineageError):
        await sink.emit(
            "validate_input",
            file_id=artifact_id,
            input_sha256="b" * 64,
            materialization_input_sha256="b" * 64,
            compression="none",
            **scope,
        )
    await sink.emit(
        "validate_input",
        file_id=artifact_id,
        input_sha256="a" * 64,
        materialization_input_sha256="a" * 64,
        compression="none",
        **scope,
    )
    run = await sink.emit(
        "begin_section",
        file_id=artifact_id,
        **scope,
        sheet_or_json_path="Sales#section[0:3]",
        table_label="Sales",
        implementation="native.ExcelReader",
        implementation_sha256="b" * 64,
        parameters={},
    )
    await sink.emit(
        "step",
        run_id=run,
        kind="materialize",
        input_sha256="a" * 64,
        implementation="native.ExcelReader",
        output_sha256="c" * 64,
        parameters={},
    )
    await sink.emit(
        "step",
        run_id=run,
        kind="finalize_parquet",
        implementation="structured.parse",
        output_sha256="d" * 64,
        parameters={},
    )
    from datetime import UTC, datetime
    from uuid import UUID

    now = datetime.now(UTC)
    async with factory.begin() as session:
        session.add(
            Table(
                id=table_id,
                tenant_id=scope["tenant_id"],
                workspace_id=UUID(scope["workspace_id"]),
                dataset_id=UUID(scope["dataset_id"]),
                name="sales",
                qualified_name="books.sales",
                kind="UPLOADED",
                is_active=True,
                created_at=now,
                updated_at=now,
                current_snapshot_id=snapshot_id,
            )
        )
        session.add(
            SchemaSnapshot(
                id=snapshot_id,
                tenant_id=scope["tenant_id"],
                workspace_id=UUID(scope["workspace_id"]),
                dataset_id=UUID(scope["dataset_id"]),
                table_id=table_id,
                taken_at=now,
                snapshot_hash="e" * 64,
                n_columns=1,
                status="READY",
                triggered_by="USER",
                created_by="owner",
            )
        )
        await session.flush()
        await sink.emit(
            "bind_snapshot",
            session=session,
            snapshot_id=snapshot_id,
            table_id=table_id,
            **scope,
            schema_sha256="e" * 64,
            row_count=2,
            receipt={"run_id": run, "parquet_sha256": "d" * 64, "parquet_byte_size": 120},
        )
    async with factory() as session:
        first = await service.describe(session, snapshot_id, table_id, "READY", scope)
        missing = await service.describe(session, uuid4(), table_id, "READY", scope)
    assert first.status == "recorded" and first.level == "file_section"
    assert first.artifact.original_filename == "books.xlsx" and first.artifact.sha256 == "a" * 64
    assert first.sheet_or_json_path == "Sales#section[0:3]" and first.parquet_sha256 == "d" * 64
    assert first.steps[0].input_sha256 == "a" * 64 and first.steps[1].input_sha256 is None
    assert [step.kind for step in first.steps] == ["materialize", "finalize_parquet"]
    assert missing.status == "not_recorded" and missing.artifact is None and missing.steps == ()
    from datetime import timedelta

    newer = uuid4()
    async with factory.begin() as session:
        session.add(
            SchemaSnapshot(
                id=newer,
                tenant_id=scope["tenant_id"],
                workspace_id=UUID(scope["workspace_id"]),
                dataset_id=UUID(scope["dataset_id"]),
                table_id=table_id,
                taken_at=now + timedelta(seconds=1),
                snapshot_hash="f" * 64,
                n_columns=1,
                status="FAILED",
                triggered_by="USER",
                created_by="owner",
            )
        )
    history = await service.read_table_history(**scope, table_id=str(table_id), page=1, page_size=1)
    assert history.total == 2 and history.has_next and history.total_pages == 2
    assert history.items[0].snapshot_id == str(newer) and history.items[0].status == "not_recorded"
    assert history.current_snapshot_id == str(snapshot_id)
    second = await service.read_table_history(**scope, table_id=str(table_id), page=2, page_size=1)
    assert second.items[0].artifact.sha256 == "a" * 64 and second.has_previous and not second.has_next
    from koinon.catalog.errors import AccessDenied

    with pytest.raises(AccessDenied):
        await service.read_snapshots(**{**scope, "tenant_id": "south"}, snapshot_ids=(str(snapshot_id),))
    with pytest.raises(AccessDenied):
        async with factory.begin() as session:
            await sink.emit(
                "bind_snapshot",
                session=session,
                snapshot_id=uuid4(),
                table_id=table_id,
                **scope,
                schema_sha256="e" * 64,
                row_count=2,
                receipt={"run_id": run, "parquet_sha256": "d" * 64, "parquet_byte_size": 120},
            )
    await engine.dispose()


async def test_real_multi_sheet_xlsx_retains_selected_sections_and_final_parquet_hashes(
    tmp_path, monkeypatch
):
    from hashlib import sha256
    from pathlib import Path
    from uuid import uuid4

    import openpyxl
    from flyquery.core.services.ingestion import lineage
    from flyquery.core.services.ingestion.stages import parse

    workbook = openpyxl.Workbook()
    first = workbook.active
    first.title = "Northern Sales"
    first.append(["item", "amount"])
    first.append(["A", 12])
    second = workbook.create_sheet("Southern Sales")
    second.append(["item", "amount"])
    second.append(["B", 47])
    path = tmp_path / "regions.xlsx"
    workbook.save(path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(parse, "_next_version", AsyncMock(return_value=1))

    async def insert(**kwargs):
        return kwargs["table_id"]

    monkeypatch.setattr(parse, "_insert_table", insert)
    events, stored = [], {}

    class Sink:
        async def emit(self, event, **values):
            events.append((event, values))
            if event == "defer_table_file":
                return True
            return str(uuid4()) if event == "begin_section" else None

    class Store:
        async def put(self, key, body, content_type):
            stored[key] = body

    with lineage.observe(Sink()):
        tables = await parse.run_parse(
            tenant_id="north",
            workspace_id=uuid4(),
            dataset_id=uuid4(),
            file_id=uuid4(),
            local_temp_path=str(path),
            file_format="xlsx",
            compression="none",
            object_store=Store(),
            session_factory=object(),
            settings=SimpleNamespace(type_infer_sample_rows=1000, max_title_rows=3),
            original_filename="regions.xlsx",
        )
    assert len(tables) == 2
    sections = [values["sheet_or_json_path"] for event, values in events if event == "begin_section"]
    assert sections[0].startswith("Northern Sales#section[") and sections[1].startswith(
        "Southern Sales#section["
    )
    monkeypatch.setattr(
        parse, "_update_table_file", AsyncMock(side_effect=AssertionError("Early file pointer mutation"))
    )
    with lineage.observe(Sink()):
        replaced = await parse.run_parse(
            tenant_id="north",
            workspace_id=uuid4(),
            dataset_id=uuid4(),
            file_id=uuid4(),
            local_temp_path=str(path),
            file_format="xlsx",
            compression="none",
            object_store=Store(),
            session_factory=object(),
            settings=SimpleNamespace(type_infer_sample_rows=1000, max_title_rows=3),
            original_filename="regions.xlsx",
            existing_table_id=tables[1].table_id,
            target_sheet_or_json_path=tables[1].sheet_or_json_path,
        )
    assert len(replaced) == 1 and replaced[0].sheet_or_json_path.startswith("Southern Sales#section[")
    parse._update_table_file.assert_not_awaited()
    Path(replaced[0].local_parquet_path).unlink()
    for table in tables:
        assert table.lineage_receipt["parquet_sha256"] == sha256(stored[table.parquet_key]).hexdigest()
        assert table.lineage_receipt["parquet_byte_size"] == len(stored[table.parquet_key])
        assert table.result.n_rows_actual == 1
        Path(table.local_parquet_path).unlink()


async def test_authority_and_version_denials_keep_their_http_semantics():
    from flyquery.core.services.ingestion import lineage
    from pyfly.kernel import ConflictException, ForbiddenException

    class Sink:
        def __init__(self, error):
            self.error = error

        async def emit(self, event, **values):
            raise self.error

    for original, expected, code in [
        (ForbiddenException("private"), ForbiddenException, "ACCESS_DENIED"),
        (
            ConflictException("private", code="CONTENT_VERSION_CONFLICT"),
            ConflictException,
            "CONTENT_VERSION_CONFLICT",
        ),
    ]:
        with lineage.observe(Sink(original)), pytest.raises(expected) as failure:
            await lineage.emit("model_input", run_id="run")
        assert isinstance(failure.value, lineage.LineageError)
        assert failure.value.code == code


async def test_cancellation_is_not_replaced_by_failure_to_record_its_last_step():
    import asyncio

    from flyquery.core.services.ingestion import lineage

    class Sink:
        async def emit(self, event, **values):
            if values.get("kind") == "stage_failed":
                raise RuntimeError("Storage is unavailable")

    with lineage.observe(Sink()), pytest.raises(asyncio.CancelledError):
        async with lineage.stage("run", "describe"):
            raise asyncio.CancelledError()


async def test_each_description_model_input_requires_current_durable_receipt_even_with_provider_fallback(
    monkeypatch,
):
    from uuid import uuid4

    from flyquery.core.agents import describe_agent
    from flyquery.core.services.ingestion import lineage
    from flyquery.core.services.ingestion.stages import describe

    class Sink:
        async def emit(self, event, **values):
            raise lineage.LineageError("Authority or durable receipt is unavailable")

    monkeypatch.setattr(
        describe,
        "_load_undescribed_columns",
        AsyncMock(
            return_value=[
                {
                    "id": uuid4(),
                    "qualified_name": "sales.amount",
                    "data_type": "INTEGER",
                    "sample_values_json": [47],
                }
            ]
        ),
    )
    agent = SimpleNamespace(run=AsyncMock())
    monkeypatch.setattr(describe_agent, "build_describe_agent", lambda _: agent)
    with lineage.observe(Sink()), pytest.raises(lineage.LineageError):
        await describe.run_describe(
            tenant_id="north",
            snapshot_id=uuid4(),
            session_factory=object(),
            settings=SimpleNamespace(
                allow_provider_fallback=True, describe_batch=50, describe_budget_cents_per_run=100
            ),
        )
    agent.run.assert_not_awaited()
