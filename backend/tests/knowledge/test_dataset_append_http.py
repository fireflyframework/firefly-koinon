# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import AsyncMock
from uuid import uuid4

from test_http_contract import bearer as bearer
from test_http_contract import client as client
from test_http_contract import enable_knowledge_routes as enable_knowledge_routes
from test_http_contract import hierarchy as hierarchy


def test_append_http_binds_existing_dataset_and_checks_authority_before_reading_bytes(
    client, hierarchy, monkeypatch
):
    from koinon.knowledge.adapters import NativeDomains

    domains = client.native_app.state.context.get_bean(NativeDomains)
    monkeypatch.setattr(domains, "ensure_workspace", AsyncMock(return_value=client.workspace_id))
    dataset_id = str(uuid4())
    monkeypatch.setattr(
        domains,
        "ingest_dataset",
        AsyncMock(
            return_value={
                "dataset_id": dataset_id,
                "file_id": str(uuid4()),
                "tables": [],
            }
        ),
    )
    ingest = AsyncMock(
        return_value={
            "file_id": str(uuid4()),
            "tables": [
                {
                    "table_id": str(uuid4()),
                    "name": "More",
                    "snapshot_id": str(uuid4()),
                    "n_columns": 1,
                    "n_rows_estimate": 1,
                },
            ],
        }
    )
    monkeypatch.setattr(domains, "append_dataset_file", ingest)
    uploaded = client.post(
        "/api/v1/tenants/north/sources/upload",
        headers={**bearer(), "Idempotency-Key": "append-http-key"},
        data={**hierarchy, "mode": "dataset"},
        files={"file": ("first.csv", b"x\n1")},
    )
    assert uploaded.status_code == 201, uploaded.text
    canonical = uploaded.json()["assets"][0]["id"]
    path = f"/api/v1/tenants/north/datasets/{canonical}/files"
    denied = client.post(path, headers=bearer("viewer"), files={"file": ("more.csv", b"x\n2")})
    assert denied.status_code == 403, denied.text
    ingest.assert_not_awaited()
    response = client.post(
        path,
        headers={**bearer(), "X-Actor": "forged", "Idempotency-Key": "append-http-key"},
        files={"file": ("more.csv", b"x\n2")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["dataset_id"] == canonical
    assert len(response.json()["table_ids"]) == 1
    assert response.headers["cache-control"] == "private, no-store"
    assert ingest.await_args.kwargs["dataset_id"] == dataset_id
    assert ingest.await_args.kwargs["actor"].endswith("|admin")
    repeated = client.post(
        path,
        headers={**bearer(), "Idempotency-Key": "append-http-key"},
        files={"file": ("more.csv", b"x\n2")},
    )
    assert repeated.status_code == 201 and repeated.json() == response.json()
    conflict = client.post(
        path,
        headers={**bearer(), "Idempotency-Key": "append-http-key"},
        files={"file": ("more.csv", b"x\n3")},
    )
    assert conflict.status_code == 409 and conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"
    missing = client.post(path, headers=bearer(), files={"file": ("more.csv", b"x\n2")})
    assert missing.status_code == 400
    assert ingest.await_count == 1


def test_append_http_rejects_extra_fields_and_oversize_upload_without_native_effects(
    client, hierarchy, monkeypatch
):
    from koinon.knowledge.adapters import NativeDomains
    from koinon.knowledge.dataset_append import DatasetFiles
    from koinon.knowledge.service import KnowledgeFacade

    service = client.native_app.state.context.get_bean(DatasetFiles)
    monkeypatch.setattr(service, "scope", AsyncMock())
    domains = client.native_app.state.context.get_bean(NativeDomains)
    ingest = AsyncMock()
    monkeypatch.setattr(domains, "append_dataset_file", ingest)
    path = "/api/v1/tenants/north/datasets/chosen/files"
    response = client.post(
        path,
        headers={**bearer(), "Idempotency-Key": "append-http-key"},
        data={"dataset_id": "forged"},
        files={"file": ("more.csv", b"x\n2")},
    )
    assert response.status_code == 400, response.text
    facade = client.native_app.state.context.get_bean(KnowledgeFacade)
    facade.settings.max_upload_bytes = 2
    response = client.post(
        path,
        headers={**bearer(), "Idempotency-Key": "append-http-key"},
        files={"file": ("more.csv", b"x\n2")},
    )
    assert response.status_code == 413, response.text
    ingest.assert_not_awaited()
