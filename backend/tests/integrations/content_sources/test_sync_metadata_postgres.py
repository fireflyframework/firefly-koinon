# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reconcile provider structure without changing committed content provenance."""

from contextlib import asynccontextmanager
from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_connection_lifecycle import lifecycle as lifecycle
from test_mapping_policy_service import empty_listing as empty_listing
from test_mapping_review import review as review
from test_source_migration_postgres import source_database as source_database
from test_sync_publication_service import claimed_source_file as claimed_source_file
from test_sync_publication_service import producer as producer
from test_sync_publication_service import source_ack_port
from test_sync_publication_service import source_files as source_files

from koinon.catalog.entities import CatalogEntry
from koinon.catalog.service import CatalogService
from koinon.integrations.content_sources.account_operations import SourceAccountOperations
from koinon.integrations.content_sources.credentials import SourceCredentialVault
from koinon.integrations.content_sources.dtos import DownloadReceipt
from koinon.integrations.content_sources.lifecycle import _no_remote_unit
from koinon.integrations.content_sources.mapping_entities import SourceMapping, SourceObject
from koinon.integrations.content_sources.mapping_service import SourceMappings
from koinon.integrations.content_sources.publication_baselines import SourcePublicationBaselines
from koinon.integrations.content_sources.publication_entities import SourcePublicationBaseline
from koinon.integrations.content_sources.settings import ContentSourceSettings
from koinon.integrations.content_sources.sync_checkpoints import SourceCheckpoints
from koinon.integrations.content_sources.sync_dtos import SourceControlInput
from koinon.integrations.content_sources.sync_entities import (
    SourceMappingPolicy,
    SourceSyncState,
    SourceSyncWork,
)
from koinon.integrations.content_sources.sync_files import SourceFiles
from koinon.integrations.content_sources.sync_folders import SourceFolders
from koinon.integrations.content_sources.sync_heartbeat import SourceSyncHeartbeat
from koinon.integrations.content_sources.sync_replacement import SourceReplacements
from koinon.integrations.content_sources.sync_runs import SourceRunRepository
from koinon.integrations.content_sources.sync_walk import WalkItem, WalkPage
from koinon.integrations.content_sources.sync_worker import SourceSyncWorker
from koinon.security.authority import primary_authority
from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings

pytestmark = pytest.mark.integration


async def begin_observed_run(value, item, monkeypatch):
    """Complete the first actual scan and admit the provider's next observation."""
    mappings = value.review.context.get_bean(SourceMappings)
    async with primary_authority():
        session = value.guard._require_session()
        mapping = await session.get(SourceMapping, value.admission.mapping_id)
        policy = await session.get(SourceMappingPolicy, value.execution.policy_id)
    capture = await mappings.remote_capture(value.admission.owner, value.admission.tenant_id, mapping, policy)
    async with primary_authority(read_only=False):
        await value.writer.authority.source_destination(value.admission)
        session = value.guard._require_session()
        assert await SourceRunRepository(session=session).finish(value.execution, capture=capture)
        revision = (await session.get(SourceSyncState, mapping.id)).revision
    catalog = value.writer.authority.catalog
    with monkeypatch.context() as patch:
        patch.setattr(catalog, "get", CatalogService.get.__get__(catalog, CatalogService))
        started = await mappings.execute(
            value.admission.owner,
            value.admission.tenant_id,
            mapping.id,
            "sync",
            SourceControlInput(operation_id=str(uuid4()), expected_revision=revision),
        )
    value.changed.update(name=item.name, version=item.version)
    async with primary_authority(read_only=False):
        await value.writer.authority.source_destination(value.admission)
        session = value.guard._require_session()
        execution = await SourceRunRepository(session=session).claim(
            value.admission.tenant_id, value.admission.owner, started.run_id, "structure-worker"
        )
        state = await session.get(SourceSyncState, mapping.id)
        state.scan_max_items = value.review.context.get_bean(ContentSourceSettings).sync_max_scan_items
        state.scan_observed_count = 0
        state.revision += 1
        await session.flush()
        pins = await SourceCheckpoints(session=session).append(
            execution,
            0,
            WalkPage((WalkItem(item, ("selected",)),), None, True, 1),
            cursor_ciphertext=None,
        )
    return replace(value.admission, run_id=execution.run_id, items=pins), execution


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_worker_reconciles_committed_file_rename_without_reimport(claimed_source_file, monkeypatch):
    current = claimed_source_file
    value, lease = current.producer, current.lease
    port, receipt = await source_ack_port(current)
    await port.acknowledge(lease, receipt)
    async with primary_authority():
        header = await value.guard._require_session().scalar(select(SourcePublicationBaseline))
        original = (header.descriptor_json, header.acknowledgement_json, header.acknowledgement_sha256)
    admission, execution = await begin_observed_run(
        value, replace(value.remote_item, name="renamed.txt"), monkeypatch
    )
    assert admission.items[0].generation == value.admission.items[0].generation
    mappings = value.review.context.get_bean(SourceMappings)
    original_source = mappings.browser._source

    @asynccontextmanager
    async def source(scope, token):
        async with original_source(scope, token) as adapter:

            async def download(item, sink, *, max_bytes, export_mime):
                _no_remote_unit()
                await sink.write(current.content)
                return DownloadReceipt(scope, item.item_id, item.version, 7, receipt.sha256, item.mime_type)

            adapter.download = download
            yield adapter

    monkeypatch.setattr(mappings.browser, "_source", source)
    capacity = WorkAdmission(WorkAdmissionSettings())
    service = SourceSyncWorker(
        mappings,
        SourceFolders(value.writer),
        SourceFiles(value.writer, mappings),
        SourceReplacements(value.writer, mappings, None, None),
        capacity,
        value.review.context.get_bean(ContentSourceSettings),
        value.review.context.get_bean(SourceCredentialVault),
        SourceAccountOperations(mappings.connections),
        SourceSyncHeartbeat(SourceRunRepository(), value.review.context.get_bean(ContentSourceSettings)),
    )
    try:
        assert await service.dispatch(admission, execution) == "acknowledged"
        async with primary_authority(read_only=False):
            session = value.guard._require_session()
            source_row = await session.get(CatalogEntry, lease.source_id)
            asset = await session.get(CatalogEntry, lease.asset_id)
            origin = await session.get(SourceObject, admission.items[0].object_id)
            work = await session.get(SourceSyncWork, admission.items[0].work_id)
            assert source_row.name == asset.name == "renamed.txt"
            assert origin.generation == value.admission.items[0].generation
            assert origin.published_native_version_id == "native-version"
            assert origin.remote_name == "renamed.txt"
            assert work.status == "imported" and work.error_code is None
            current_header = await SourcePublicationBaselines(session).previous(admission, origin)
            assert current_header.attempt_id == header.attempt_id
            assert (
                current_header.descriptor_json,
                current_header.acknowledgement_json,
                current_header.acknowledgement_sha256,
            ) == original
    finally:
        capacity.close_workers()
