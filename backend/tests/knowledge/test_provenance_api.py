# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from test_facade import context as context
from test_facade import upload

from koinon.catalog.errors import AccessDenied, InvalidHierarchy
from koinon.knowledge.lineage.dtos import LineagePage, SnapshotLineage, SourceArtifact, TransformStep
from koinon.knowledge.provenance.service import TableProvenanceService


@pytest.fixture
async def provenance(context):
    knowledge, catalog, domains, _, _ = context
    snapshot_id = str(uuid4())
    domains.ingest_dataset.return_value = {
        "dataset_id": "native-dataset",
        "file_id": "native-file",
        "tables": [{"table_id": "native-table", "name": "Forecast", "snapshot_id": snapshot_id}],
    }
    dataset = (await upload(context, "dataset"))["assets"][0]["id"]
    table = (await catalog.list("issuer|admin", "north", kind="table", parent_id=dataset))[0].id
    stamp = datetime(2026, 10, 27, tzinfo=UTC)
    artifact = SourceArtifact("file", "planning.xlsx", "a" * 64, 1234, "XLSX", "NONE", "issuer|admin", stamp)
    step = TransformStep(
        "step", 1, "materialize", "test.reader", "a" * 64, "b" * 64, {"header_row": 1}, "issuer|admin", stamp
    )
    receipt = SnapshotLineage(
        tenant_id="north",
        workspace_id="native-workspace",
        dataset_id="native-dataset",
        table_id="native-table",
        snapshot_id=snapshot_id,
        status="recorded",
        snapshot_status="READY",
        artifact=artifact,
        run_id="run",
        operation="upload",
        sheet_or_json_path="Forecast#section[0:3]",
        parquet_sha256="b" * 64,
        parquet_byte_size=456,
        row_count=2,
        actor="issuer|admin",
        recorded_at=stamp,
        steps=(step,),
    )
    reader = SimpleNamespace(
        read_snapshots=AsyncMock(return_value=(receipt,)), read_table_history=AsyncMock()
    )
    return (
        TableProvenanceService(knowledge, SimpleNamespace(get=lambda: reader)),
        reader,
        receipt,
        dataset,
        table,
    )


async def test_exact_snapshot_preserves_distinct_hashes_and_canonical_ids(provenance):
    service, reader, receipt, dataset, table = provenance
    value = await service.snapshot("issuer|reader", "north", dataset, table, receipt.snapshot_id)
    assert (value.dataset_id, value.table_id, value.snapshot_id) == (dataset, table, receipt.snapshot_id)
    assert value.artifact.sha256 == "a" * 64 and value.parquet_sha256 == "b" * 64
    assert value.sheet_or_json_path == "Forecast#section[0:3]" and value.level == "file_section"
    assert value.steps[0].input_sha256 == "a" * 64
    reader.read_snapshots.assert_awaited_once_with(
        actor="issuer|reader",
        tenant_id="north",
        workspace_id="native-workspace",
        dataset_id="native-dataset",
        snapshot_ids=(receipt.snapshot_id,),
    )


async def test_foreign_authority_is_denied_before_native_read(provenance):
    service, reader, receipt, dataset, table = provenance
    for subject, tenant in (("issuer|outsider", "north"), ("issuer|reader", "south")):
        with pytest.raises(AccessDenied):
            await service.snapshot(subject, tenant, dataset, table, receipt.snapshot_id)
    reader.read_snapshots.assert_not_awaited()


async def test_native_scope_and_snapshot_mismatch_cannot_be_exposed(provenance):
    service, reader, receipt, dataset, table = provenance
    for changes in (
        {"tenant_id": "south"},
        {"workspace_id": "foreign"},
        {"dataset_id": "foreign"},
        {"table_id": "foreign"},
        {"snapshot_id": str(uuid4())},
    ):
        reader.read_snapshots.return_value = (replace(receipt, **changes),)
        with pytest.raises(AccessDenied):
            await service.snapshot("issuer|reader", "north", dataset, table, receipt.snapshot_id)


async def test_unrecorded_history_never_fills_origin_from_current_metadata(provenance):
    service, reader, receipt, dataset, table = provenance
    await service.knowledge.catalog.update(
        "issuer|admin", "north", table, {"metadata": {"filename": "current-file.xlsx", "sha256": "f" * 64}}
    )
    reader.read_snapshots.return_value = (
        SnapshotLineage(
            tenant_id=receipt.tenant_id,
            workspace_id=receipt.workspace_id,
            dataset_id=receipt.dataset_id,
            table_id=receipt.table_id,
            snapshot_id=receipt.snapshot_id,
            snapshot_status="READY",
            status="not_recorded",
        ),
    )
    value = await service.snapshot("issuer|reader", "north", dataset, table, receipt.snapshot_id)
    assert value.status == "not_recorded" and value.artifact is None and value.steps == ()
    assert "current-file.xlsx" not in value.model_dump_json()


async def test_history_keeps_server_page_and_observed_current_pointer(provenance):
    service, reader, receipt, dataset, table = provenance
    current = str(uuid4())
    reader.read_table_history.return_value = LineagePage((receipt,), 26, 2, 25, 2, False, True, current)
    value = await service.history("issuer|reader", "north", dataset, table, page=2, page_size=25)
    assert (value.page, value.page_size, value.total, value.pages) == (2, 25, 26, 2)
    assert value.current_snapshot_id == current and value.items[0].snapshot_id == receipt.snapshot_id
    assert not hasattr(value.items[0], "steps")
    reader.read_table_history.assert_awaited_once_with(
        actor="issuer|reader",
        tenant_id="north",
        workspace_id="native-workspace",
        dataset_id="native-dataset",
        table_id="native-table",
        page=2,
        page_size=25,
    )


async def test_invalid_kind_and_pagination_are_refused_before_native_read(provenance):
    from pyfly.kernel import InvalidRequestException

    service, reader, receipt, dataset, table = provenance
    with pytest.raises(InvalidHierarchy):
        await service.snapshot("issuer|reader", "north", dataset, dataset, receipt.snapshot_id)
    for values in ({"page": 0}, {"page_size": 101}, {"page_size": 0}, {"page": True}):
        with pytest.raises(InvalidRequestException):
            await service.history("issuer|reader", "north", dataset, table, **values)
    reader.read_snapshots.assert_not_awaited()
    reader.read_table_history.assert_not_awaited()


async def test_incomplete_recorded_binding_cannot_be_reported_as_recorded(provenance):
    from pyfly.kernel import ServiceUnavailableException

    service, reader, receipt, dataset, table = provenance
    for changes in ({"artifact": None}, {"run_id": None}, {"steps": ()}, {"parquet_sha256": None}):
        reader.read_snapshots.return_value = (replace(receipt, **changes),)
        with pytest.raises(ServiceUnavailableException):
            await service.snapshot("issuer|reader", "north", dataset, table, receipt.snapshot_id)


async def test_missing_datasource_is_unavailable_not_unknown_historical_origin(provenance):
    from pyfly.data.relational.datasource_registry import NoSuchDataSourceError
    from pyfly.kernel import ServiceUnavailableException

    service, reader, receipt, dataset, table = provenance
    reader.read_snapshots.side_effect = NoSuchDataSourceError("structured")
    with pytest.raises(ServiceUnavailableException):
        await service.snapshot("issuer|reader", "north", dataset, table, receipt.snapshot_id)
