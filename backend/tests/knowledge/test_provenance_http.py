# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Signed HTTP and real DI; native storage is a controlled read-port fixture."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from unittest.mock import AsyncMock
from uuid import uuid4

from test_http_contract import bearer as bearer
from test_http_contract import client as client
from test_http_contract import enable_knowledge_routes as enable_knowledge_routes
from test_http_contract import hierarchy as hierarchy

from koinon.catalog.service import CatalogService
from koinon.knowledge.adapters import NativeDomains
from koinon.knowledge.lineage.dtos import LineagePage, SnapshotLineage, SourceArtifact, TransformStep
from koinon.knowledge.lineage.ports import StructuredSnapshotLineagePort
from koinon.knowledge.lineage.service import NativeStructuredLineage


def prepared(client, hierarchy, monkeypatch):
    context = client.native_app.state.context
    native_dataset, native_table, snapshot = (str(uuid4()) for _ in range(3))
    domains = context.get_bean(NativeDomains)
    monkeypatch.setattr(domains, "ensure_workspace", AsyncMock(return_value=client.workspace_id))
    monkeypatch.setattr(
        domains,
        "ingest_dataset",
        AsyncMock(
            return_value={
                "dataset_id": native_dataset,
                "file_id": str(uuid4()),
                "tables": [{"table_id": native_table, "name": "Forecast", "snapshot_id": snapshot}],
            }
        ),
    )
    content = b"value\n47\n"
    response = client.post(
        "/api/v1/tenants/north/sources/upload",
        headers=bearer(),
        data={**hierarchy, "mode": "dataset"},
        files={"file": ("plan.csv", content)},
    )
    assert response.status_code == 201, response.text
    dataset = response.json()["assets"][0]["id"]

    async def table_id():
        return (
            await context.get_bean(CatalogService).list(
                "https://identity.example.test/realms/koinon|admin", "north", kind="table", parent_id=dataset
            )
        )[0].id

    table = client.portal.call(table_id)
    reader = context.get_bean(StructuredSnapshotLineagePort)
    assert isinstance(reader, NativeStructuredLineage)
    return context, reader, native_dataset, native_table, snapshot, dataset, table, content


def test_signed_http_resolves_native_port_and_preserves_exact_snapshot(client, hierarchy, monkeypatch):
    _, reader, native_dataset, native_table, snapshot, dataset, table, content = prepared(
        client, hierarchy, monkeypatch
    )
    stamp = datetime(2026, 10, 27, tzinfo=UTC)
    source_hash = sha256(content).hexdigest()
    receipt = SnapshotLineage(
        tenant_id="north",
        workspace_id=client.workspace_id,
        dataset_id=native_dataset,
        table_id=native_table,
        snapshot_id=snapshot,
        snapshot_status="READY",
        status="recorded",
        artifact=SourceArtifact(
            "artifact", "plan.csv", source_hash, len(content), "CSV", "none", "recorded-author", stamp
        ),
        run_id="transform",
        operation="upload",
        parquet_sha256="b" * 64,
        parquet_byte_size=345,
        schema_sha256="c" * 64,
        row_count=1,
        actor="recorded-author",
        recorded_at=stamp,
        steps=(
            TransformStep(
                "step", 1, "materialize", "test.reader", source_hash, "b" * 64, {}, "recorded-author", stamp
            ),
        ),
    )
    read = AsyncMock(return_value=(receipt,))
    monkeypatch.setattr(reader, "read_snapshots", read)
    path = f"/api/v1/tenants/north/datasets/{dataset}/tables/{table}/provenance?snapshot_id={snapshot}"
    assert client.get(path).status_code == 401
    response = client.get(path, headers=bearer("viewer"))
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["dataset_id"] == dataset and value["table_id"] == table
    assert value["artifact"]["sha256"] == source_hash
    assert value["parquet_sha256"] == "b" * 64 and value["schema_sha256"] == "c" * 64
    assert read.await_args.kwargs["snapshot_ids"] == (snapshot,)
    read.reset_mock()
    assert client.get(path.replace("/north/", "/south/"), headers=bearer()).status_code == 403
    read.assert_not_awaited()


def test_signed_http_history_is_paged_and_keeps_unrecorded_origin(client, hierarchy, monkeypatch):
    _, reader, native_dataset, native_table, snapshot, dataset, table, _ = prepared(
        client, hierarchy, monkeypatch
    )
    current = str(uuid4())
    old = SnapshotLineage(
        tenant_id="north",
        workspace_id=client.workspace_id,
        dataset_id=native_dataset,
        table_id=native_table,
        snapshot_id=snapshot,
        snapshot_status="READY",
        status="not_recorded",
    )
    read = AsyncMock(return_value=LineagePage((old,), 26, 2, 25, 2, False, True, current))
    monkeypatch.setattr(reader, "read_table_history", read)
    path = f"/api/v1/tenants/north/datasets/{dataset}/tables/{table}/snapshots"
    response = client.get(path + "?page=2&page_size=25", headers=bearer("viewer"))
    assert response.status_code == 200, response.text
    value = response.json()
    assert (value["page"], value["total"], value["current_snapshot_id"]) == (2, 26, current)
    assert value["items"][0]["status"] == "not_recorded"
    assert value["items"][0]["artifact"] is None and "steps" not in value["items"][0]
    read.reset_mock()
    assert client.get(path + "?page_size=101", headers=bearer()).status_code == 400
    read.assert_not_awaited()


def test_provenance_pat_scope_and_revocation_precede_native_read(client, hierarchy, monkeypatch):
    _, reader, native_dataset, native_table, snapshot, dataset, table, _ = prepared(
        client, hierarchy, monkeypatch
    )
    receipt = SnapshotLineage(
        tenant_id="north",
        workspace_id=client.workspace_id,
        dataset_id=native_dataset,
        table_id=native_table,
        snapshot_id=snapshot,
        snapshot_status="READY",
        status="not_recorded",
    )
    read = AsyncMock(return_value=(receipt,))
    monkeypatch.setattr(reader, "read_snapshots", read)
    path = f"/api/v1/tenants/north/datasets/{dataset}/tables/{table}/provenance?snapshot_id={snapshot}"
    for scopes, expected in ((["catalog:read"], 200), (["chat:use"], 200), (["profile:read"], 403)):
        issued = client.post(
            "/api/v1/tokens",
            headers=bearer(),
            json={
                "name": "Scoped provenance",
                "tenant_id": "north",
                "scopes": scopes,
                "asset_ids": [dataset],
                "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
        )
        assert issued.status_code == 201
        authority = {"Authorization": "Bearer " + issued.json()["token"]}
        read.reset_mock()
        response = client.get(path, headers=authority)
        assert response.status_code == expected
        if expected == 403:
            read.assert_not_awaited()
        assert client.delete("/api/v1/tokens/" + issued.json()["id"], headers=bearer()).status_code == 204
        read.reset_mock()
        response = client.get(path, headers=authority)
        assert response.status_code == 401
        read.assert_not_awaited()
