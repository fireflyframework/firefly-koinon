# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


async def test_coordinates_persist_atomically_and_read_exact_bounded_points_and_sql_pages(monkeypatch):
    from flyquery.core.services.ingestion.coordinates import (
        ColumnOrigin,
        MaterializationCoordinates,
        RowRange,
    )
    from pyfly.kernel import InvalidRequestException
    from sqlalchemy import ForeignKeyConstraint, MetaData, text

    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.lineage import coordinate_service as module
    from koinon.knowledge.lineage.coordinate_dtos import CellPosition
    from koinon.knowledge.lineage.coordinate_entities import (
        CoordinateColumnRow,
        CoordinateManifestRow,
        CoordinateRangeRow,
    )

    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.execute(text("PRAGMA foreign_keys=ON"))
        metadata = MetaData()
        for entity in (CoordinateManifestRow, CoordinateRangeRow, CoordinateColumnRow):
            copied = entity.__table__.to_metadata(metadata)
            if entity is not CoordinateManifestRow:
                copied.append_constraint(
                    ForeignKeyConstraint(["snapshot_id"], ["flyquery_coordinate_manifests.snapshot_id"])
                )
            await connection.run_sync(copied.create)
        await connection.execute(
            text(
                "CREATE TABLE flyquery_schema_snapshots(id CHAR(32),tenant_id TEXT,workspace_id CHAR(32),"
                "dataset_id CHAR(32),table_id CHAR(32),n_rows_actual INTEGER,n_columns INTEGER)"
            )
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def unit(*args, **kwargs):
        async with factory.begin() as session:
            yield session

    monkeypatch.setattr(module, "infrastructure_unit", unit)
    workspace, dataset, table, snapshot, old, run, artifact = [uuid4() for _ in range(7)]
    scope = dict(
        actor="owner",
        tenant_id="north",
        workspace_id=str(workspace),
        dataset_id=str(dataset),
        table_id=str(table),
        snapshot_id=str(snapshot),
    )
    mapping = MaterializationCoordinates(
        "excel",
        "xlsx",
        "sheet_row",
        "a" * 64,
        3,
        2,
        (RowRange(0, 1, 6), RowRange(1, 2, 9)),
        (ColumnOrigin(0, 3, (), None, ((3, 3),)), ColumnOrigin(1, 6, (), None, ((3, 6),))),
        source_sheet="Facts",
    )
    async with factory.begin() as session:
        for identifier in (snapshot, old):
            await session.execute(
                text(
                    "INSERT INTO flyquery_schema_snapshots VALUES(:id,:tenant,:workspace,:dataset,:table,3,2)"
                ),
                dict(
                    id=identifier.hex,
                    tenant="north",
                    workspace=workspace.hex,
                    dataset=dataset.hex,
                    table=table.hex,
                ),
            )
        await module.persist_coordinates(
            session,
            **scope,
            run_id=run,
            artifact_id=artifact,
            coordinates=mapping,
            row_count=3,
            column_count=2,
            input_sha256="a" * 64,
        )
    from flyquery.core.services.ingestion.lineage import LineageError

    with pytest.raises(LineageError, match="verified materialization"):
        async with factory.begin() as session:
            await module.persist_coordinates(
                session,
                **(scope | {"snapshot_id": str(old)}),
                run_id=run,
                artifact_id=artifact,
                coordinates=mapping,
                row_count=3,
                column_count=2,
                input_sha256="b" * 64,
            )
    service = module.NativeStructuredCoordinates(SimpleNamespace(get=lambda _: object()))
    selected = await service.read_cells(**scope, cells=(CellPosition(2, 1), CellPosition(0, 0)))
    assert selected.manifest.status == "complete" and selected.manifest.mapping_sha256 == mapping.digest()
    assert [(point.source_row, point.source_column) for point in selected.items] == [(10, 6), (6, 3)]
    assert selected.items[0].header_cells == ((3, 6),)
    page = await service.read_row_ranges(**scope, page=2, page_size=1)
    assert page.total == 2 and page.items[0].output_start == 1 and page.has_previous and not page.has_next
    assert (await service.read_manifest(**(scope | {"snapshot_id": str(old)}))).status == "not_recorded"
    with pytest.raises(InvalidRequestException):
        await service.read_cells(**scope, cells=(CellPosition(3, 0),))
    with pytest.raises(InvalidRequestException):
        await service.read_cells(**scope, cells=(CellPosition(0, 0),) * 1001)
    with pytest.raises(AccessDenied):
        await service.read_manifest(**(scope | {"tenant_id": "foreign"}))
    with pytest.raises(RuntimeError):
        async with factory.begin() as session:
            await module.persist_coordinates(
                session,
                **(scope | {"snapshot_id": str(old)}),
                run_id=run,
                artifact_id=artifact,
                coordinates=mapping,
                row_count=3,
                column_count=2,
                input_sha256="a" * 64,
            )
            raise RuntimeError("rollback")
    assert (await service.read_manifest(**(scope | {"snapshot_id": str(old)}))).status == "not_recorded"
    await engine.dispose()
