# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Signed HTTP with actual dependency injection and a controlled native read port."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from flyquery.core.services.ingestion.coordinates import ColumnOrigin, RowRange
from test_http_contract import bearer as bearer
from test_http_contract import client as client
from test_http_contract import enable_knowledge_routes as enable_knowledge_routes
from test_http_contract import hierarchy as hierarchy
from test_provenance_http import prepared

from koinon.knowledge.lineage.coordinate_dtos import (
    CoordinateManifest,
    CoordinatePage,
    CoordinateSelection,
    SourceCell,
)
from koinon.knowledge.lineage.coordinate_ports import StructuredCoordinatesPort
from koinon.knowledge.lineage.coordinate_service import NativeStructuredCoordinates


def setup_coordinates(client, hierarchy, monkeypatch):
    context, _, native_dataset, native_table, snapshot, dataset, table, _ = prepared(
        client, hierarchy, monkeypatch
    )
    reader = context.get_bean(StructuredCoordinatesPort)
    assert isinstance(reader, NativeStructuredCoordinates)
    manifest = CoordinateManifest(
        tenant_id="north",
        workspace_id=client.workspace_id,
        dataset_id=native_dataset,
        table_id=native_table,
        snapshot_id=snapshot,
        status="complete",
        row_count=1,
        column_count=1,
        artifact_id="artifact",
        run_id="run",
        input_sha256="a" * 64,
        mapping_sha256="b" * 64,
        source_format="CSV",
        source_variant="csv",
        row_kind="record",
    )
    reads = {
        "read_manifest": AsyncMock(return_value=manifest),
        "read_cells": AsyncMock(
            return_value=CoordinateSelection(manifest, (SourceCell(0, 0, 1, 0, (), ((0, 0),), "int"),))
        ),
        "read_row_ranges": AsyncMock(
            return_value=CoordinatePage(manifest, (RowRange(0, 1, 1),), 1, 1, 25, 1, False, False)
        ),
        "read_column_bindings": AsyncMock(
            return_value=CoordinatePage(
                manifest, (ColumnOrigin(0, 0, (), "int", ((0, 0),)),), 1, 1, 25, 1, False, False
            )
        ),
    }
    for name, read in reads.items():
        monkeypatch.setattr(reader, name, read)
    return manifest, reads, f"/api/v1/tenants/north/datasets/{dataset}/tables/{table}/coordinates", dataset


def test_all_coordinate_routes_use_exact_scoped_snapshot(client, hierarchy, monkeypatch):
    manifest, reads, path, dataset = setup_coordinates(client, hierarchy, monkeypatch)
    for suffix in ("", "/rows", "/columns"):
        assert client.get(path + suffix, params={"snapshot_id": manifest.snapshot_id}).status_code == 401
        response = client.get(
            path + suffix, params={"snapshot_id": manifest.snapshot_id}, headers=bearer("viewer")
        )
        assert response.status_code == 200, response.text
        result = response.json()
        value = result if not suffix else result["manifest"]
        assert value["dataset_id"] == dataset and value["snapshot_id"] == manifest.snapshot_id
    response = client.post(
        path + "/cells",
        json={"snapshot_id": manifest.snapshot_id, "cells": [{"row": 0, "column": 0}]},
        headers=bearer("viewer"),
    )
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["source_row"] == 1
    for read in reads.values():
        assert read.await_args.kwargs["snapshot_id"] == manifest.snapshot_id
        assert read.await_args.kwargs["actor"].endswith("|viewer")


def test_coordinate_validation_and_pat_read_scope_precede_native_read(client, hierarchy, monkeypatch):
    manifest, reads, path, dataset = setup_coordinates(client, hierarchy, monkeypatch)
    for payload, status in (
        ({"snapshot_id": manifest.snapshot_id, "cells": [{"row": True, "column": 0}]}, 422),
        ({"snapshot_id": manifest.snapshot_id, "cells": [{"row": 0, "column": 0}] * 2}, 422),
        ({"snapshot_id": "current", "cells": [{"row": 0, "column": 0}]}, 400),
    ):
        assert client.post(path + "/cells", json=payload, headers=bearer()).status_code == status
    reads["read_cells"].assert_not_awaited()
    assert (
        client.get(
            path + "/rows", params={"snapshot_id": manifest.snapshot_id, "page_size": 101}, headers=bearer()
        ).status_code
        == 400
    )
    reads["read_row_ranges"].assert_not_awaited()
    for scopes, expected in ((["catalog:read"], 200), (["profile:read"], 403)):
        issued = client.post(
            "/api/v1/tokens",
            headers=bearer(),
            json={
                "name": "Coordinate access",
                "tenant_id": "north",
                "scopes": scopes,
                "asset_ids": [dataset],
                "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
        )
        assert issued.status_code == 201
        authorization = {"Authorization": "Bearer " + issued.json()["token"]}
        reads["read_cells"].reset_mock()
        response = client.post(
            path + "/cells",
            headers=authorization,
            json={"snapshot_id": manifest.snapshot_id, "cells": [{"row": 0, "column": 0}]},
        )
        assert response.status_code == expected, response.text
        if expected == 403:
            reads["read_cells"].assert_not_awaited()
        assert client.delete("/api/v1/tokens/" + issued.json()["id"], headers=bearer()).status_code == 204
        reads["read_cells"].reset_mock()
        assert (
            client.get(path, params={"snapshot_id": manifest.snapshot_id}, headers=authorization).status_code
            == 401
        )
        reads["read_cells"].assert_not_awaited()
