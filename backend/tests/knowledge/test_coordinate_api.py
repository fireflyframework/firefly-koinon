# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from flyquery.core.services.ingestion.coordinates import ColumnOrigin, RowRange
from pydantic import ValidationError
from pyfly.kernel import InvalidRequestException, ServiceUnavailableException
from test_facade import context as context
from test_provenance_api import provenance as provenance

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.lineage.coordinate_dtos import (
    CoordinateManifest,
    CoordinatePage,
    CoordinateSelection,
    SourceCell,
)


@pytest.fixture
async def coordinates(provenance):
    from koinon.knowledge.provenance.coordinate_service import TableCoordinateService

    bindings, _, receipt, dataset, table = provenance
    manifest = CoordinateManifest(
        tenant_id=receipt.tenant_id,
        workspace_id=receipt.workspace_id,
        dataset_id=receipt.dataset_id,
        table_id=receipt.table_id,
        snapshot_id=receipt.snapshot_id,
        status="complete",
        row_count=2,
        column_count=2,
        artifact_id="artifact",
        run_id="run",
        input_sha256="a" * 64,
        mapping_sha256="b" * 64,
        source_format="XLSX",
        source_variant="xlsx",
        row_kind="sheet_row",
        source_sheet="Plan",
        parser_decisions=(("header_row", 3),),
        dependencies=(("openpyxl", "3.1.5"),),
    )
    reader = SimpleNamespace(
        read_manifest=AsyncMock(return_value=manifest),
        read_cells=AsyncMock(),
        read_row_ranges=AsyncMock(),
        read_column_bindings=AsyncMock(),
    )
    return (
        TableCoordinateService(bindings, SimpleNamespace(get=lambda: reader)),
        reader,
        manifest,
        dataset,
        table,
    )


async def test_exact_manifest_uses_canonical_ids_and_observed_native_coordinates(coordinates):
    service, reader, manifest, dataset, table = coordinates
    value = await service.manifest("issuer|reader", "north", dataset, table, manifest.snapshot_id)
    assert (value.dataset_id, value.table_id, value.native_table_id) == (dataset, table, "native-table")
    assert value.source_sheet == "Plan" and value.index_base == 0
    assert value.model_dump(mode="json")["parser_decisions"] == [{"name": "header_row", "value": 3}]
    assert value.model_dump(mode="json")["dependencies"] == [{"name": "openpyxl", "version": "3.1.5"}]
    assert "values" not in value.model_dump()
    assert reader.read_manifest.await_args.kwargs == dict(
        actor="issuer|reader",
        tenant_id="north",
        workspace_id="native-workspace",
        dataset_id="native-dataset",
        table_id="native-table",
        snapshot_id=manifest.snapshot_id,
    )


async def test_authority_precedes_coordinate_access(coordinates):
    service, reader, manifest, dataset, table = coordinates
    for subject, tenant in (("issuer|outsider", "north"), ("issuer|reader", "south")):
        with pytest.raises(AccessDenied):
            await service.manifest(subject, tenant, dataset, table, manifest.snapshot_id)
    reader.read_manifest.assert_not_awaited()


@pytest.mark.parametrize("field", ("tenant_id", "workspace_id", "dataset_id", "table_id", "snapshot_id"))
async def test_foreign_native_coordinate_scope_is_never_projected(coordinates, field):
    service, reader, manifest, dataset, table = coordinates
    reader.read_manifest.return_value = replace(manifest, **{field: "foreign"})
    with pytest.raises(AccessDenied):
        await service.manifest("issuer|reader", "north", dataset, table, manifest.snapshot_id)


@pytest.mark.parametrize(
    "changes",
    (
        {"index_base": True},
        {"index_base": 1},
        {"row_count": True},
        {"mapping_sha256": None},
        {"status": "partial"},
        {"source_path": (False,)},
        {"parser_decisions": (("bad", float("nan")),)},
        {"rejected_source_rows": (2, 2)},
    ),
)
async def test_invalid_native_receipts_fail_closed(coordinates, changes):
    service, reader, manifest, dataset, table = coordinates
    reader.read_manifest.return_value = replace(manifest, **changes)
    with pytest.raises(ServiceUnavailableException):
        await service.manifest("issuer|reader", "north", dataset, table, manifest.snapshot_id)


async def test_old_snapshot_has_no_current_origin_backfill(coordinates):
    service, reader, manifest, dataset, table = coordinates
    reader.read_manifest.return_value = CoordinateManifest(
        **{
            key: getattr(manifest, key)
            for key in ("tenant_id", "workspace_id", "dataset_id", "table_id", "snapshot_id")
        },
        status="not_recorded",
    )
    value = await service.manifest("issuer|reader", "north", dataset, table, manifest.snapshot_id)
    assert value.status == "not_recorded" and value.artifact_id is None and value.row_count is None
    reader.read_manifest.return_value = replace(reader.read_manifest.return_value, artifact_id="current")
    with pytest.raises(ServiceUnavailableException):
        await service.manifest("issuer|reader", "north", dataset, table, manifest.snapshot_id)


async def test_cells_preserve_requested_order_and_exact_header_positions(coordinates):
    from koinon.knowledge.provenance.coordinate_dtos import CoordinateCellRequest

    service, reader, manifest, dataset, table = coordinates
    request = CoordinateCellRequest(
        snapshot_id=manifest.snapshot_id, cells=[{"row": 1, "column": 1}, {"row": 0, "column": 0}]
    )
    reader.read_cells.return_value = CoordinateSelection(
        manifest,
        (
            SourceCell(1, 1, 5, 6, (), ((3, 6),), "int"),
            SourceCell(0, 0, 4, 3, (), ((3, 3),), "str"),
        ),
    )
    value = await service.cells("issuer|reader", "north", dataset, table, request)
    assert [(cell.source_row, cell.source_column) for cell in value.items] == [(5, 6), (4, 3)]
    assert value.items[0].model_dump(mode="json")["header_cells"] == [{"row": 3, "column": 6}]
    reader.read_cells.return_value = replace(
        reader.read_cells.return_value, items=reader.read_cells.return_value.items[::-1]
    )
    with pytest.raises(ServiceUnavailableException):
        await service.cells("issuer|reader", "north", dataset, table, request)


@pytest.mark.parametrize(
    "cells",
    (
        [],
        [{"row": True, "column": 0}],
        [{"row": 0.5, "column": 1}],
        [{"row": -1, "column": 1}],
        [{"row": 0, "column": 0}] * 2,
    ),
)
def test_cell_request_rejects_ambiguous_or_duplicate_positions(cells):
    from koinon.knowledge.provenance.coordinate_dtos import CoordinateCellRequest

    with pytest.raises(ValidationError):
        CoordinateCellRequest(snapshot_id="snapshot", cells=cells)


@pytest.mark.parametrize("kind", ("rows", "columns"))
async def test_server_pages_preserve_exact_snapshot_and_pagination(coordinates, kind):
    service, reader, manifest, dataset, table = coordinates
    item = RowRange(1, 1, 5) if kind == "rows" else ColumnOrigin(1, 6, (), "int", ((3, 6),))
    method = reader.read_row_ranges if kind == "rows" else reader.read_column_bindings
    method.return_value = CoordinatePage(manifest, (item,), 2, 2, 1, 2, False, True)
    value = await getattr(service, kind)(
        "issuer|reader", "north", dataset, table, manifest.snapshot_id, page=2, page_size=1
    )
    assert (value.page, value.pages, value.total, value.has_previous) == (2, 2, 2, True)
    assert value.manifest.snapshot_id == manifest.snapshot_id
    method.return_value = replace(method.return_value, total_pages=99)
    with pytest.raises(ServiceUnavailableException):
        await getattr(service, kind)(
            "issuer|reader", "north", dataset, table, manifest.snapshot_id, page=2, page_size=1
        )


async def test_invalid_snapshot_and_page_do_not_reach_reader(coordinates):
    service, reader, manifest, dataset, table = coordinates
    with pytest.raises(InvalidRequestException):
        await service.manifest("issuer|reader", "north", dataset, table, "current")
    for values in ({"page": True}, {"page_size": 101}, {"page": 1000002}):
        with pytest.raises(InvalidRequestException):
            await service.rows("issuer|reader", "north", dataset, table, manifest.snapshot_id, **values)
    reader.read_manifest.assert_not_awaited()
    reader.read_row_ranges.assert_not_awaited()


@pytest.mark.parametrize("changes", ({"page": True}, {"page_size": True}, {"total_pages": True}))
async def test_native_page_cannot_coerce_booleans_into_recorded_counts(coordinates, changes):
    service, reader, manifest, dataset, table = coordinates
    reader.read_row_ranges.return_value = replace(
        CoordinatePage(manifest, (RowRange(0, 2, 4),), 1, 1, 1, 1, False, False), **changes
    )
    with pytest.raises(ServiceUnavailableException):
        await service.rows("issuer|reader", "north", dataset, table, manifest.snapshot_id, page_size=1)


async def test_missing_coordinate_datasource_is_actionable(coordinates):
    from pyfly.data.relational.datasource_registry import NoSuchDataSourceError

    service, reader, manifest, dataset, table = coordinates
    reader.read_manifest.side_effect = NoSuchDataSourceError("structured")
    with pytest.raises(ServiceUnavailableException) as error:
        await service.manifest("issuer|reader", "north", dataset, table, manifest.snapshot_id)
    assert error.value.code == "COORDINATES_UNAVAILABLE"


async def test_nested_native_source_type_is_preserved_without_truncation(coordinates):
    service, reader, manifest, dataset, table = coordinates
    native_type = (
        '{"type":"record","fields":['
        + ",".join('{"name":"value' + str(n) + '","type":"long"}' for n in range(40))
        + "]}"
    )
    assert 512 < len(native_type) < 4096
    reader.read_column_bindings.return_value = CoordinatePage(
        replace(manifest, column_count=1),
        (ColumnOrigin(0, 0, (), native_type, ()),),
        1,
        1,
        25,
        1,
        False,
        False,
    )
    result = await service.columns("issuer|reader", "north", dataset, table, manifest.snapshot_id)
    assert result.items[0].source_type == native_type


async def test_complete_column_mapping_cannot_omit_a_recorded_output_column(coordinates):
    service, reader, manifest, dataset, table = coordinates
    reader.read_column_bindings.return_value = CoordinatePage(
        manifest, (ColumnOrigin(0, 0),), 1, 1, 25, 1, False, False
    )
    with pytest.raises(ServiceUnavailableException):
        await service.columns("issuer|reader", "north", dataset, table, manifest.snapshot_id)
