# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings


@pytest.mark.parametrize("wrong", ["tenant", "workspace", "status", None])
async def test_native_append_verifies_scoped_active_dataset_and_retains_all_table_results(wrong):
    from flyquery.core.services.datasets.dataset_service import DatasetService
    from flyquery.core.services.ingestion.ingest_service import IngestedTable, IngestResult, IngestService
    from pyfly.kernel import ForbiddenException

    from koinon.knowledge.adapters import NativeDomains

    workspace, dataset = uuid4(), uuid4()
    row = {
        "id": dataset,
        "tenant_id": "north",
        "workspace_id": workspace,
        "status": "ACTIVE",
        "name": "Sales",
    }
    if wrong == "tenant":
        row["tenant_id"] = "south"
    elif wrong == "workspace":
        row["workspace_id"] = uuid4()
    elif wrong == "status":
        row["status"] = "ARCHIVED"
    tables = [IngestedTable(str(uuid4()), name, 2, 3, str(uuid4())) for name in ("Sales", "Returns")]
    dataset_service = SimpleNamespace(get=AsyncMock(return_value=row), create=AsyncMock())
    ingest = SimpleNamespace(ingest_upload=AsyncMock(return_value=IngestResult(str(uuid4()), tables)))
    services = {DatasetService: dataset_service, IngestService: ingest}
    container = SimpleNamespace(
        contains_type=lambda kind: kind in services, resolve=lambda kind: services[kind]
    )
    domains = NativeDomains(container, admission=WorkAdmission(WorkAdmissionSettings()))
    captures = []

    @asynccontextmanager
    async def scoped(**arguments):
        captures.append(arguments)
        yield

    domains.structured_lineage = scoped
    arguments = dict(
        tenant_id="north",
        workspace_id=str(workspace),
        dataset_id=str(dataset),
        filename="more.xlsx",
        content=b"bytes",
        actor="issuer|admin",
        source_catalog_id="canonical-dataset",
    )
    operation = domains.append_dataset_file
    if wrong is not None:
        with pytest.raises(ForbiddenException):
            await operation.__wrapped__(domains, **arguments)
        ingest.ingest_upload.assert_not_awaited()
    else:
        result = await operation.__wrapped__(domains, **arguments)
        assert [table["name"] for table in result["tables"]] == ["Sales", "Returns"]
        assert captures[0]["source_catalog_id"] == "canonical-dataset"
        assert captures[0]["dataset_id"] == str(dataset)
        assert ingest.ingest_upload.await_args.kwargs["max_tables"] == 128
        assert ingest.ingest_upload.await_args.kwargs["append_only"] is True
        assert ingest.ingest_upload.await_args.kwargs["dataset_name"] == "Sales"
    dataset_service.create.assert_not_awaited()


async def test_native_append_limit_fails_before_describe_embed_or_publish(monkeypatch, tmp_path):
    from flyquery.config import FlyquerySettings
    from flyquery.core.services.ingestion import ingest_service as module
    from pyfly.kernel import PayloadTooLargeException

    received_copy = tmp_path / "received.xlsx"
    received_copy.write_bytes(b"123")
    received = SimpleNamespace(
        file_id=uuid4(),
        size_bytes=3,
        local_temp_path=str(received_copy),
        file_format="xlsx",
        compression="none",
    )
    monkeypatch.setattr(module, "run_receive", AsyncMock(return_value=received))
    monkeypatch.setattr(module, "run_parse", AsyncMock(return_value=[object(), object()]))
    workspace_service = SimpleNamespace(
        get=AsyncMock(return_value={"storage_used_bytes": 0}), track_storage=AsyncMock()
    )
    native = module.IngestService(FlyquerySettings(), object(), workspace_service, lambda: None, object())
    process = AsyncMock()
    monkeypatch.setattr(native, "_process_section", process)
    with pytest.raises(PayloadTooLargeException):
        await native.ingest_upload(
            tenant_id="north",
            workspace_id=uuid4(),
            dataset_id=uuid4(),
            filename="two.xlsx",
            file_bytes=b"123",
            actor="owner",
            max_tables=1,
        )
    process.assert_not_awaited()
    assert not received_copy.exists()
