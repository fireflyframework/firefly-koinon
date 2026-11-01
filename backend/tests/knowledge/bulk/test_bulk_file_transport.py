# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0

from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit
from test_bulk_native import bulk as bulk
from test_bulk_native import request

from koinon.knowledge.bulk.dtos import BulkAction
from koinon.knowledge.bulk.queue import BulkQueue
from koinon.knowledge.bulk.repositories import BulkRepository


async def test_streamed_upload_persists_pinned_receipt_only_after_current_writer_cas(bulk, tmp_path):
    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "create")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    ticket = await bulk.service.reserve_stream("issuer|editor", "north", batch.id, item.id, "upload")
    path = tmp_path / "original"
    path.write_bytes(b"original")
    await bulk.service.finish_stream(
        "issuer|editor", "north", batch.id, item.id, ticket, path, 8, ticket.sha256
    )
    registry = bulk.context.get_bean(DataSourceRegistry)
    async with infrastructure_unit(registry.get("primary")):
        upload = await bulk.context.get_bean(BulkRepository).upload_by_id(ticket.upload_id)
        assert upload.object_reference_json["sha256"] == ticket.sha256
    current = await bulk.service.get("issuer|editor", "north", batch.id)
    await bulk.service.submit(
        "issuer|editor", "north", batch.id, BulkAction(expected_revision=current.revision), "submit"
    )
    queue = bulk.context.get_bean(BulkQueue)
    lease = await queue.claim("worker")
    original = await queue.original(lease)
    restored = tmp_path / "restored"
    reference = await bulk.service.storage.read_file(original, restored)
    assert restored.read_bytes() == b"original" and reference.to_dict() == upload.object_reference_json


async def test_capabilities_and_manifest_admission_honor_smaller_shared_scratch_budget(bulk):
    import pytest
    from pyfly.kernel import PayloadTooLargeException

    bulk.service.storage.scratch.capacity_bytes = 12
    capability = await bulk.service.capabilities("issuer|editor", "north", bulk.target["workspace_id"])
    assert capability.max_file_bytes == 6
    with pytest.raises(PayloadTooLargeException):
        await bulk.service.create("issuer|editor", "north", request(bulk.target, b"1234567"), "too-large")
